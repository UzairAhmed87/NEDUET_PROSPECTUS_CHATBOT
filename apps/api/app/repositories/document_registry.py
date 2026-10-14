from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.documents import DocumentSummary


class DocumentRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"documents": []})

    def list_documents(self) -> list[DocumentSummary]:
        payload = self._read()
        documents = [DocumentSummary.model_validate(item) for item in payload.get("documents", [])]
        documents.sort(key=lambda item: item.ingested_at, reverse=True)
        return documents

    def get(self, document_id: str) -> DocumentSummary | None:
        for document in self.list_documents():
            if document.document_id == document_id:
                return document
        return None

    def find_by_hash(self, sha256: str) -> DocumentSummary | None:
        for document in self.list_documents():
            if document.sha256 == sha256:
                return document
        return None

    def upsert(self, document: DocumentSummary) -> None:
        documents = [item for item in self.list_documents() if item.document_id != document.document_id]
        documents.append(document)
        self._write({"documents": [item.model_dump(mode="json") for item in documents]})

    def delete(self, document_id: str) -> None:
        documents = [item for item in self.list_documents() if item.document_id != document_id]
        self._write({"documents": [item.model_dump(mode="json") for item in documents]})

    def count(self) -> int:
        return len(self.list_documents())

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"documents": []}

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
