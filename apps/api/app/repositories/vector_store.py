from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.chunking_service import Chunk
from app.services.lexical_index import BM25Index


@dataclass
class VectorHit:
    chunk_id: str
    text: str
    distance: float
    metadata: dict[str, Any]


class ChromaVectorStore:
    def __init__(self, persist_dir: Path, collection_name: str) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )
        self._lexical: BM25Index | None = None
        self._lexical_count = -1

    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings must be the same length.")
        self._collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.text for chunk in chunks],
            metadatas=[_chunk_metadata(chunk) for chunk in chunks],
        )

    def delete_document(self, document_id: str) -> None:
        self._collection.delete(where={"document_id": document_id})

    def query(
        self,
        embedding: list[float],
        *,
        top_k: int,
        document_ids: list[str] | None = None,
        academic_year: str | None = None,
    ) -> list[VectorHit]:
        where = _where_filter(document_ids, academic_year)
        kwargs: dict[str, Any] = {
            "query_embeddings": [embedding],
            "n_results": max(top_k, 1),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        try:
            result = self._collection.query(**kwargs)
        except Exception:
            if self.count() == 0:
                return []
            raise
        ids = (result.get("ids") or [[]])[0]
        if not ids:
            return []
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        hits: list[VectorHit] = []
        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
            hits.append(
                VectorHit(
                    chunk_id=chunk_id,
                    text=text or "",
                    distance=float(distance),
                    metadata=dict(metadata or {}),
                )
            )
        return hits

    def get_by_pages(self, document_ids: list[str], page_numbers: list[int]) -> list[VectorHit]:
        unique_docs = [item for item in dict.fromkeys(document_ids) if item]
        unique_pages = [page for page in dict.fromkeys(page_numbers) if page > 0]
        if not unique_docs or not unique_pages:
            return []
        where = {
            "$and": [
                {"document_id": unique_docs[0]}
                if len(unique_docs) == 1
                else {"document_id": {"$in": unique_docs}},
                {"page_number": unique_pages[0]}
                if len(unique_pages) == 1
                else {"page_number": {"$in": unique_pages}},
            ]
        }
        try:
            result = self._collection.get(where=where, include=["documents", "metadatas"])
        except Exception:
            if self.count() == 0:
                return []
            raise
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        hits: list[VectorHit] = []
        for chunk_id, text, metadata in zip(ids, documents, metadatas):
            hits.append(
                VectorHit(
                    chunk_id=chunk_id,
                    text=text or "",
                    distance=1.0,
                    metadata=dict(metadata or {}),
                )
            )
        return hits

    def count(self) -> int:
        return int(self._collection.count())

    def all_chunks(self) -> list[tuple[str, str, dict[str, Any]]]:
        result = self._collection.get(include=["documents", "metadatas"])
        return [
            (chunk_id, text or "", dict(metadata or {}))
            for chunk_id, text, metadata in zip(
                result.get("ids") or [], result.get("documents") or [], result.get("metadatas") or []
            )
        ]

    def get_with_distances(self, chunk_ids: list[str], query_embedding: list[float]) -> list[VectorHit]:
        """Fetch chunks by id and compute their cosine distance to the query embedding."""
        if not chunk_ids:
            return []
        result = self._collection.get(ids=chunk_ids, include=["documents", "metadatas", "embeddings"])
        hits: list[VectorHit] = []
        query_norm = math.sqrt(sum(value * value for value in query_embedding)) or 1.0
        embeddings = result.get("embeddings")
        if embeddings is None:
            embeddings = []
        for chunk_id, text, metadata, vector in zip(
            result.get("ids") or [], result.get("documents") or [], result.get("metadatas") or [], embeddings
        ):
            values = [float(item) for item in vector]
            norm = math.sqrt(sum(item * item for item in values)) or 1.0
            cosine = sum(a * b for a, b in zip(query_embedding, values)) / (query_norm * norm)
            hits.append(VectorHit(chunk_id=chunk_id, text=text or "", distance=1.0 - cosine, metadata=dict(metadata or {})))
        return hits

    def lexical_index(self) -> BM25Index:
        count = self.count()
        if self._lexical is None or self._lexical_count != count:
            self._lexical = BM25Index().build(self.all_chunks())
            self._lexical_count = count
        return self._lexical


def _chunk_metadata(chunk: Chunk) -> dict[str, Any]:
    return {
        "document_id": chunk.document_id,
        "document_title": chunk.document_title,
        "document_version": chunk.document_version or "",
        "academic_year": chunk.academic_year or "",
        "source_filename": chunk.source_filename,
        "page_number": chunk.page_number,
        "chunk_id": chunk.chunk_id,
        "section": chunk.section or "",
        "printed_page": chunk.printed_page or "",
    }


def _where_filter(document_ids: list[str] | None, academic_year: str | None) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if document_ids:
        if len(document_ids) == 1:
            clauses.append({"document_id": document_ids[0]})
        else:
            clauses.append({"document_id": {"$in": document_ids}})
    if academic_year:
        clauses.append({"academic_year": academic_year})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}
