from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    document_ids: list[str] | None = None
    academic_year: str | None = None

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty.")
        return cleaned


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    document_version: str | None = None
    source_filename: str
    page_number: int
    excerpt: str
    distance: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    insufficient_evidence: bool
    limitation: str | None = None
    # no_relevant_passages | weak_evidence | model_insufficient | no_valid_citation | unverified_figures
    refusal_reason: str | None = None
    conversation_id: str
    retrieved_chunk_count: int
