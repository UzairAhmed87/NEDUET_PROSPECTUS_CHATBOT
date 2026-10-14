#!/usr/bin/env python3
"""Evaluate retrieval, citations, answer facts, refusals, and latency separately.

Modes:
  retrieval  - retrieval only (no LLM calls); fast, used to compare index configurations.
  full       - retrieval + generation through the production AnswerService.

All rates are measured on the manually constructed cases in the eval file and apply
only to the configured corpus, index, and providers. They are not official accuracy claims.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

HIT_KS = (1, 3, 5, 10)
_PAGE_REF = re.compile(r"\bpages?\s*\d+(?:\s*(?:,|and|-|–)\s*\d+)*", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?")
_OCR_ZERO = re.compile(r"(?<=[\d,])[oO](?=[\d,oO/%\-]|\b)")


def normalize_numbers(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = _OCR_ZERO.sub("0", text)
    return re.sub(r"(?<=\d),(?=\d{3})", "", text)


def normalize(text: str) -> str:
    return " ".join(normalize_numbers(text).lower().split())


def fact_present(fact: str, answer_norm: str) -> bool:
    needle = normalize(fact)
    if re.fullmatch(r"[\d.]+%?", needle):
        return re.search(rf"(?<![\d.]){re.escape(needle)}(?![\d])", answer_norm) is not None
    return needle in answer_norm


def numeric_claims(answer: str) -> list[str]:
    stripped = _PAGE_REF.sub(" ", answer)
    claims = []
    for match in _NUMBER.finditer(stripped):
        token = normalize_numbers(match.group(0)).rstrip(".,")
        digits = token.rstrip("%")
        if not digits:
            continue
        if token.endswith("%") or len(digits.replace(".", "")) >= 3 or "." in digits:
            claims.append(token)
    return claims


def claim_supported(claim: str, evidence_norm: str) -> bool:
    return re.search(rf"(?<![\d.]){re.escape(claim)}(?![\d])", evidence_norm) is not None


def build_services(chroma_dir: Path | None, top_k: int | None, max_distance: float | None):
    from app.core.config import get_settings
    from app.providers.embeddings import build_embedding_provider
    from app.providers.generation import build_generation_provider
    from app.repositories.vector_store import ChromaVectorStore
    from app.services.answer_service import AnswerService
    from app.services.conversation_store import ConversationStore
    from app.services.embedding_service import EmbeddingService
    from app.services.retrieval_service import RetrievalService

    updates: dict = {}
    if chroma_dir is not None:
        updates["chroma_dir"] = chroma_dir
    if top_k is not None:
        updates["retrieval_top_k"] = top_k
    if max_distance is not None:
        updates["retrieval_max_distance"] = max_distance
    settings = get_settings().model_copy(update=updates)
    store = ChromaVectorStore(settings.chroma_dir, settings.chroma_collection)
    retrieval = RetrievalService(settings, EmbeddingService(build_embedding_provider(settings)), store)
    return settings, store, retrieval, lambda: AnswerService(
        retrieval, build_generation_provider(settings), ConversationStore()
    )


def chunk_lookup(store, chunk_ids: list[str]) -> dict[str, dict]:
    if not chunk_ids:
        return {}
    data = store._collection.get(ids=chunk_ids, include=["documents", "metadatas"])
    return {
        cid: {"text": text or "", "metadata": meta or {}}
        for cid, text, meta in zip(data["ids"], data["documents"], data["metadatas"])
    }


def score_retrieval(case: dict, retrieved) -> dict:
    expected = set(case.get("expected_pages") or [])
    ranked_pages = [hit.page_number for hit in retrieved.hits]
    accepted_pages = sorted({hit.page_number for hit in retrieved.accepted})
    row = {
        "ranked_pages": ranked_pages[:12],
        "accepted_pages": accepted_pages,
        "best_distance": round(min((h.distance for h in retrieved.hits), default=1.0), 4),
        "gate_refused": bool(retrieved.insufficient_evidence),
    }
    for k in HIT_KS:
        row[f"hit@{k}"] = bool(expected & set(ranked_pages[:k])) if expected else None
    row["expected_page_in_context"] = bool(expected & set(accepted_pages)) if expected else None
    return row


def score_answer(case: dict, chat: dict, store) -> dict:
    should_refuse = bool(case.get("should_refuse", case.get("expect_refusal")))
    expected = set(case.get("expected_pages") or [])
    refused = bool(chat.get("insufficient_evidence"))
    answer = chat.get("answer") or ""
    answer_norm = normalize(answer)
    citations = chat.get("citations") or []

    stored = chunk_lookup(store, [c["chunk_id"] for c in citations])
    invalid = [
        c["chunk_id"]
        for c in citations
        if c["chunk_id"] not in stored
        or int(stored[c["chunk_id"]]["metadata"].get("page_number") or -1) != int(c["page_number"])
        or str(stored[c["chunk_id"]]["metadata"].get("document_id") or "") != c["document_id"]
    ]
    evidence_norm = normalize(" ".join(item["text"] for item in stored.values()))
    claims = [] if refused else numeric_claims(answer)
    unsupported_claims = [claim for claim in claims if not claim_supported(claim, evidence_norm)]
    cited_pages = sorted({int(c["page_number"]) for c in citations})

    missing_facts = [
        group[0]
        for group in case.get("key_facts") or []
        if not any(fact_present(alt, answer_norm) for alt in group)
    ]
    forbidden_hits = [fact for fact in case.get("forbidden_facts") or [] if fact_present(fact, answer_norm)]

    answered = not refused
    correct = (
        refused if should_refuse else answered and not missing_facts and not forbidden_hits
    )
    unsupported = answered and (should_refuse or bool(forbidden_hits) or bool(unsupported_claims))
    citation_claim_ok = None
    if answered and citations:
        page_ok = (not expected) or bool(expected & set(cited_pages))
        citation_claim_ok = page_ok and not unsupported_claims
    return {
        "refused": refused,
        "refusal_ok": refused == should_refuse,
        "false_refusal": refused and not should_refuse,
        "correct": correct,
        "unsupported": unsupported,
        "citation_valid": (not invalid) if citations else None,
        "citation_claim_ok": citation_claim_ok,
        "cited_pages": cited_pages,
        "missing_facts": missing_facts,
        "forbidden_hits": forbidden_hits,
        "unsupported_numbers": unsupported_claims,
        "limitation": chat.get("limitation"),
        "answer": answer,
    }


def _rate(rows: list[dict], key: str) -> dict:
    values = [row[key] for row in rows if row.get(key) is not None]
    if not values:
        return {"rate": None, "n": 0}
    return {"rate": round(sum(1 for v in values if v) / len(values), 4), "n": len(values)}


def summarize(rows: list[dict], mode: str) -> dict:
    answerable = [r for r in rows if not r["should_refuse"]]
    refusal_cases = [r for r in rows if r["should_refuse"]]
    summary: dict = {"cases": len(rows), "answerable": len(answerable), "refusal_cases": len(refusal_cases)}
    for k in HIT_KS:
        summary[f"hit@{k}"] = _rate(answerable, f"hit@{k}")
    summary["expected_page_in_context"] = _rate(answerable, "expected_page_in_context")
    summary["gate_refusal_on_answerable"] = _rate(answerable, "gate_refused")
    summary["gate_refusal_on_refusal_cases"] = _rate(refusal_cases, "gate_refused")
    if mode == "full":
        answered = [r for r in rows if not r["refused"]]
        summary["correct_answer_rate_answerable"] = _rate(answerable, "correct")
        summary["false_refusal_rate"] = _rate(answerable, "false_refusal")
        summary["refusal_correct_on_refusal_cases"] = _rate(refusal_cases, "refusal_ok")
        summary["unsupported_answer_rate_of_answered"] = _rate(answered, "unsupported")
        summary["citation_validity"] = _rate(rows, "citation_valid")
        summary["citation_to_claim_correctness"] = _rate(rows, "citation_claim_ok")
        summary["errors"] = sum(1 for r in rows if r.get("error"))
    latencies = [r["latency_s"] for r in rows if r.get("latency_s") is not None]
    if latencies:
        ordered = sorted(latencies)
        summary["latency_s"] = {
            "mean": round(statistics.mean(ordered), 2),
            "p50": round(ordered[len(ordered) // 2], 2),
            "p90": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))], 2),
            "max": round(ordered[-1], 2),
        }
    by_category: dict[str, dict] = {}
    for row in answerable:
        bucket = by_category.setdefault(row["category"], {"n": 0, "context_hit": 0, "correct": 0})
        bucket["n"] += 1
        bucket["context_hit"] += 1 if row.get("expected_page_in_context") else 0
        bucket["correct"] += 1 if row.get("correct") else 0
    summary["by_category"] = by_category
    return summary


def run(args) -> dict:
    payload = json.loads(args.eval_file.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    if args.ids:
        wanted = set(args.ids.split(","))
        cases = [c for c in cases if c.get("id") in wanted]
    settings, store, retrieval, make_answers = build_services(args.chroma_dir, args.top_k, args.max_distance)
    answers = make_answers() if args.mode == "full" else None
    rows = []
    for index, case in enumerate(cases):
        row = {
            "id": case.get("id"),
            "category": case.get("category", ""),
            "language": case.get("language", "en"),
            "should_refuse": bool(case.get("should_refuse", case.get("expect_refusal"))),
            "expected_pages": case.get("expected_pages") or [],
        }
        started = time.perf_counter()
        retrieved = retrieval.retrieve(case["question"])
        row["retrieval_latency_s"] = round(time.perf_counter() - started, 3)
        row.update(score_retrieval(case, retrieved))
        if answers is not None:
            if index and args.delay:
                time.sleep(args.delay)
            started = time.perf_counter()
            try:
                response = answers.answer(case["question"]).model_dump()
                row.update(score_answer(case, response, store))
            except Exception as exc:  # recorded as a failure, never hidden
                row.update({"error": f"{type(exc).__name__}: {exc}", "refused": True, "refusal_ok": False,
                            "false_refusal": not row["should_refuse"], "correct": False, "unsupported": False,
                            "citation_valid": None, "citation_claim_ok": None})
            row["latency_s"] = round(time.perf_counter() - started, 3)
        rows.append(row)
        print(_case_line(row, args.mode), flush=True)
    return {
        "label": args.label,
        "mode": args.mode,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "eval_file": str(args.eval_file.relative_to(ROOT)) if args.eval_file.is_relative_to(ROOT) else str(args.eval_file),
        "config": {
            "chroma_dir": str(settings.chroma_dir),
            "embedding_model": settings.embedding_model,
            "generation_provider": settings.generation_provider,
            "groq_model": settings.groq_model if args.mode == "full" else None,
            "retrieval_top_k": settings.retrieval_top_k,
            "retrieval_max_distance": settings.retrieval_max_distance,
            "index_chunks": store.count(),
        },
        "summary": summarize(rows, args.mode),
        "rows": rows,
    }


def _case_line(row: dict, mode: str) -> str:
    parts = [f"{row['id']:<22}", f"ctx={'ok' if row.get('expected_page_in_context') else ('-' if row['should_refuse'] else 'MISS')}",
             f"d={row['best_distance']}", f"gate={'refuse' if row['gate_refused'] else 'pass'}"]
    if mode == "full":
        parts.append(f"correct={'ok' if row.get('correct') else 'FAIL'}")
        if row.get("missing_facts"):
            parts.append(f"missing={row['missing_facts']}")
        if row.get("unsupported_numbers"):
            parts.append(f"unsupported_nums={row['unsupported_numbers']}")
        if row.get("error"):
            parts.append(f"error={row['error'][:80]}")
        parts.append(f"{row.get('latency_s', 0):.1f}s")
    return "  " + " ".join(parts).encode("ascii", "replace").decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--eval-file", type=Path, default=ROOT / "data" / "eval" / "questions_2025.json")
    parser.add_argument("--mode", choices=("retrieval", "full"), default="retrieval")
    parser.add_argument("--chroma-dir", type=Path, help="Evaluate a different index directory")
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--max-distance", type=float)
    parser.add_argument("--ids", help="Comma-separated case ids to run")
    parser.add_argument("--delay", type=float, default=0.0, help="Seconds between LLM calls (rate limits)")
    parser.add_argument("--label", default="run")
    parser.add_argument("--out", type=Path, help="Write the full JSON report here")
    args = parser.parse_args()

    report = run(args)
    print(json.dumps(report["summary"], indent=2))
    print("\nRates are measured on manually constructed cases only; they are not official accuracy claims.")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Report written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
