from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.repositories.document_registry import DocumentRegistry
from app.api.dependencies import get_registry
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_settings),
    registry: DocumentRegistry = Depends(get_registry),
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="ned-prospectus-assistant",
        embedding_provider=settings.embedding_provider,
        generation_provider=settings.generation_provider,
        documents_indexed=registry.count(),
        groq_configured=bool(settings.groq_api_key),
        groq_model=settings.groq_model,
        embedding_model=settings.embedding_model,
    )
