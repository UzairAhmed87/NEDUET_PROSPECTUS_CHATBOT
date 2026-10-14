from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    service: str
    embedding_provider: str
    generation_provider: str
    documents_indexed: int
    groq_configured: bool
    groq_model: str
    embedding_model: str
