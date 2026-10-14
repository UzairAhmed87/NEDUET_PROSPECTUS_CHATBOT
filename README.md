# NED Prospectus Assistant

A grounded retrieval-augmented generation (RAG) assistant that answers questions **only** from official NED University of Engineering & Technology prospectus PDFs you ingest. It does not invent fees, deadlines, eligibility rules, or policies. If retrieved evidence is weak or missing, it refuses.

This repository shipped **without** an official prospectus and **without** API credentials. Until you add both, the chat UI can run against an empty corpus (and will refuse), and tests use a synthetic fixture PDF plus fake embedding/generation providers.

## Architecture

- **`apps/web`** — Next.js App Router UI. Calls FastAPI. Never holds the Groq key.
- **`apps/api`** — FastAPI RAG service: PyMuPDF extraction, paragraph-aware chunking, local MiniLM embeddings, ChromaDB, Groq generation (or fake providers for tests).
- **`scripts/`** — CLI ingest and evaluation.
- **`data/documents/`** — place official PDFs here (gitignored contents).
- **`data/chroma/`** — persistent vector store (gitignored contents).

See `docs/architecture.md`, `docs/implementation-plan.md`, and `docs/decisions.md`.

## Requirements

- Python 3.11–3.14 (ChromaDB currently needs `onnxruntime` wheels; Python 3.15 is not usable on this machine)
- Node.js 20+
- A [Groq API key](https://console.groq.com/keys) for grounded answer generation
- An official NED prospectus PDF that **you** obtain from the university (not included)

Docker is optional and not required.

## Setup

```bash
copy .env.example .env
```

On macOS/Linux use `cp .env.example .env`. Set at least:

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Groq grounded generation (server-side only) |
| `GROQ_MODEL` | Groq chat model id (default `openai/gpt-oss-20b`, verified on Groq) |
| `ADMIN_API_KEY` | Protects ingest and retrieval-debug |
| `CORS_ORIGINS` | Explicit browser origins (default localhost) |
| `NEXT_PUBLIC_API_URL` | Frontend → API (also copy into `apps/web/.env.local`) |

```bash
copy apps\web\.env.example apps\web\.env.local
```

Install:

```bash
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r apps/api/requirements.txt

npm --prefix apps/web install
```

## Ingest a prospectus

1. Obtain the official PDF yourself. Do not commit it.
2. Save it under `data/documents/`, for example `data/documents/ned-undergraduate-prospectus.pdf`.
3. Ingest:

```bash
python scripts/ingest_documents.py data/documents/ned-undergraduate-prospectus.pdf --title "Undergraduate Prospectus" --year 2024-25
```

Add `--verified` only if you have confirmed the file against an official NED source. Without that flag the UI will not describe the file as the latest official prospectus.

Re-index the same bytes:

```bash
python scripts/ingest_documents.py data/documents/ned-undergraduate-prospectus.pdf --replace --title "Undergraduate Prospectus" --year 2024-25
```

You can also ingest from `http://localhost:3000/admin` with `X-Admin-Key`.

## Run locally

Terminal 1 — API:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --app-dir apps/api
```

Terminal 2 — UI:

```bash
npm --prefix apps/web run dev
```

Open `http://localhost:3000`.

API reference (also in OpenAPI at `http://127.0.0.1:8000/docs`):

| Method | Path | Auth |
| --- | --- | --- |
| GET | `/api/v1/health` | public |
| GET | `/api/v1/documents` | public |
| POST | `/api/v1/documents/ingest` | `X-Admin-Key` |
| POST | `/api/v1/chat` | public (rate limited) |
| POST | `/api/v1/retrieval/debug` | `X-Admin-Key` |

## RAG knobs

| Setting | Default | Notes |
| --- | --- | --- |
| `CHUNK_SIZE_CHARS` | 1200 | Paragraph-aware target size |
| `CHUNK_OVERLAP_CHARS` | 200 | Boundary overlap |
| `RETRIEVAL_TOP_K` | 12 | Neighbors requested from Chroma after lexical rerank |
| `RETRIEVAL_MAX_DISTANCE` | 0.72 | Cosine **distance** cutoff (lower is closer). Calibrated on the fixture + fake embeddings; recalibrate on a real prospectus. |
| `EMBEDDING_PROVIDER` | `local` | ONNX `all-MiniLM-L6-v2` for both index and query. Use `fake` only for tests |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | 384-d; must match the space used at ingest time |
| `GENERATION_PROVIDER` | `groq` | Use `fake` only for tests |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Read from env. Verified live on Groq; `openai/gpt-oss-120b` also works |
| `GROQ_MAX_COMPLETION_TOKENS` | 4096 | Includes hidden reasoning tokens; too low truncates the JSON answer |
| `GROQ_REASONING_EFFORT` | `low` | Sent to reasoning models such as gpt-oss; leave empty for models that reject it |

## Tests and lint

```bash
python -m pytest apps/api/tests -q
npm --prefix apps/web test
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
```

Pytest uses a **synthetic fixture PDF** and fake providers. It does not call Groq unless you set `GENERATION_PROVIDER=groq` with a real `GROQ_API_KEY`.

Evaluation (after a corpus is indexed):

```bash
python scripts/evaluate_retrieval.py --eval-file data/eval/questions.json
```

Do not quote an accuracy percentage that this script did not produce on the stated corpus.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| UI: cannot reach the API | API on port 8000, `NEXT_PUBLIC_API_URL`, CORS origins |
| `PROVIDER_NOT_CONFIGURED` | `GROQ_API_KEY` when `GENERATION_PROVIDER=groq` |
| Duplicate ingest 409 | Same file hash; pass `--replace` or `replace=true` |
| Image-only / empty pages | Scanned pages are OCR’d automatically; remaining empty pages are flagged |
| Weak or empty answers | Scanned PDFs need OCR; fee/department questions should retrieve campus-wide figures even when a department-specific line is missing. Raise `RETRIEVAL_TOP_K` if lists are truncated. Recalibrate `RETRIEVAL_MAX_DISTANCE` only after evaluation |
| Admin 401 | `ADMIN_API_KEY` in `.env` must not remain the placeholder, and the header must match |
| Quota / 502 | Groq rate limits, timeouts, or invalid key; keys are never returned to the browser |

## Known limitations

- Scanned pages are OCR’d with RapidOCR (ONNX). Layout, tables, and small print may be imperfect.
- Tables and multi-column layouts may extract in awkward reading order.
- Cosine threshold `0.72` was calibrated on the synthetic fixture with fake embeddings. Recalibrate after indexing a real prospectus with local MiniLM embeddings.
- Conversation history is in-memory continuity only and is discarded on process restart. It is never used as evidence.
- Prompt injection cannot be eliminated. Passages are untrusted and citations are validated; residual risk remains.
- The assistant is not an official university decision.

## Security

Secrets live in environment variables. Do not commit `.env`, uploaded PDFs, or `data/chroma` contents. Ingest and retrieval-debug require an admin key. CORS is an allow-list.
