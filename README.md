# Krishi Mitra

A local multilingual, evidence-grounded organic farming assistant for Sikkim.
FastAPI + React/Vite + MongoDB + persistent FAISS + BM25 + reciprocal rank fusion
+ cross-encoder reranking. Claude is primary; **Gemini 3.6 Flash** is the fallback.

## Start on Windows

Requires Python 3.11+, Node 20+, and internet access for initial packages/model
downloads. Run from PowerShell:

```powershell
cd D:\mini
.\run.ps1
```

The launcher creates the virtual environment, installs changed dependencies,
creates `backend/.env` when absent, and starts both services on localhost.
It uses an existing MongoDB connection first. If no server is running,
it downloads a verified project-local MongoDB
Community archive into `.runtime` and starts it on `127.0.0.1:27017`.
This does not install a Windows service. An existing database is never stopped.
The archive is checked against the publisher's SHA-256 when available; if the
checksum service is unreachable, its MongoDB publisher code signature is required.
Press Ctrl+C in the launching terminal to stop the processes it started.

- Frontend: http://localhost:5173
- Backend: http://127.0.0.1:8000
- Interactive API documentation: http://127.0.0.1:8000/docs
- Readiness: http://127.0.0.1:8000/api/health

If PowerShell execution policy blocks scripts, run this invocation:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

An existing MongoDB server is detected automatically. To use another local
installation, set `MONGODB_URI` in `backend/.env` and run `./run.ps1`.

## Configure the LLM

Edit [backend/.env](backend/.env), using [backend/.env.example](backend/.env.example).
Keep all API keys on the backend. Never put keys in frontend variables.

```dotenv
ANTHROPIC_API_KEY=your_anthropic_key
ANTHROPIC_MODEL=your_available_claude_model_id
GEMINI_API_KEY=your_google_key
GEMINI_MODEL=gemini-3.6-flash
```

Claude is tried first when its key and model are both configured. Missing
configuration, SDK errors, and empty responses trigger Gemini. Failure of both
providers returns a useful 503 response. Requests have a configurable 60-second timeout and
SDK retries are disabled. Neither prompts nor raw SDK exceptions are logged.
Gemini 3.6 uses minimal thinking by default for interactive latency and small
translation/audit outputs. Adjust generation.gemini_thinking_level in config.yaml;
when changing Gemini models, choose a thinking level that model supports.
Generation temperature is passed to Gemini and to Anthropic SDK versions that
expose that parameter; current Anthropic SDKs manage sampling without it.
Restart the backend after editing environment variables or config.yaml.

The app can ingest English documents without an API key. Answer generation,
non-English query normalization, and the default evidence audit need an available
LLM. Provider calls can incur charges. Translation and audits use the same fallback.

## Use your documents

1. Open **Knowledge Base**, choose or drop a document, and optionally supply
   its title, organization, original URL, publication date, crop, topic,
   district, and organic-standard applicability.
2. Select **Upload & index**. The progress bar polls the real ingestion job.
3. Wait for `indexed`. A failed file remains in the library with an error and
   can be reindexed after fixing the cause. Its original is retained.
4. Ask a question in English, Devanagari Nepali, Romanized Nepali, or mixed text.
5. Open a source citation to inspect its passage and download the original.

There is no bundled agricultural dataset and no preloaded farming advice.
Upload your official documents manually. Every upload starts **unverified**;
an organization field does not establish authenticity. Unknown source metadata
remains unknown. Without supporting passages, the assistant reports insufficient
evidence instead of supplying general model knowledge.

| Format | Processing |
| --- | --- |
| PDF | PyMuPDF, page metadata; scanned/empty PDFs report that OCR is required |
| TXT / MD | UTF-8 or UTF-16 text |
| HTML / HTM | BeautifulSoup; scripts/styles excluded |
| CSV | Headings are attached to row values |
| JSON / JSONL | Separate records with section metadata |
| XML | defusedxml; external entities rejected |
| XLS / XLSX | xlrd / openpyxl; sheet names and table headings retained |
| DOCX | python-docx; paragraph/table order retained |
| PPTX | python-pptx; slide metadata and table text |
| EPUB | EbookLib; chapter metadata |
| DOC / PPT | Requires LibreOffice; set SOFFICE_PATH if it is not on PATH |

Extensions are case insensitive. The default limit is 50 MB. Structured-file
signatures, archive expansion, unsafe paths, and macro-bearing modern Office
archives are checked. Legacy files are converted with a separate headless
LibreOffice profile. No uploaded file is served as executable web content.
Complex charts, merged cells, scanned tables, and irregular layouts may require
manual cleanup. OCR is reported as a requirement, not silently simulated.

## Configuration and experiments

[backend/config.yaml](backend/config.yaml) controls chunking, retrieval,
normalization, and guardrails. Defaults are approximately 400 words per chunk,
75-word overlap where sentence boundaries permit, and a 500-word maximum.
Small tables are kept together. Original source text is always preserved.

