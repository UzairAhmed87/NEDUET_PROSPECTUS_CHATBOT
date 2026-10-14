# Implementation Plan — NED Prospectus Assistant

## Status of the existing repository

The workspace at `D:\RAG-CHATBOT-BUILDER` was empty at inspection: no package manifests, source files, lockfiles, or prospectus PDFs. This project is therefore a greenfield monorepo. There is no prior framework to preserve.

## Product

**NED Prospectus Assistant** answers questions only from official NED University of Engineering & Technology prospectus PDFs that have been ingested into the local vector store. It must refuse when retrieved evidence is insufficient and must never invent fees, deadlines, eligibility rules, or policies.

## Architecture (high level)

Two independently runnable applications:

| App | Stack | Role |
| --- | --- | --- |
| `apps/api` | FastAPI, Pydantic, PyMuPDF, ChromaDB, Groq | Ingestion, retrieval, grounded generation |
| `apps/web` | Next.js App Router, TypeScript, Tailwind | Chat UI, document status, citations |

They communicate over HTTP. The browser never holds the Groq API key. The Next.js app is a client of the FastAPI service; business logic does not live in React components or Next.js route handlers.

```
Browser  →  Next.js UI  →  FastAPI  →  ChromaDB (local)
                                 ↘  Groq (generation only)
```

## Folder structure

The repository follows the requested monorepo layout. Adaptations:

- Provider abstractions live in `apps/api/app/providers/` so embedding and generation backends can change without rewriting services.
- A document registry (`apps/api/app/repositories/document_registry.py`) stores file hashes, titles, and ingestion metadata beside Chroma, because Chroma metadata alone is awkward for duplicate detection and listing.
- Conversation continuity uses an in-memory store. Historical assistant answers are never used as evidence.
- Evaluation fixtures live in `data/eval/`, not in the vector store.

## Data flow

1. **Ingest.** An admin (script or protected API) uploads a PDF. The file is type-checked, size-limited, hashed, and opened with PyMuPDF.
2. **Extract.** Text is taken page by page. Empty or image-only pages are flagged as needing OCR; they are not silently indexed as empty knowledge.
3. **Chunk.** Pages are split on paragraph/sentence boundaries with configurable size and overlap. Each chunk carries document ID, title, version/year, page number, chunk ID, and source filename.
4. **Embed.** Chunks are embedded by the local MiniLM provider (same model for queries). A deterministic fake provider exists for tests.
5. **Store.** Embeddings and metadata persist in ChromaDB. The registry records the file hash so duplicate ingestion is rejected unless replacement is explicit.
6. **Query.** The user question is embedded in the same space. Top-k cosine neighbors are fetched. Chunks below the documented distance threshold are discarded.
7. **Refuse or generate.** If nothing survives the threshold, the API returns `insufficient_evidence` without calling the generator. Otherwise the generator receives wrapped, untrusted passages and must return JSON. Citation IDs are validated against retrieved chunks before the response leaves the server.
8. **Display.** The UI renders the answer as Markdown, with page-linked citations and expandable excerpts from the retrieved chunks.

## Security considerations

- Secrets only via environment variables; `.env` is gitignored.
- CORS allow-list from `CORS_ORIGINS` (no wildcard in production).
- Ingest and retrieval-debug require `X-Admin-Key`.
- Upload path sanitization, PDF-only, size cap.
- Rate limits on chat and admin routes.
- Retrieved prospectus text is treated as untrusted data (prompt-injection resistant wrapping). Residual risk remains: a sufficiently adversarial PDF plus a non-compliant model could still influence wording. Mitigation is refusal-on-low-evidence, citation validation, and adversarial tests — not a claim of elimination.
- Errors returned to the browser are sanitized; stack traces stay in server logs.
- User questions are logged in truncated form only; API keys are never logged.

## Testing strategy

| Layer | Tool | Focus |
| --- | --- | --- |
| Unit | Pytest | Extraction, chunking, hashing, citation validation, retrieval filtering, API validation |
| Integration | Pytest + temp Chroma | Ingest → store → retrieve → grounded response (fake providers by default) |
| Adversarial | Pytest | Off-topic questions, instruction override, fabricated fees/deadlines, injected instructions in passages, contradictions |
| Frontend | Vitest + Testing Library | Composer, citations, empty/error states, API client mapping |
| Types / lint | `tsc --noEmit`, ESLint, ruff if present | Regression |

A synthetic **test-fixture PDF** is generated at test time. It is clearly labelled as a fixture, not an official prospectus. Live Groq tests are optional and skipped without credentials.

The evaluation script (`scripts/evaluate_retrieval.py`) scores retrieval relevance, citation correctness, and refusal separately. It does not invent accuracy percentages.

## Setup requirements

- Python 3.11–3.14 (create the venv with `py -3.14`; Python 3.15 currently lacks `onnxruntime` wheels required by ChromaDB)
- Node.js 20+
- A Groq API key for grounded generation (`GROQ_API_KEY`)
- An admin key for ingest/debug (`ADMIN_API_KEY`)
- The official NED prospectus PDF placed in `data/documents/` (not shipped in this repo)

The application is runnable without Docker. `EMBEDDING_PROVIDER=fake` and `GENERATION_PROVIDER=fake` allow pipeline tests without network credentials; they are not suitable for answering real student questions.

## Missing information and assets (not invented)

1. **Official prospectus PDF** — not present. Operators must supply the authentic file.
2. **Academic year / document version** — unknown until the operator provides it at ingest time. The UI will not claim “latest official prospectus.”
3. **Groq API key** — supplied by the operator via `GROQ_API_KEY`; never committed.
4. **Confirmed production origin list** — default local origins only; production hosts must be set in `CORS_ORIGINS`.
5. **Similarity threshold calibration on real NED PDFs** — the default cosine distance cutoff (`0.72`) was measured on the synthetic fixture with fake embeddings. It must be re-calibrated with `scripts/evaluate_retrieval.py` after a real prospectus is indexed with local MiniLM embeddings.

## Implementation order

1. Repository layout and architecture docs.
2. Backend configuration, schemas, health endpoint.
3. Extraction, chunking, embeddings, persistent indexing.
4. Retrieval service and debug endpoint.
5. Grounded generation, citation validation, refusal.
6. Frontend chat UI.
7. Tests and evaluation harness.
8. README, `.env.example`, verification.
