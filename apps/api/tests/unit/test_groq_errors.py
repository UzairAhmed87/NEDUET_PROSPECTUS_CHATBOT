from app.core.exceptions import ProviderError
from app.providers.generation import sanitize_generation_exception


def test_timeout_message_is_sanitized() -> None:
    error = sanitize_generation_exception(TimeoutError("request timeout"))
    assert isinstance(error, ProviderError)
    assert "timed out" in error.message.lower()
    assert "gsk_" not in error.message


def test_rate_limit_message_is_sanitized() -> None:
    error = sanitize_generation_exception(RuntimeError("429 rate limit exceeded"))
    assert "rate limit" in error.message.lower()


def test_auth_message_does_not_leak_key() -> None:
    error = sanitize_generation_exception(RuntimeError("Invalid API key gsk_secret"))
    assert "gsk_secret" not in error.message
    assert "credentials" in error.message.lower()
