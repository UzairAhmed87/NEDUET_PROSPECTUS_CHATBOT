from app.providers.base import EmbeddingProvider
from app.services.chunking_service import Chunk


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        return self.provider.embed_texts([chunk.text for chunk in chunks])

    def embed_query(self, question: str) -> list[float]:
        return self.provider.embed_query(question)
