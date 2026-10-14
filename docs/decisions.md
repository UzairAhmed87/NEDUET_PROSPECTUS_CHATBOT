# Technical Decisions — NED Prospectus Assistant

## Direct RAG implementation, no LangChain

A small, explicit Python pipeline (extract → chunk → embed → retrieve → generate) is easier to test, explain, and constrain than a general orchestration framework. Provider adapters isolate Groq generation and local embeddings so either can be swapped without rewriting retrieval.

**Trade-off:** We reimplement chunking, retries, and prompt assembly. That is acceptable at this scope.

## ChromaDB as the vector store

Chroma provides a persistent, local, cosine-capable store with no extra server process. That matches a university-lab / single-operator deployment.

**Trade-off:** Chroma is not a multi-tenant production search cluster. Metadata filters and cosine HNSW are sufficient for a modest prospectus corpus (one to a few PDFs).

## Groq for generation, local MiniLM for embeddings

Groq is used only for grounded JSON answers (`GROQ_MODEL`). The default `openai/gpt-oss-20b` was confirmed available on Groq at implementation time (JSON object mode succeeded). `openai/gpt-oss-120b` also succeeded. `llama-3.3-70b-versatile` was not present on the live model list for this account, so it is not the default. Groq does not provide embeddings, so indexing and query vectors use the same local ONNX model (`all-MiniLM-L6-v2`, 384 dimensions) via Chroma’s bundled runtime.

Tests must not depend on live credentials. A deterministic hashing embedding and a schema-faithful fake generator cover ingestion, retrieval, citation validation, and refusal.

**Trade-off:** MiniLM quality is weaker than large hosted embedding APIs, but it keeps document and query vectors in one space without a second cloud key.

## Cosine distance threshold (not an invented similarity “accuracy”)

Chroma is configured with `hnsw:space = cosine`. Query results include a **distance** where `0` is identical and `2` is opposite for cosine.

Default: `RETRIEVAL_MAX_DISTANCE=0.72`, `RETRIEVAL_TOP_K=12`.

Query text is expanded with a small prospectus glossary (for example CSIT → computer science and information technology, fee → tuition/fee structure) before embedding. Candidates are lexically reranked, then chunks from the same page (and the next page of a short “CHAPTER” heading) are packed into the prompt. That recovers fee tables and faculty lists that MiniLM ranks just outside a tiny top-k on OCR’d two-column pages.

**Trade-off:** A slightly larger prompt. Cap is 18 chunks. Off-topic questions are still dropped by the cosine threshold before Groq is called.

This value was chosen after retrieval tests against the synthetic fixture PDF using the **fake** embedding provider (see `docs/evaluation.md` and `apps/api/tests`). It is **not** a calibrated threshold for official NED prospectuses or MiniLM embeddings. After ingesting a real document with `EMBEDDING_PROVIDER=local`, run:

```bash
python scripts/evaluate_retrieval.py --eval-file data/eval/questions.json
```

and adjust `RETRIEVAL_MAX_DISTANCE` so off-topic questions refuse while page-anchored questions still retrieve the expected pages.

**Limitation:** Absolute cosine distances shift with embedding model, chunk size, and document language. Do not treat `0.72` as universal.

## Chunk size 1200 characters, overlap 200

Prospectus pages mix dense policy paragraphs and lists. ~1200 characters (roughly 200–300 tokens) keeps a fee table row or eligibility clause intact more often than tiny 200-character windows, without stuffing the full page into the prompt. Overlap of 200 characters reduces boundary misses.

Both values are environment-configurable. Re-evaluate after indexing a real PDF: tables and multi-column layouts may still split poorly because PyMuPDF extraction is reading-order text, not a layout model.

## Paragraph-aware splitting, not token-only windows

Chunks break on blank lines, then sentences, then hard length. This avoids cutting “Eligibility:” from its following sentence when the paragraph fits.

**Trade-off:** A single huge paragraph still gets hard-wrapped. Overlap exists for that case.

## Duplicate detection by SHA-256 of file bytes

Document ID is derived from the hash prefix plus a slug of the original filename. Re-ingesting the identical bytes is rejected unless `replace=true`, which deletes prior chunks for that document ID and writes a new index.

**Trade-off:** A visually identical prospectus exported twice with different bytes (re-scanned, re-exported) is treated as a new document. That is safer than silently merging.

## Refuse before calling the generator when retrieval is empty

If no chunk is within `RETRIEVAL_MAX_DISTANCE`, `AnswerService` returns `insufficient_evidence` immediately. This prevents the model from answering from parametric knowledge when the corpus has nothing relevant.

If retrieval succeeds but the passages do not contain the answer, the prompt requires the model to set `insufficient_evidence: true`. Citation IDs that the model invents are dropped.

## Retrieved passages are untrusted

Passages are wrapped in delimiters and the system prompt forbids following instructions found inside them or in the user question. This mitigates, and does not eliminate, prompt injection.

## Conversation history is continuity only

Optional `conversation_id` stores recent user questions so follow-ups like “and the fees?” can be rewritten with prior user text. Assistant answers from history are **not** passed as evidence and are **not** embedded into the retrieval query as ground truth.

**Trade-off:** In-memory store is lost on process restart. Persistence is unnecessary for a local assistant.

## Admin key for ingest and retrieval debug

There is no multi-user auth system. A shared `ADMIN_API_KEY` compared against `X-Admin-Key` is enough to keep indexing and similarity dumps off the public chat surface.

## Next.js talks to FastAPI directly

No Next.js API proxy. CORS is an explicit origin list. API keys stay on the Python process. `NEXT_PUBLIC_API_URL` is the only browser-visible configuration.

## UI direction

Academic editorial layout (warm paper, ink, crimson accent) rather than a generic AI landing page. Suggested questions are generic *process* prompts (“What does the indexed prospectus say about eligibility?”) plus optional headings extracted at ingest time. They never assert unverified facts such as a merit percentage.

## What we will not claim

- That any ingested file is the latest official prospectus unless the operator supplies a verified year and authenticity note.
- That prompt injection is solved.
- That retrieval accuracy is a measured percentage on official NED documents until `evaluate_retrieval.py` is run against those documents.
