#!/usr/bin/env python3
"""Build a vector index for one PDF into a chosen directory and record its manifest.

Used to compare extraction / chunking / embedding configurations side by side without
touching the production index. OCR results are cached per page, so only the first run
pays the OCR cost.

Example:
  python scripts/build_index.py data/documents/UGProspectus2025.pdf \
      --chroma-dir data/experiments/cols_600 --chunk-size 650 --overlap 100 --section-headers
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--chroma-dir", type=Path, required=True)
    parser.add_argument("--title", default="Undergraduate Prospectus 2025")
    parser.add_argument("--year", default="2025")
    parser.add_argument("--version", default=None)
    parser.add_argument("--chunk-size", type=int)
    parser.add_argument("--overlap", type=int)
    parser.add_argument("--section-headers", action="store_true")
    parser.add_argument("--no-columns", action="store_true", help="Keep OCR engine line order (old behaviour)")
    parser.add_argument("--no-digit-fix", action="store_true")
    parser.add_argument("--embedding-model")
    parser.add_argument("--fresh", action="store_true", help="Delete the target directory first")
    parser.add_argument("--report", type=Path, help="Write a per-page extraction report (JSON)")
    parser.add_argument("--dump-text", type=Path, help="Write extracted page text for inspection")
    args = parser.parse_args()

    from app.core.config import get_settings
    from app.providers.embeddings import build_embedding_provider
    from app.repositories.document_registry import DocumentRegistry
    from app.repositories.vector_store import ChromaVectorStore
    from app.services.chunking_service import ChunkingService
    from app.services.embedding_service import EmbeddingService
    from app.services.extraction_service import ExtractionService
    from app.services.ingestion_service import IngestionService
    from app.utils.hashing import document_id_from, sha256_bytes

    if args.fresh and args.chroma_dir.exists():
        shutil.rmtree(args.chroma_dir)
    updates: dict = {"chroma_dir": args.chroma_dir}
    if args.embedding_model:
        updates["embedding_model"] = args.embedding_model
    settings = get_settings().model_copy(update=updates)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)

    extraction = ExtractionService(
        ocr_cache_dir=settings.ocr_cache_dir,
        column_aware=not args.no_columns,
        fix_ocr_digits=not args.no_digit_fix,
    )
    chunking = ChunkingService(
        args.chunk_size or settings.chunk_size_chars,
        args.overlap if args.overlap is not None else settings.chunk_overlap_chars,
        section_headers=args.section_headers,
    )
    store = ChromaVectorStore(settings.chroma_dir, settings.chroma_collection)
    service = IngestionService(
        settings=settings,
        extraction_service=extraction,
        chunking_service=chunking,
        embedding_service=EmbeddingService(build_embedding_provider(settings)),
        vector_store=store,
        registry=DocumentRegistry(settings.registry_path),
    )

    payload = args.pdf.read_bytes()
    digest = sha256_bytes(payload)
    started = time.perf_counter()
    response = service._index_path(
        args.pdf,
        document_id=document_id_from(args.pdf.name, digest),
        digest=digest,
        title=args.title,
        document_version=args.version,
        academic_year=args.year,
        authenticity_verified=False,
        replace=True,
        source_filename=args.pdf.name,
    )
    elapsed = time.perf_counter() - started
    print(json.dumps({"document_id": response.document.document_id, "chunks": response.document.chunk_count,
                      "seconds": round(elapsed, 1), "warnings": response.warnings}, indent=2))

    if args.report or args.dump_text:
        result = extraction.extract_pdf(args.pdf)
        if args.report:
            rows = [
                {
                    "page": page.page_number,
                    "printed_page": page.printed_page,
                    "chars": page.char_count,
                    "ocr_used": page.ocr_used,
                    "ocr_error": page.ocr_error,
                    "columns": page.ocr_columns,
                    "confidence": page.ocr_confidence,
                    "low_confidence_lines": page.ocr_low_confidence_lines,
                    "digit_fixes": page.digit_fixes,
                }
                for page in result.pages
            ]
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps({"config": result.config, "pages": rows}, indent=2), encoding="utf-8")
        if args.dump_text:
            args.dump_text.parent.mkdir(parents=True, exist_ok=True)
            with args.dump_text.open("w", encoding="utf-8") as handle:
                for page in result.pages:
                    handle.write(f"\n===== PAGE {page.page_number} (printed {page.printed_page}) =====\n{page.text}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
