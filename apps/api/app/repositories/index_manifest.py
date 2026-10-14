"""Records how a vector index was built so incompatible indexes are never mixed or queried."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import ValidationFailed

MANIFEST_FILENAME = "index_manifest.json"


def manifest_path(chroma_dir: Path) -> Path:
    return chroma_dir / MANIFEST_FILENAME


def read_manifest(chroma_dir: Path) -> dict | None:
    path = manifest_path(chroma_dir)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def embedding_signature(provider: str, model: str) -> str:
    return f"{provider.strip().lower()}:{model.strip().lower()}"


def ensure_compatible(chroma_dir: Path, *, embedding_provider: str, embedding_model: str) -> dict | None:
    """Raise if the index was embedded with a different model than the one configured."""
    manifest = read_manifest(chroma_dir)
    if manifest is None:
        return None
    built_with = manifest.get("embedding_signature")
    configured = embedding_signature(embedding_provider, embedding_model)
    if built_with and built_with != configured:
        raise ValidationFailed(
            "The vector index was built with a different embedding model. "
            "Re-embed the entire corpus before querying or adding documents.",
            details={"index_embedding": built_with, "configured_embedding": configured},
        )
    return manifest


def write_manifest(
    chroma_dir: Path,
    *,
    embedding_provider: str,
    embedding_model: str,
    extraction: dict,
    chunking: dict,
    documents: dict[str, dict],
    chunk_count: int,
) -> dict:
    existing = read_manifest(chroma_dir) or {}
    merged_documents = {**(existing.get("documents") or {}), **documents}
    manifest = {
        "embedding_signature": embedding_signature(embedding_provider, embedding_model),
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "extraction": extraction,
        "chunking": chunking,
        "documents": merged_documents,
        "chunk_count": chunk_count,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    chroma_dir.mkdir(parents=True, exist_ok=True)
    manifest_path(chroma_dir).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
