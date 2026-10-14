import logging

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_answer_service
from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationFailed
from app.core.logging import truncate_for_log
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.answer_service import AnswerService

router = APIRouter()
logger = logging.getLogger("ned.chat")


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    answer_service: AnswerService = Depends(get_answer_service),
) -> ChatResponse:
    del request
    if len(payload.question) > settings.max_question_chars:
        raise ValidationFailed(
            f"Question exceeds {settings.max_question_chars} characters.",
        )
    logger.info("chat question_chars=%s preview=%s", len(payload.question), truncate_for_log(payload.question, 48))
    return answer_service.answer(
        payload.question,
        conversation_id=payload.conversation_id,
        document_ids=payload.document_ids,
        academic_year=payload.academic_year,
    )
