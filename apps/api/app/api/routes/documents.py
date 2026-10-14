from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.exceptions import ValidationFailed
from app.core.security import require_admin_key
from app.api.dependencies import get_ingestion_service, get_registry
from app.repositories.document_registry import DocumentRegistry
from app.schemas.documents import DocumentListResponse, IngestResponse
from app.services.ingestion_service import IngestionService

router = APIRouter()

AUTHENTICITY_NOTICE = (
    "Listed documents are whatever has been ingested locally. "
    "A file is not treated as the latest official NED prospectus unless authenticity_verified is true."
)


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(registry: DocumentRegistry = Depends(get_registry)) -> DocumentListResponse:
    return DocumentListResponse(documents=registry.list_documents(), authenticity_notice=AUTHENTICITY_NOTICE)


@router.post(
    "/documents/ingest",
    response_model=IngestResponse,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    document_version: str | None = Form(default=None),
    academic_year: str | None = Form(default=None),
    authenticity_verified: bool = Form(default=False),
    replace: bool = Form(default=False),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> IngestResponse:
    filename = file.filename or "upload.pdf"
    payload = await file.read()
    if not payload:
        raise ValidationFailed("Uploaded file is empty.")
    return ingestion_service.ingest_bytes(
        filename,
        payload,
        title=title,
        document_version=document_version,
        academic_year=academic_year,
        authenticity_verified=authenticity_verified,
        replace=replace,
    )
