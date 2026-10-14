from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings
from app.repositories.vector_store import ChromaVectorStore, VectorHit
from app.schemas.retrieval import RetrievedChunk
from app.services.embedding_service import EmbeddingService
from app.services.lexical_index import reciprocal_rank_fusion
from app.utils.query import expand_retrieval_query, lexical_overlap
from app.utils.text import excerpt

MAX_PACKED_CHUNKS = 14
CHAPTER_NEIGHBOR_CHARS = 320
LEXICAL_DISTANCE_BONUS = 0.4
PRIMARY_PACK_HITS = 4


REFUSAL_NO_PASSAGES = "no_relevant_passages"
REFUSAL_WEAK_EVIDENCE = "weak_evidence"
COVERAGE_PASSAGES = 5


@dataclass
class RetrievalResult:
    hits: list[RetrievedChunk]
    accepted: list[RetrievedChunk]
    insufficient_evidence: bool
    refusal_reason: str | None = None
    signals: dict = field(default_factory=dict)


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        embedding_service: EmbeddingService,
        vector_store: ChromaVectorStore,
    ) -> None:
        self.settings = settings
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def retrieve(
        self,
        question: str,
        *,
        top_k: int | None = None,
        document_ids: list[str] | None = None,
        academic_year: str | None = None,
    ) -> RetrievalResult:
        k = top_k or self.settings.retrieval_top_k
        search_text = expand_retrieval_query(question)
        candidate_k = min(32, max(k * 3, k))
        embedding = self.embedding_service.embed_query(search_text)
        raw_hits = self.vector_store.query(
            embedding,
            top_k=candidate_k,
            document_ids=document_ids,
            academic_year=academic_year,
        )
        max_distance = self.settings.retrieval_max_distance
        if self.settings.retrieval_mode == "hybrid":
            ranked = self._hybrid_rank(
                raw_hits, embedding, search_text, candidate_k, document_ids, academic_year
            )
        else:
            ranked = rerank_hits([_to_retrieved(hit, max_distance) for hit in raw_hits], search_text)
        selected = ranked[:k]
        packed = self._pack_related_pages(selected)
        accepted = [hit for hit in packed if hit.within_threshold]
        signals = self._answerability_signals(question, selected)
        reason = self._refusal_reason(accepted, signals)
        return RetrievalResult(
            hits=packed,
            accepted=[] if reason else accepted,
            insufficient_evidence=reason is not None,
            refusal_reason=reason,
            signals=signals,
        )

    def _hybrid_rank(
        self,
        raw_hits: list[VectorHit],
        embedding: list[float],
        search_text: str,
        candidate_k: int,
        document_ids: list[str] | None,
        academic_year: str | None,
    ) -> list[RetrievedChunk]:
        lexical = self.vector_store.lexical_index().search(
            search_text, top_n=candidate_k, document_ids=document_ids, academic_year=academic_year
        )
        by_id = {hit.chunk_id: hit for hit in raw_hits}
        missing = [hit.chunk_id for hit in lexical if hit.chunk_id not in by_id]
        for hit in self.vector_store.get_with_distances(missing, embedding):
            by_id[hit.chunk_id] = hit
        fused = reciprocal_rank_fusion(
            [[hit.chunk_id for hit in raw_hits], [hit.chunk_id for hit in lexical]],
            k=self.settings.retrieval_rrf_k,
        )
        max_distance = self.settings.retrieval_max_distance
        return [_to_retrieved(by_id[chunk_id], max_distance) for chunk_id, _score in fused if chunk_id in by_id]

    def _answerability_signals(self, question: str, selected: list[RetrievedChunk]) -> dict:
        within = [hit for hit in selected if hit.within_threshold]
        best_distance = min((hit.distance for hit in selected), default=1.0)
        coverage = 0.0
        if within:
            index = self.vector_store.lexical_index()
            coverage = max(index.weighted_coverage(question, hit.text) for hit in within[:COVERAGE_PASSAGES])
        return {"best_distance": round(best_distance, 4), "lexical_coverage": round(coverage, 4)}

    def _refusal_reason(self, accepted: list[RetrievedChunk], signals: dict) -> str | None:
        if not accepted:
            return REFUSAL_NO_PASSAGES
        strict = self.settings.retrieval_strict_distance
        if (
            strict is not None
            and signals["best_distance"] > strict
            and signals["lexical_coverage"] < self.settings.retrieval_min_coverage
        ):
            return REFUSAL_WEAK_EVIDENCE
        return None

    def _pack_related_pages(self, selected: list[RetrievedChunk]) -> list[RetrievedChunk]:
        pages = pages_to_pack(selected, primary=PRIMARY_PACK_HITS)
        document_ids = [hit.document_id for hit in selected if hit.document_id]
        if not pages or not document_ids:
            return selected
        extras = self.vector_store.get_by_pages(document_ids, sorted(pages))
        page_distance = distances_for_packed_pages(selected, pages)
        extra_chunks = [
            _to_retrieved(
                VectorHit(
                    chunk_id=hit.chunk_id,
                    text=hit.text,
                    distance=page_distance.get(int(hit.metadata.get("page_number") or 0), hit.distance),
                    metadata=hit.metadata,
                ),
                self.settings.retrieval_max_distance,
            )
            for hit in extras
        ]
        return merge_packed_chunks(selected, extra_chunks, cap=MAX_PACKED_CHUNKS)


