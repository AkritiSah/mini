from dataclasses import dataclass
import logging
import random
import time
from threading import Lock, RLock

logger = logging.getLogger('krishi')


class LLMUnavailable(RuntimeError):
    pass


def failure_details(error):
    """Describe failures without exposing SDK bodies, prompts, URLs, or credentials."""
    chain = []
    current = error
    while current is not None and current not in chain and len(chain) < 8:
        chain.append(current)
        current = current.__cause__ or current.__context__
    status = getattr(error, 'status_code', None) or getattr(error, 'code', None)
    status = status if type(status) is int else None
    names = {type(item).__name__ for item in chain}
    network_errno = next((item.errno for item in reversed(chain)
                          if isinstance(item, OSError) and item.errno is not None), None)
    if status in (401, 403):
        category, reason, retryable = 'authentication', 'credentials rejected; check the API key and model permissions', False
    elif status == 404:
        category, reason, retryable = 'model_not_found', 'model unavailable; check the configured model ID and access', False
    elif status == 429:
        category, reason, retryable = 'rate_limit', 'rate limit or quota exceeded; check billing and retry later', True
    elif status in (408, 504) or names & {'APITimeoutError', 'TimeoutException', 'TimeoutError', 'ConnectTimeout', 'ReadTimeout', 'WriteTimeout', 'PoolTimeout'}:
        category, reason, retryable = 'timeout', 'request timed out; retry later or increase the provider timeout', True
    elif status is not None and 500 <= status <= 599:
        category, reason, retryable = 'provider_unavailable', 'provider temporarily unavailable; retry later', True
    elif names & {'SSLError', 'SSLCertVerificationError'}:
        category, reason, retryable = 'tls', 'TLS verification failed; check certificates and HTTPS proxy settings', False
    elif network_errno in (10054, 104) or 'ConnectionResetError' in names:
        category, reason, retryable = 'connection_reset', 'connection reset; check network, VPN, firewall, and proxy settings', True
    elif network_errno in (10061, 111) or 'ConnectionRefusedError' in names:
        category, reason, retryable = 'connection_refused', 'connection refused; check network and HTTP_PROXY/HTTPS_PROXY settings', True
    elif 'gaierror' in names:
        category, reason, retryable = 'dns', 'DNS lookup failed; check internet access and DNS settings', True
    elif names & {'APIConnectionError', 'ConnectError', 'ProxyError', 'RemoteProtocolError'}:
        category, reason, retryable = 'connection', 'connection failed; check network, firewall, and proxy settings', True
    elif status is not None:
        category, reason, retryable = 'request', 'request rejected; check model parameters and account access', False
    else:
        category, reason, retryable = 'sdk_or_response', 'SDK error or empty response; check SDK compatibility and model settings', False
    return {'status': status, 'category': category, 'reason': reason, 'retryable': retryable,
            'error_type': type(error).__name__, 'cause_type': type(chain[-1]).__name__,
            'network_errno': network_errno}


@dataclass
class Completion:
    text: str
    provider: str
    model: str


class LLMClient:
    def __init__(self, settings, config):
        self.settings, self.config = settings, config
        self._client = None
        self._client_lock = RLock()
        self._closed = False
        self._connection_checked = False
        self.connection_status = 'not_checked' if settings.llm_ready else 'not_configured'
        self._cooldown_until, self._failure_reason = 0, ''
        self._cooldown_lock = Lock()

    def _timeout(self):
        return self.config.get('gemini_timeout_seconds', self.config.get('timeout_seconds', 60))

    def _get_client(self):
        with self._client_lock:
            if self._closed:
                raise LLMUnavailable('Gemini client is closed. Restart the backend.')
            if not self.settings.llm_ready:
                raise LLMUnavailable('Gemini is not configured. Set GEMINI_API_KEY and GEMINI_MODEL in backend/.env.')
            if self._client is None:
                from google import genai
                from google.genai import types
                self._client = genai.Client(api_key=self.settings.gemini_api_key,
                    http_options=types.HttpOptions(timeout=self._timeout() * 1000,
                        retry_options=types.HttpRetryOptions(attempts=1)))
            return self._client

    def initialize(self):
        """Create one pooled client and warm its connection once, without generating text."""
        with self._client_lock:
            if self._connection_checked or not self.settings.llm_ready:
                return
            self._connection_checked = True
            try:
                from google.genai import types
                client = self._get_client()
                client.models.get(model=self.settings.gemini_model,
                    config=types.GetModelConfig(http_options=types.HttpOptions(
                        timeout=self.config.get('connection_check_timeout_seconds', 10) * 1000,
                        retry_options=types.HttpRetryOptions(attempts=1))))
                self.connection_status = 'ready'
                logger.info('provider=gemini model=%s connection_ready client_reused=true', self.settings.gemini_model)
            except Exception as error:
                self.connection_status = 'unavailable'
                detail = failure_details(error)
                logger.warning('provider=gemini connection_check_failed status=%s category=%s cause_type=%s',
                               detail['status'], detail['category'], detail['cause_type'])
                # Startup remains usable for document management; real calls can recover.

    def close(self):
        with self._client_lock:
            if self._closed:
                return
            self._closed = True
            self.connection_status = 'closed'
            if self._client is not None:
                self._client.close()

    def _gemini(self, prompt, system, tokens):
        from google.genai import types
        response = self._get_client().models.generate_content(
            model=self.settings.gemini_model, contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system,
                max_output_tokens=tokens,
                thinking_config=types.ThinkingConfig(thinking_level=self.config['gemini_thinking_level'])
                if self.config.get('gemini_thinking_level') else None))
        return response.text

    def complete(self, prompt: str, system: str, max_tokens=None) -> Completion:
        if not self.settings.llm_ready:
            raise LLMUnavailable('Gemini is not configured. Set GEMINI_API_KEY and GEMINI_MODEL in backend/.env.')
        with self._cooldown_lock:
            if time.monotonic() < self._cooldown_until:
                raise LLMUnavailable(f'Gemini temporarily cooling down: {self._failure_reason}. Retry shortly.')
        attempts = self.config.get('max_provider_attempts', 2)
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            try:
                text = self._gemini(prompt, system, max_tokens or self.config['max_output_tokens'])
                if not isinstance(text, str) or not text.strip():
                    raise ValueError('Empty response')
                self.connection_status = 'ready'
                with self._cooldown_lock:
                    self._cooldown_until, self._failure_reason = 0, ''
                return Completion(text.strip(), 'gemini', self.settings.gemini_model)
            except Exception as error:
                detail = failure_details(error)
                reason = (f"HTTP {detail['status']}: " if detail['status'] else '') + detail['reason']
                logger.warning('provider=gemini model=%s generation_failed status=%s error_type=%s '
                               'category=%s cause_type=%s network_errno=%s attempt=%s/%s elapsed_ms=%s',
                               self.settings.gemini_model, detail['status'], detail['error_type'], detail['category'],
                               detail['cause_type'], detail['network_errno'], attempt, attempts,
                               round((time.monotonic() - started) * 1000))
                if detail['retryable'] and attempt < attempts:
                    delay = self.config.get('retry_initial_delay_seconds', 1) * 2 ** (attempt - 1)
                    time.sleep(delay + random.uniform(0, delay * .25))
                    continue
                self.connection_status = 'unavailable'
                with self._cooldown_lock:
                    self._cooldown_until = time.monotonic() + self.config.get('provider_cooldown_seconds', 30)
                    self._failure_reason = reason
                raise LLMUnavailable(f'Gemini is unavailable ({reason}). Check backend/.env, model access, and account quota.') from None
