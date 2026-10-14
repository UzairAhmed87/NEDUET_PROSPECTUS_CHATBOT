from pydantic import BaseModel, Field, field_validator

from app.schemas.chat import Citation


class RetrievalDebugRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=32)
    document_ids: list[str] | None = None
    academic_year: str | None = None

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty.")
        return cleaned


class RetrievedChunk(Citation):
    text: str
    within_threshold: bool


class RetrievalDebugResponse(BaseModel):
    question: str
    top_k: int
    max_distance: float
    embedding_provider: str
    embedding_model: str
    hits: list[RetrievedChunk]
    accepted_count: int
    insufficient_evidence: bool
