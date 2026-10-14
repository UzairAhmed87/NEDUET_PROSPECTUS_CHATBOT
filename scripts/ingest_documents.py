#!/usr/bin/env python3
"""Ingest PDF prospectuses into the local Chroma store."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))


def build_ingestion():
    from app.core.config import get_settings
    from app.providers.embeddings import build_embedding_provider
    from app.repositories.document_registry import DocumentRegistry
    from app.repositories.vector_store import ChromaVectorStore
    from app.services.chunking_service import ChunkingService
    from app.services.embedding_service import EmbeddingService
    from app.services.extraction_service import ExtractionService
    from app.services.ingestion_service import IngestionService

    settings = get_settings()
    settings.ensure_directories()
    return IngestionService(
        settings=settings,
        extraction_service=ExtractionService(),
        chunking_service=ChunkingService(settings.chunk_size_chars, settings.chunk_overlap_chars),
        embedding_service=EmbeddingService(build_embedding_provider(settings)),
        vector_store=ChromaVectorStore(settings.chroma_dir, settings.chroma_collection),
        registry=DocumentRegistry(settings.registry_path),
    ), settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest NED prospectus PDFs.")
    parser.add_argument("paths", nargs="+", type=Path, help="PDF files to ingest")
    parser.add_argument("--title", help="Display title")
    parser.add_argument("--version", dest="document_version", help="Document version label")
    parser.add_argument("--year", dest="academic_year", help="Academic year, e.g. 2024-25")
    parser.add_argument(
        "--verified",
        action="store_true",
        help="Mark authenticity as verified by the operator (do not set unless you checked the source)",
    )
    parser.add_argument("--replace", action="store_true", help="Replace an already indexed file with the same hash")
    args = parser.parse_args()

    ingestion, settings = build_ingestion()
    print(f"Provider: {settings.embedding_provider}  store: {settings.chroma_dir}")

    exit_code = 0
    for path in args.paths:
        print(f"\nIngesting {path} ...")
        try:
            result = ingestion.ingest_path(
                path,
                title=args.title,
                document_version=args.document_version,
                academic_year=args.academic_year,
                authenticity_verified=args.verified,
                replace=args.replace,
            )
        except Exception as exc:
            print(f"FAILED: {exc}")
            exit_code = 1
            continue
        doc = result.document
        print(f"OK  id={doc.document_id}  pages={doc.page_count}  chunks={doc.chunk_count}")
        for warning in result.warnings:
            print(f"  warning: {warning}")
        for issue in result.page_issues:
            kind = "ocr" if issue.needs_ocr else "empty"
            print(f"  page {issue.page_number}: {kind} (chars={issue.char_count}, images={issue.image_count})")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
