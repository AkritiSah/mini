from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import math
import random
import time
from threading import Lock, RLock

logger = logging.getLogger('krishi')


class LLMUnavailable(RuntimeError):
    def __init__(self, message, *, category=None, retry_after=None):
        super().__init__(message)
        self.category, self.retry_after = category, retry_after


def _seconds(value):
    try:
        seconds = float(str(value).removesuffix('s'))
        return seconds if math.isfinite(seconds) and seconds >= 0 else None
    except (TypeError, ValueError):
        return None


def _quota_details(error):
    """Read only structured retry/quota fields; never return provider messages."""
    delays, exhausted = [], False
    headers = getattr(getattr(error, 'response', None), 'headers', None)
    if headers is not None:
        value = headers.get('Retry-After')
        seconds = _seconds(value)
        if seconds is None and isinstance(value, str):
            try:
                seconds = max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
        if seconds is not None:
            delays.append(seconds)
    body = getattr(error, 'details', None)
    if isinstance(body, dict):
        body = body.get('error', body)
        details = body.get('details', []) if isinstance(body, dict) else []
    else:
        details = body if isinstance(body, list) else []
    for detail in details if isinstance(details, list) else []:
        if not isinstance(detail, dict):
            continue
        kind = str(detail.get('@type', ''))
        if kind.endswith('RetryInfo'):
            seconds = _seconds(detail.get('retryDelay'))
            if seconds is not None:
                delays.append(seconds)
        if kind.endswith('QuotaFailure'):
            violations = detail.get('violations', [])
            for violation in violations if isinstance(violations, list) else []:
                if not isinstance(violation, dict):
                    continue
                quota_id = str(violation.get('quotaId', '')).lower()
                if 'perday' in quota_id or _seconds(violation.get('quotaValue')) == 0:
                    exhausted = True
    return max(delays, default=None), exhausted


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
        retry_after, exhausted = _quota_details(error)
        if exhausted:
            category, reason, retryable = 'quota_exhausted', 'daily quota exhausted or quota limit is zero; check your project limits and billing in Google AI Studio', False
        else:
            category, reason, retryable = 'rate_limit', 'rate limit reached; wait before retrying and check project limits in Google AI Studio', True
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
            'retry_after_seconds': retry_after if status == 429 else None,
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
        self._request_lock = Lock()

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
        # Coordinate chat and ingestion retries against the same project quota.
        with self._request_lock:
            return self._complete(prompt, system, max_tokens)

    def _complete(self, prompt, system, max_tokens):
        if not self.settings.llm_ready:
            raise LLMUnavailable('Gemini is not configured. Set GEMINI_API_KEY and GEMINI_MODEL in backend/.env.')
        with self._cooldown_lock:
            remaining = self._cooldown_until - time.monotonic()
            if remaining > 0:
                raise LLMUnavailable(f'Gemini temporarily cooling down: {self._failure_reason}. '
                                     f'Retry after {math.ceil(remaining)} seconds.', retry_after=remaining)
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
                               'category=%s cause_type=%s network_errno=%s attempt=%s/%s elapsed_ms=%s retry_after_seconds=%s',
                               self.settings.gemini_model, detail['status'], detail['error_type'], detail['category'],
                               detail['cause_type'], detail['network_errno'], attempt, attempts,
                               round((time.monotonic() - started) * 1000), detail['retry_after_seconds'])
                delay = self.config.get('retry_initial_delay_seconds', 1) * 2 ** (attempt - 1)
                if detail['status'] == 429:
                    delay = max(delay, detail['retry_after_seconds'] or 0,
                                self.config.get('rate_limit_retry_seconds', 30))
                wait_limit = self.config.get('max_retry_wait_seconds', 60)
                if detail['retryable'] and attempt < attempts and delay <= wait_limit:
                    time.sleep(min(wait_limit, delay + random.uniform(0, delay * .25)))
                    continue
                self.connection_status = 'unavailable'
                with self._cooldown_lock:
                    cooldown = max(self.config.get('provider_cooldown_seconds', 30),
                                   detail['retry_after_seconds'] or 0,
                                   self.config.get('rate_limit_retry_seconds', 30) if detail['status'] == 429 else 0)
                    self._cooldown_until = time.monotonic() + cooldown
                    self._failure_reason = reason
                guidance = (f'Retry after at least {math.ceil(cooldown)} seconds.'
                            if detail['retryable'] else 'Resolve the account or model configuration before retrying.')
                raise LLMUnavailable(f'Gemini is unavailable ({reason}). {guidance}',
                                     category=detail['category'], retry_after=cooldown) from None
