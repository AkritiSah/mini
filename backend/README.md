# Backend

From this directory:

```powershell
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
..\.venv\Scripts\python.exe -m pytest -q
```

Set configuration in `.env` using `.env.example`. Retrieval, chunking, translation,
and guardrails are configured in `config.yaml`. Paths resolve relative to this
directory, independent of the launch directory. Full setup and operational details
are in the root [README](../README.md) and [architecture](../ARCHITECTURE.md).
