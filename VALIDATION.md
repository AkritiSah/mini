# Validation — 14 November 2026

Project location: D:\mini. Windows, Python 3.12.4, Node 22.13.0.

| Check | Result |
| --- | --- |
| Backend pytest suite | 27 passed |
| Frontend Vitest workflow tests | 3 passed |
| Playwright desktop/mobile checks in Edge | 2 passed |
| Vite production build | Passed |
| Dependency consistency (pip check) | Passed |
| PowerShell launcher syntax | Passed |
| run.ps1 -SmokeTest | Passed; real local MongoDB, backend, frontend, shutdown |
| Production MPNet | 768-dimensional normalized embeddings verified |
| Production cross-encoder | Real passage reranking verified |
| Live Gemini fallback | gemini-3.6-flash verified |
| Real document lifecycle | Ingestion, reindex, restart persistence, deletion passed |

The real-system check used the [ICAR-IISR Ginger pamphlet](https://www.spices.res.in/storage/app/public/pdfs/GINGER/2ENG.pdf)
in a newly generated temporary MongoDB database. The official PDF produced 16
MPNet/FAISS vectors. Hybrid retrieval and real cross-encoder reranking succeeded.
English, Nepali, and Romanized Nepali answers passed citation checks and the
semantic evidence audit through Gemini 3.6 Flash. An unrelated programming query
was refused. Reindexing succeeded. Restart loaded the saved vectors without
loading MPNet, and deleting the document removed its chunks and vectors.
The temporary database and extracted validation source records were removed.
No validation documents were added to the user's normal knowledge base.

The installed Anthropic SDK removed its temperature argument. The adapter handles
that API difference, and an offline test uses the real SDK's serializer and a
mock HTTP transport to verify requests. A live Claude request then reached a
connection error in this environment. Successful live Claude generation remains
unverified here; provider failure correctly invokes the verified Gemini fallback.

Browser checks covered both pages, navigation, example-question selection,
upload initial state, JavaScript errors, and horizontal overflow at 1440px and
390px widths. Screenshots are under .runtime. Browser tests do not replace
multilingual field evaluation with farmers or scientific review of source material.

Run commands are in README.md. Detailed real-system results for this run are in
.runtime/system-check.json. Live validation intentionally uses API credits.
