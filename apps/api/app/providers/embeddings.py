from __future__ import annotations

import hashlib
import math
import re

from app.core.config import Settings
from app.core.exceptions import ProviderConfigurationError, ProviderError

_TOKEN = re.compile(r"[a-z0-9]+")
FAKE_DIMENSION = 96
LOCAL_DIMENSION = 384
SUPPORTED_LOCAL_MODELS = {"all-minilm-l6-v2"}
_STOP = {
    "this",
    "that",
    "with",
    "from",
    "have",
    "what",
    "when",
    "which",
    "your",
    "about",
    "does",
    "the",
    "and",
    "for",
    "are",
    "was",
    "were",
    "you",
    "not",
    "but",
}


class FakeEmbeddingProvider:
    """Deterministic token-hash embeddings for tests. Not for production answers."""

    name = "fake"
    model_name = "hash-v1"
    dimension = FAKE_DIMENSION

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = [
            token
            for token in _TOKEN.findall(text.lower())
            if len(token) >= 4 and token not in _STOP
        ]
        if not tokens:
            vector[0] = 1.0
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return _l2_normalize(vector)


class LocalEmbeddingProvider:
    """ONNX MiniLM embeddings used for both indexing and query vectors."""

    name = "local"
    dimension = LOCAL_DIMENSION

    def __init__(self, model_name: str) -> None:
        normalized = model_name.strip()
        if normalized.lower() not in SUPPORTED_LOCAL_MODELS:
            raise ProviderConfigurationError(
                "The local embedding provider currently supports only all-MiniLM-L6-v2 "
                f"(384 dimensions). Received {model_name!r}."
            )
        try:
            from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
        except ImportError as exc:  # pragma: no cover
            raise ProviderConfigurationError(
                "ChromaDB ONNX embeddings are not available. Install chromadb and onnxruntime."
            ) from exc
        self.model_name = normalized
        self._fn = ONNXMiniLM_L6_V2()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self._fn(texts)
        except Exception as exc:
            raise ProviderError("Local embedding failed.") from exc
        return [_as_float_list(vector) for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


def build_embedding_provider(settings: Settings) -> FakeEmbeddingProvider | LocalEmbeddingProvider:
    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider()
    return LocalEmbeddingProvider(settings.embedding_model)


def _as_float_list(vector) -> list[float]:
    values = list(vector)
    if not values:
        raise ProviderError("Embedding provider returned an empty vector.")
    return [float(value) for value in values]


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0:
        return vector
    return [component / norm for component in vector]