MPNet is English oriented. Nepali/mixed documents require
`translation.translate_documents: true`; otherwise ingestion returns an
actionable error instead of silently embedding them as English. This defaults
to false because translating books may be expensive. Queries are normalized
by default. Language detection and the scope classifier are lightweight
heuristics and can misclassify unfamiliar wording.

| Experiment | Configuration |
| --- | --- |
| BM25 only | retrieval.mode: bm25; rerank_enabled: false |
| FAISS only | retrieval.mode: dense; rerank_enabled: false |
| Hybrid | retrieval.mode: hybrid; rerank_enabled: false |
| Hybrid + reranking | retrieval.mode: hybrid; rerank_enabled: true |
| Multilingual normalization | translation.enabled and normalize_to_english |
| Context and guardrails | request filters and guardrails flags |

`rerank_input_limit` caps the merged candidate pool sent to the cross-encoder.
It is an efficiency control, adjustable for ablation studies. The defaults
retrieve up to 1000 candidates per retriever, rerank 200, retain 50, and send
up to 8 to the LLM. Thresholds should be evaluated on your dataset.

Chat requests accept exact metadata filters for `crop`, `topic`,
`source_organization`, `publication_date`, `district`, and `organic_standard`.
Only explicitly supplied metadata participates. Response metadata contains
selected chunk IDs and scores, model names, settings, dataset version, and latency
for later Recall@K, MRR/nDCG, citation, and language evaluations. Conversation
history lives in the browser session and is sent as context; it is not stored
in MongoDB. Questions and document text are excluded from application logs.

The output guard checks citation IDs and script deterministically. By default,
an additional LLM audit checks source support, requested language, topicality,
and organic-compliance conflicts. Invalid or negative audits return insufficient
evidence. These checks reduce errors; they do not establish scientific correctness.

## Persistence and recovery

- Originals: `data/raw`; processed original/normalized chunks: `data/processed`.
- MongoDB: documents, chunks, ingestion_jobs collections; FAISS is the vector store.
- The project-local MongoDB server persists data in `.runtime/mongo-data`.
  An existing MongoDB installation uses its own configured data directory.
- FAISS snapshots have checksums and a stable vector-position/chunk-ID mapping.
  An atomic manifest selects a complete index generation. Unchanged vectors
  are reused, including across restarts.
- Documents become indexed only after their chunks and vector manifest commit.
  Interrupted jobs become failed on restart. Reindex them from the library.
- Query-time reconciliation excludes failed/deleted chunks and rebuilds a stale
  or damaged index from MongoDB records when needed.
- Stop the backend before a manual full rebuild:

```powershell
.\.venv\Scripts\python.exe scripts\rebuild_index.py
```

Use **one backend worker**. A process-local lock serializes mutations and retrieval
snapshots. Do not run concurrent backend instances or the rebuild script against
the same database/index. This is a localhost research prototype without login.

## Validation

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm test
npm run build
```

Optional desktop/mobile browser checks using installed Microsoft Edge:
`npm run test:e2e` from frontend. Screenshots are written under `.runtime`.

Backend tests use a deterministic test-only embedder, LLM fixture, mongomock,
and real FAISS. They test parsing, malformed uploads, safe XML, chunking,
deduplication, lifecycle, persistence, corruption recovery, metadata filters,
languages, guardrails, and provider fallback without paid requests.
Frontend tests exercise real request construction and failure presentation.
Test fixtures are explicitly synthetic and are never loaded as project data.

To download and check the real production models before uploading a document:

```powershell
.\.venv\Scripts\python.exe scripts\prefetch_models.py
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the data flow and API contract.

## Troubleshooting

- **MongoDB unavailable:** run `./run.ps1` to start the included local server,
  or start your existing MongoDB installation and correct MONGODB_URI.
  Health reports a degraded state until it connects.
- **Missing model/key:** fill backend/.env; use the precise model ID available
  to the relevant account. Gemini defaults to gemini-3.6-flash.
- **Model download failure:** check internet access. Weights are cached under
  `.runtime/models`; reindex the failed upload after connectivity is restored.
- **Legacy parser unavailable:** install LibreOffice and set its executable
  path in SOFFICE_PATH. No conversion is reported as successful when unavailable.
- **Port already in use:** stop the existing app on 8000/5173 before launching.
- **Logs:** `.runtime/backend.err.log`, `.runtime/frontend.err.log`,
  `.runtime/mongo.log`, and `backend/logs/application.log`.

Relevant upstream documentation: [MongoDB ZIP installation](https://www.mongodb.com/docs/v8.0/tutorial/install-mongodb-on-windows-zip/),
[Sentence Transformers](https://sbert.net/),
[Google GenAI SDK](https://googleapis.github.io/python-genai/),
[Gemini 3.6 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash).
