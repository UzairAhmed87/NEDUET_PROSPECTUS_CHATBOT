from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    model_name: str
    dimension: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@runtime_checkable
class GenerationProvider(Protocol):
    name: str
    model_name: str

    def generate(self, system_instruction: str, user_prompt: str) -> str: ...
