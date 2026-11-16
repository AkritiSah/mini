from dataclasses import dataclass
import logging
import inspect

logger = logging.getLogger('krishi')


class LLMUnavailable(RuntimeError):
    pass


@dataclass
class Completion:
    text: str
    provider: str
    model: str


class LLMClient:
    def __init__(self, settings, config):
        self.settings = settings
        self.config = config

    def _claude(self, prompt, system, tokens):
        from anthropic import Anthropic
        with Anthropic(api_key=self.settings.anthropic_api_key,
                       timeout=self.config.get('timeout_seconds', 60), max_retries=0) as client:
            arguments = dict(model=self.settings.anthropic_model, max_tokens=tokens,
                system=system, messages=[{'role': 'user', 'content': prompt}])
            # Current Anthropic SDKs removed temperature. Older versions expose it.
            if 'temperature' in inspect.signature(client.messages.create).parameters:
                arguments['temperature'] = self.config['temperature']
            response = client.messages.create(**arguments)
        return '\n'.join(block.text for block in response.content if block.type == 'text')

    def _gemini(self, prompt, system, tokens):
        from google import genai
        from google.genai import types
        with genai.Client(api_key=self.settings.gemini_api_key,
                          http_options=types.HttpOptions(timeout=self.config.get('timeout_seconds', 60) * 1000,
                              retry_options=types.HttpRetryOptions(attempts=1))) as client:
            response = client.models.generate_content(
                model=self.settings.gemini_model, contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system,
                    temperature=self.config['temperature'], max_output_tokens=tokens,
                    thinking_config=types.ThinkingConfig(thinking_level=self.config['gemini_thinking_level'])
                    if self.config.get('gemini_thinking_level') else None))
        return response.text

    def complete(self, prompt: str, system: str, max_tokens=None) -> Completion:
        failures = []
        providers = [
            ('anthropic', self.settings.anthropic_model,
             bool(self.settings.anthropic_api_key and self.settings.anthropic_model), self._claude),
            ('gemini', self.settings.gemini_model, bool(self.settings.gemini_api_key), self._gemini),
        ]
        for provider, model, ready, call in providers:
            if not ready:
                continue
            try:
                text = call(prompt, system, max_tokens or self.config['max_output_tokens'])
                if not isinstance(text, str) or not text.strip():
                    raise ValueError('Empty response')
                return Completion(text.strip(), provider, model)
            except Exception as error:
                # SDK bodies may contain prompts/keys: never log raw exceptions.
                status = getattr(error, 'status_code', None) or getattr(error, 'code', None)
                status = status if isinstance(status, int) else None
                reason = f'HTTP {status}' if status else 'connection or SDK failure'
                failures.append(f'{provider}: {reason}')
                logger.warning('provider=%s generation_failed status=%s error_type=%s',
                               provider, status, type(error).__name__)
        detail = ' (' + '; '.join(failures) + ')' if failures else ''
        raise LLMUnavailable('No LLM is available' + detail + '. Check backend/.env, model access, and account quota.')
