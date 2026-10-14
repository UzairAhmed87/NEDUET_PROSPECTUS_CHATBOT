import pytest

from app.core.exceptions import ProviderError
from app.services.answer_service import parse_model_answer


def test_parses_plain_json() -> None:
    parsed = parse_model_answer(
        '{"answer":"No.","citation_ids":["a"],"insufficient_evidence":false,"limitation":null}'
    )
    assert parsed.answer == "No."
    assert parsed.citation_ids == ["a"]


def test_parses_fenced_json() -> None:
    parsed = parse_model_answer("```json\n{\"answer\":\"Yes.\",\"citation_ids\":[],\"insufficient_evidence\":true}\n```")
    assert parsed.insufficient_evidence is True


def test_rejects_non_json() -> None:
    with pytest.raises(ProviderError):
        parse_model_answer("not json")
