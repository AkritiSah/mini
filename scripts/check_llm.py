"""Check the shared Gemini connection and send one tiny live generation request."""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from src.llm.llm_client import LLMClient, failure_details
from src.settings import Settings, load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, help='Override the Gemini timeout in seconds')
    args = parser.parse_args()
    if args.timeout is not None and args.timeout <= 0:
        parser.error('--timeout must be positive')
    settings = Settings()
    if not settings.llm_ready:
        print('Gemini is not configured. Set GEMINI_API_KEY and GEMINI_MODEL in backend/.env.')
        return 1
    config = dict(load_config()['generation'], max_provider_attempts=1)
    if args.timeout is not None:
        config.update(gemini_timeout_seconds=args.timeout, connection_check_timeout_seconds=args.timeout)
    llm = LLMClient(settings, config)
    started = time.monotonic()
    try:
        llm.initialize()
        print(f'Gemini connection={llm.connection_status} model={settings.gemini_model}', flush=True)
        result = llm.complete('Reply with OK.', 'Connectivity check. Return only OK.', 64)
        print(f'Gemini generation OK model={result.model} elapsed={time.monotonic()-started:.1f}s', flush=True)
        return 0
    except Exception as error:
        from src.llm.llm_client import LLMUnavailable
        reason = str(error) if isinstance(error, LLMUnavailable) else failure_details(error)['reason']
        print(f'Gemini check failed: {reason}', flush=True)
        return 1
    finally:
        llm.close()


if __name__ == '__main__':
    raise SystemExit(main())
