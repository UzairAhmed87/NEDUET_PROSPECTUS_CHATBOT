from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import DuplicateDocumentError, ValidationFailed
from app.repositories.document_registry import DocumentRegistry, utcnow
from app.repositories.index_manifest import ensure_compatible, write_manifest
from app.repositories.vector_store import ChromaVectorStore
from app.schemas.documents import DocumentSummary, IngestResponse, PageIssue
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.extraction_service import ExtractionService
from app.utils.files import unique_destination, validate_pdf_payload
from app.utils.hashing import document_id_from, sha256_bytes

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        settings: Settings,
        extraction_service: ExtractionService,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        vector_store: ChromaVectorStore,
        registry: DocumentRegistry,
    ) -> None:
        self.settings = settings
        self.extraction_service = extraction_service
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.registry = registry

    def ingest_bytes(
        self,
        filename: str,
        payload: bytes,
        *,
        title: str | None = None,
        document_version: str | None = None,
        academic_year: str | None = None,
        authenticity_verified: bool = False,
        replace: bool = False,
    ) -> IngestResponse:
        safe_name = validate_pdf_payload(filename, payload, self.settings.max_upload_bytes)
        digest = sha256_bytes(payload)
        existing = self.registry.find_by_hash(digest)
        if existing and not replace:
            raise DuplicateDocumentError(
                "This file has already been ingested. Pass replace=true to re-index it.",
                details={"document_id": existing.document_id, "sha256": digest},
            )

        document_id = existing.document_id if existing else document_id_from(safe_name, digest)
        destination = self._write_payload(safe_name, payload, document_id)
        return self._index_path(
            destination,
            document_id=document_id,
            digest=digest,
            title=title or Path(safe_name).stem.replace("-", " ").replace("_", " "),
            document_version=document_version,
            academic_year=academic_year,
            authenticity_verified=authenticity_verified,
            replace=bool(existing),
            source_filename=safe_name,
        )

    def ingest_path(
        self,
        path: Path,
        *,
        title: str | None = None,
        document_version: str | None = None,
        academic_year: str | None = None,
        authenticity_verified: bool = False,
        replace: bool = False,
    ) -> IngestResponse:
        if not path.is_file():
            raise ValidationFailed(f"File not found: {path}")
        payload = path.read_bytes()
        return self.ingest_bytes(
            path.name,
            payload,
            title=title,
            document_version=document_version,
            academic_year=academic_year,
            authenticity_verified=authenticity_verified,
            replace=replace,
        )

    def _write_payload(self, safe_name: str, payload: bytes, document_id: str) -> Path:
        target_name = f"{document_id}{Path(safe_name).suffix.lower()}"
        destination = unique_destination(self.settings.documents_dir, target_name)
        destination.write_bytes(payload)
        return destination

    def _index_path(
        self,
        path: Path,
        *,
        document_id: str,
        digest: str,
        title: str,
        document_version: str | None,
        academic_year: str | None,
        authenticity_verified: bool,
        replace: bool,
        source_filename: str,
    ) -> IngestResponse:
        manifest = ensure_compatible(
            self.settings.chroma_dir,
            embedding_provider=self.settings.embedding_provider,
            embedding_model=self.settings.embedding_model,
        )
        logger.info("Extracting PDF %s", path.name)
        extraction = self.extraction_service.extract_pdf(path)
        chunks = self.chunking_service.chunk_extraction(
            extraction,
            document_id=document_id,
            document_title=title,
            document_version=document_version,
            academic_year=academic_year,
            source_filename=source_filename,
        )
        logger.info("Embedding %s chunks for %s", len(chunks), document_id)
        embeddings = self.embedding_service.embed_chunks(chunks)

        if replace:
            self.vector_store.delete_document(document_id)
            self.registry.delete(document_id)

        self.vector_store.upsert_chunks(chunks, embeddings)
        chunking_config = self.chunking_service.config()
        write_manifest(
            self.settings.chroma_dir,
            embedding_provider=self.settings.embedding_provider,
            embedding_model=self.settings.embedding_model,
            extraction=extraction.config,
            chunking=chunking_config,
            documents={
                document_id: {
                    "sha256": digest,
                    "chunk_count": len(chunks),
                    "extraction": extraction.config,
                    "chunking": chunking_config,
                }
            },
            chunk_count=self.vector_store.count(),
        )
        summary = DocumentSummary(
            document_id=document_id,
            title=title,
            source_filename=source_filename,
            document_version=document_version,
            academic_year=academic_year,
            authenticity_verified=authenticity_verified,
            page_count=extraction.page_count,
            chunk_count=len(chunks),
            sha256=digest,
            ingested_at=utcnow(),
            headings=extraction.headings,
            ocr_page_count=extraction.ocr_page_count,
            empty_page_count=extraction.empty_page_count,
        )
        self.registry.upsert(summary)

        warnings: list[str] = []
        if extraction.ocr_page_count:
            warnings.append(
                f"{extraction.ocr_page_count} page(s) were image-only and were indexed via OCR. Layout and tables may be imperfect."
            )
        if extraction.ocr_failed_pages:
            warnings.append(
                f"OCR failed on page(s) {extraction.ocr_failed_pages}; their content is NOT indexed."
            )
        fixed_pages = [page.page_number for page in extraction.pages if page.digit_fixes]
        if fixed_pages:
            warnings.append(
                f"Letter 'o' was read as zero inside numbers on page(s) {fixed_pages}; verify those figures against the PDF."
            )
        if manifest and (
            manifest.get("chunking") != self.chunking_service.config()
            or manifest.get("extraction") != extraction.config
        ):
            warnings.append(
                "This document was indexed with different extraction/chunking settings than the existing index."
            )
        if extraction.empty_page_count:
            warnings.append(f"{extraction.empty_page_count} page(s) contained no extractable text.")
        if not authenticity_verified:
            warnings.append(
                "Authenticity is unverified. The assistant will not describe this file as the latest official prospectus."
            )
        if extraction.extractable_char_count < 400:
            warnings.append("Very little text was extracted; retrieval quality may be poor.")

        page_issues = [
            PageIssue(
                page_number=page.page_number,
                is_empty=page.is_empty,
                needs_ocr=page.needs_ocr,
                char_count=page.char_count,
                image_count=page.image_count,
                ocr_error=page.ocr_error,
            )
            for page in extraction.pages
            if page.is_empty or page.needs_ocr or page.ocr_error
        ]
        logger.info("Ingested %s (%s chunks)", document_id, len(chunks))
        return IngestResponse(
            document=summary,
            replaced=replace,
            warnings=warnings,
            page_issues=page_issues,
        )
