import json

import pytest

from app.core.exceptions import ProviderError
from app.schemas.retrieval import RetrievedChunk
from app.services.answer_service import AnswerService
from app.services.conversation_store import ConversationStore
from app.services.retrieval_service import RetrievalResult


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="doc-p100-c1",
        document_id="doc",
        document_title="Fixture",
        document_version=None,
        source_filename="fixture.pdf",
        page_number=100,
        excerpt="fee",
        distance=0.4,
        text="Semester fee Rs.1/-",
        within_threshold=True,
    )


class _StubRetrieval:
    def retrieve(self, *_args, **_kwargs) -> RetrievalResult:
        chunk = _chunk()
        return RetrievalResult(hits=[chunk], accepted=[chunk], insufficient_evidence=False)


class _SequenceProvider:
    name = "stub"
    model_name = "stub"

    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls = 0

    def generate(self, _system: str, _user: str) -> str:
        output = self.outputs[self.calls]
        self.calls += 1
        return output


VALID = json.dumps(
    {
        "answer": "The semester fee is Rs.1/- (page 100).",
        "citation_ids": ["doc-p100-c1"],
        "insufficient_evidence": False,
        "limitation": None,
    }
)


def test_truncated_json_is_retried_once() -> None:
    provider = _SequenceProvider(['{"answer": "The semester fee is', VALID])
    service = AnswerService(_StubRetrieval(), provider, ConversationStore())
    response = service.answer("What is the fee?")
    assert provider.calls == 2
    assert response.insufficient_evidence is False
    assert response.citations[0].page_number == 100


def test_persistent_invalid_json_raises_after_retry() -> None:
    provider = _SequenceProvider(["not json", "still not json"])
    service = AnswerService(_StubRetrieval(), provider, ConversationStore())
    with pytest.raises(ProviderError):
        service.answer("What is the fee?")
    assert provider.calls == 2
