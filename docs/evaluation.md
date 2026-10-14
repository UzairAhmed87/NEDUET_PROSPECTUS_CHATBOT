# Evaluation — NED Prospectus Assistant

This document describes **how** retrieval, citations, and refusals are measured. It does not report fabricated accuracy percentages.

## What is scored

The script `scripts/evaluate_retrieval.py` reads a JSON file of cases and reports three independent rates:

1. **Retrieval relevance** — did any returned chunk include an expected page number (or was retrieval correctly empty for refusal cases)?
2. **Citation correctness** — did every citation in the answer refer to a retrieved chunk ID, and did cited pages intersect the expected pages?
3. **Refusal behavior** — did `insufficient_evidence` match the case’s `expect_refusal` flag?

These are counted separately. A high refusal rate with a low citation rate is a meaningful failure, not a single blended “accuracy.”

## Fixture used in automated tests

Pytest builds a small **test-fixture PDF** at runtime. It is labelled inside the file as a test fixture, not an official NED prospectus. Official fees, deadlines, and merit figures are not copied from the university.

The fixture exists so extraction, chunking, hashing, retrieval wiring, citation validation, and adversarial grounding can run without credentials or copyrighted PDFs.

## Default threshold

`RETRIEVAL_MAX_DISTANCE=0.72` (cosine distance on Chroma) is the cutoff exercised against the fixture with the **fake** embedding provider. Distances from local MiniLM embeddings on a real prospectus will differ. Recalibrate after ingesting an official PDF. Default `RETRIEVAL_TOP_K` is 12; retrieval also expands a small glossary and packs same-page chunks so fee tables and faculty lists are less likely to sit just outside the prompt.

## Case file format

See `data/eval/questions.json`:

```json
{
  "cases": [
    {
      "id": "programs-page-1",
      "question": "Which undergraduate programs are listed?",
      "expected_pages": [1],
      "expect_refusal": false
    },
    {
      "id": "off-topic",
      "question": "What is the capital of France?",
      "expected_pages": [],
      "expect_refusal": true
    }
  ]
}
```

## Running evaluation

From the repository root, with the API dependencies installed and a corpus indexed:

```bash
python scripts/evaluate_retrieval.py --eval-file data/eval/questions.json
```

Against a running API (optional live generation):

```bash
python scripts/evaluate_retrieval.py --eval-file data/eval/questions.json --base-url http://127.0.0.1:8000
```

Do not publish a percentage in README or UI unless this script produced it on the stated corpus and model.

## Known evaluation gaps

- Scanned / image-only pages need OCR; they will look like missing evidence.
- Tables may extract in confusing reading order; page hits can be right while the answer is weakly grounded.
- Multi-document contradictions are only as good as the operator ingesting distinct versions with `document_version` set.
