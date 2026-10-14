from datetime import datetime

from pydantic import BaseModel, Field


class PageIssue(BaseModel):
    page_number: int
    is_empty: bool
    needs_ocr: bool
    char_count: int
    image_count: int
    ocr_error: str | None = None


class DocumentSummary(BaseModel):
    document_id: str
    title: str
    source_filename: str
    document_version: str | None = None
    academic_year: str | None = None
    authenticity_verified: bool = False
    page_count: int
    chunk_count: int
    sha256: str
    ingested_at: datetime
    headings: list[str] = Field(default_factory=list)
    ocr_page_count: int = 0
    empty_page_count: int = 0


class IngestResponse(BaseModel):
    document: DocumentSummary
    replaced: bool = False
    warnings: list[str] = Field(default_factory=list)
    page_issues: list[PageIssue] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
    authenticity_notice: str