def rerank_hits(hits: list[RetrievedChunk], query: str) -> list[RetrievedChunk]:
    def sort_key(hit: RetrievedChunk) -> tuple[float, float]:
        overlap = lexical_overlap(query, hit.text)
        adjusted = hit.distance - (LEXICAL_DISTANCE_BONUS * overlap)
        return (adjusted, hit.distance)

    return sorted(hits, key=sort_key)


def pages_to_pack(hits: list[RetrievedChunk], *, primary: int = PRIMARY_PACK_HITS) -> set[int]:
    pages: set[int] = set()
    for hit in hits[:primary]:
        if not hit.within_threshold or hit.page_number <= 0:
            continue
        pages.add(hit.page_number)
    for hit in hits:
        if not hit.within_threshold or hit.page_number <= 0:
            continue
        compact = " ".join(hit.text.split())
        if len(compact) < CHAPTER_NEIGHBOR_CHARS and "chapter" in compact.lower():
            pages.add(hit.page_number)
            pages.add(hit.page_number + 1)
            if hit.page_number > 1:
                pages.add(hit.page_number - 1)
    return pages


def merge_packed_chunks(
    selected: list[RetrievedChunk],
    extras: list[RetrievedChunk],
    *,
    cap: int,
) -> list[RetrievedChunk]:
    merged: list[RetrievedChunk] = []
    seen: set[str] = set()
    for hit in [*selected, *extras]:
        if hit.chunk_id in seen:
            continue
        seen.add(hit.chunk_id)
        merged.append(hit)
        if len(merged) >= cap:
            break
    return merged


def distances_for_packed_pages(hits: list[RetrievedChunk], pages: set[int]) -> dict[int, float]:
    best: dict[int, float] = {}
    for hit in hits:
        current = best.get(hit.page_number)
        if current is None or hit.distance < current:
            best[hit.page_number] = hit.distance
    for hit in hits:
        compact = " ".join(hit.text.split())
        if len(compact) >= CHAPTER_NEIGHBOR_CHARS or "chapter" not in compact.lower():
            continue
        for neighbor in (hit.page_number - 1, hit.page_number + 1):
            if neighbor in pages and neighbor not in best:
                best[neighbor] = hit.distance
    return best


def _to_retrieved(hit: VectorHit, max_distance: float) -> RetrievedChunk:
    metadata = hit.metadata
    return RetrievedChunk(
        chunk_id=hit.chunk_id,
        document_id=str(metadata.get("document_id") or ""),
        document_title=str(metadata.get("document_title") or "Untitled document"),
        document_version=str(metadata.get("document_version") or "") or None,
        source_filename=str(metadata.get("source_filename") or ""),
        page_number=int(metadata.get("page_number") or 0),
        excerpt=excerpt(hit.text),
        distance=hit.distance,
        text=hit.text,
        within_threshold=hit.distance <= max_distance,
    )
