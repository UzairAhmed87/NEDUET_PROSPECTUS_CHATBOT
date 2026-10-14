from __future__ import annotations

import json
import re

from app.core.config import Settings
from app.core.exceptions import ProviderConfigurationError, ProviderError

_PASSAGE_ID = re.compile(r'<passage id="([^"]+)"')


class FakeGenerationProvider:
    """Returns grounded JSON from retrieved passage IDs. Used in tests only."""

    name = "fake"
    model_name = "fixture-generator"

    def generate(self, system_instruction: str, user_prompt: str) -> str:
        del system_instruction
        passage_ids = _PASSAGE_ID.findall(user_prompt)
        passages = _extract_passage_bodies(user_prompt)
        question = _extract_current_question(user_prompt).lower()

        injection_markers = (
            "ignore all previous",
            "ignore previous instructions",
            "you are now",
            "reveal the system prompt",
            "from your general knowledge",
            "bypass grounding",
        )
        user_is_adversarial = any(marker in question for marker in injection_markers)
        passage_injection = any(
            "ignore all previous" in body.lower() or "reveal the system prompt" in body.lower()
            for body in passages
        )
        asking_to_follow_hidden = any(
            token in question
            for token in ("hidden instruction", "admission is free", "deadline is tomorrow")
        )

        if user_is_adversarial or not passage_ids or (passage_injection and asking_to_follow_hidden):
            return json.dumps(
                {
                    "answer": (
                        "The available prospectus does not provide enough information "
                        "to answer reliably."
                    ),
                    "citation_ids": [],
                    "insufficient_evidence": True,
                    "limitation": "The question could not be grounded in retrieved passages.",
                }
            )

        combined = " ".join(passages).lower()
        if _question_unsupported(question, combined):
            return json.dumps(
                {
                    "answer": (
                        "The available prospectus does not provide enough information "
                        "to answer reliably."
                    ),
                    "citation_ids": [],
                    "insufficient_evidence": True,
                    "limitation": "Retrieved passages do not establish the requested fact.",
                }
            )

        snippet = passages[0].strip().replace("\n", " ")
        if len(snippet) > 420:
            snippet = snippet[:419] + "…"
        return json.dumps(
            {
                "answer": (
                    "According to the retrieved prospectus passage: "
                    f"{snippet} This is not an official university decision."
                ),
                "citation_ids": passage_ids[:3],
                "insufficient_evidence": False,
                "limitation": None,
            }
        )


class GroqGenerationProvider:
    name = "groq"

    def __init__(
        self,
        api_key: str,
        model_name: str,
        timeout_seconds: float = 60.0,
        max_completion_tokens: int = 4096,
        reasoning_effort: str = "",
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError(
                "GROQ_API_KEY is required when GENERATION_PROVIDER=groq."
            )
        if not model_name.strip():
            raise ProviderConfigurationError("GROQ_MODEL must be set to a Groq chat model id.")
        try:
            from groq import Groq
        except ImportError as exc:  # pragma: no cover
            raise ProviderConfigurationError("The groq package is not installed.") from exc
        self.model_name = model_name.strip()
        self.max_completion_tokens = max_completion_tokens
        self.reasoning_effort = reasoning_effort.strip().lower()
        self._client = Groq(api_key=api_key, timeout=timeout_seconds)

    def generate(self, system_instruction: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt},
        ]
        last_error: Exception | None = None
        for attempt in range(2):
            kwargs: dict = {
                "model": self.model_name,
                "temperature": 0.0,
                "messages": messages,
                "max_completion_tokens": self.max_completion_tokens,
            }
            if self.reasoning_effort:
                kwargs["reasoning_effort"] = self.reasoning_effort
            if attempt == 0:
                kwargs["response_format"] = {"type": "json_object"}
            try:
                response = self._client.chat.completions.create(**kwargs)
            except Exception as exc:
                last_error = exc
                if attempt == 0 and _is_retryable_json_error(exc):
                    continue
                raise sanitize_generation_exception(exc) from exc
            text = ""
            finish_reason = None
            if response.choices:
                text = response.choices[0].message.content or ""
                finish_reason = getattr(response.choices[0], "finish_reason", None)
            if finish_reason == "length":
                last_error = ProviderError("The Groq response was cut off before it finished.")
                if attempt == 0:
                    continue
                raise last_error
            if text.strip():
                return text
            last_error = ProviderError("The generation provider returned an empty response.")
            if attempt == 0:
                continue
        if isinstance(last_error, Exception) and not isinstance(last_error, ProviderError):
            raise sanitize_generation_exception(last_error) from last_error
        raise ProviderError("The generation provider returned an empty response.")


def build_generation_provider(settings: Settings) -> FakeGenerationProvider | GroqGenerationProvider:
    if settings.generation_provider == "fake":
        return FakeGenerationProvider()
    return GroqGenerationProvider(
        settings.groq_api_key,
        settings.groq_model,
        timeout_seconds=settings.groq_timeout_seconds,
        max_completion_tokens=settings.groq_max_completion_tokens,
        reasoning_effort=settings.groq_reasoning_effort,
    )


def _is_retryable_json_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "json_validate_failed" in message or "failed to validate json" in message


def sanitize_generation_exception(exc: Exception) -> ProviderError:
    try:
        import groq
    except ImportError:
        groq = None  # type: ignore[assignment]

    if groq is not None:
        if isinstance(exc, groq.AuthenticationError):
            return ProviderError("The Groq API rejected the configured credentials.")
        if isinstance(exc, groq.RateLimitError):
            return ProviderError("The Groq API rate limit was exceeded. Please wait and try again.")
        if isinstance(exc, getattr(groq, "APITimeoutError", tuple())):
            return ProviderError("The Groq API request timed out.")
        if isinstance(exc, groq.APIStatusError):
            status = getattr(exc, "status_code", None)
            if status in {401, 403}:
                return ProviderError("The Groq API rejected the configured credentials.")
            if status == 429:
                return ProviderError("The Groq API rate limit was exceeded. Please wait and try again.")

    message = str(exc).lower()
    if "timeout" in message:
        return ProviderError("The Groq API request timed out.")
    if "rate" in message or "429" in message:
        return ProviderError("The Groq API rate limit was exceeded. Please wait and try again.")
    if "api key" in message or "401" in message or "unauthorized" in message:
        return ProviderError("The Groq API rejected the configured credentials.")
    return ProviderError("The Groq API request failed.")


def _extract_passage_bodies(prompt: str) -> list[str]:
    bodies = re.findall(r"<passage[^>]*>(.*?)</passage>", prompt, flags=re.DOTALL)
    return [body.strip() for body in bodies]


def _extract_current_question(prompt: str) -> str:
    match = re.search(r"CURRENT QUESTION:\s*(.*?)(?:\n\n|\Z)", prompt, flags=re.DOTALL)
    return match.group(1).strip() if match else prompt


def _question_unsupported(question: str, combined_passages: str) -> bool:
    if "capital of france" in question or "weather" in question:
        return True
    if "deadline is tomorrow" in question:
        return True
    if "admission is free" in question and "admission is free" not in combined_passages:
        return True
    return False
