from fastapi import APIRouter, Depends

from app.api.dependencies import get_retrieval_service
from app.core.config import get_settings
from app.core.security import require_admin_key
from app.schemas.retrieval import RetrievalDebugRequest, RetrievalDebugResponse
from app.services.retrieval_service import RetrievalService

router = APIRouter()


@router.post(
    "/retrieval/debug",
    response_model=RetrievalDebugResponse,
    dependencies=[Depends(require_admin_key)],
)
def retrieval_debug(
    payload: RetrievalDebugRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> RetrievalDebugResponse:
    settings = get_settings()
    result = retrieval_service.retrieve(
        payload.question,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
        academic_year=payload.academic_year,
    )
    return RetrievalDebugResponse(
        question=payload.question,
        top_k=payload.top_k or settings.retrieval_top_k,
        max_distance=settings.retrieval_max_distance,
        embedding_provider=settings.embedding_provider,
        embedding_model=retrieval_service.embedding_service.provider.model_name,
        hits=result.hits,
        accepted_count=len(result.accepted),
        insufficient_evidence=result.insufficient_evidence,
    )
