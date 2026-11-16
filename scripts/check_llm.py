"""Small live connectivity check using configured backend credentials; no keys printed."""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from src.settings import Settings, load_config
from src.llm.llm_client import LLMClient, LLMUnavailable

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--diagnose-primary', action='store_true')
    args = parser.parse_args()
    settings = Settings()
    client = LLMClient(settings, load_config()['generation'])
    if args.diagnose_primary:
        try:
            client._claude('Reply OK.', 'Connectivity check. Reply only OK.', 64)
            print('Claude connectivity passed.')
        except Exception as error:
            print(f'Claude diagnostic: {type(error).__name__}; cause: {type(error.__cause__).__name__}')
            import traceback
            for frame in traceback.extract_tb(error.__traceback__)[-3:]:
                print(f'Frame: {Path(frame.filename).name}:{frame.lineno} in {frame.name}')
            raise SystemExit(1)
        raise SystemExit(0)
    try:
        result = client.complete(
            'Reply with OK.', 'This is a connectivity check. Reply only with OK.', max_tokens=64)
        print(f'Live LLM check passed: provider={result.provider}, model={result.model}')
    except LLMUnavailable as error:
        print('Live LLM check failed. Both configured providers rejected or could not complete the request. Check key validity, account quota, model access, and connectivity.')
        print(str(error))
        raise SystemExit(1)
