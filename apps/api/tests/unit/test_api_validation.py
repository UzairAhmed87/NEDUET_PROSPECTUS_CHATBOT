from app.schemas.chat import ChatRequest
from pydantic import ValidationError
import pytest


def test_chat_request_rejects_blank_question() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(question="   ")


def test_chat_request_strips_whitespace() -> None:
    payload = ChatRequest(question="  What programmes are listed?  ")
    assert payload.question == "What programmes are listed?"
