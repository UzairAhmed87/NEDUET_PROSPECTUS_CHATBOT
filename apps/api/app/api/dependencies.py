from functools import lru_cache

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.security import require_admin_key
from app.providers.embeddings import build_embedding_provider
from app.providers.generation import build_generation_provider
from app.repositories.document_registry import DocumentRegistry
from app.repositories.vector_store import ChromaVectorStore
from app.services.answer_service import AnswerService
from app.services.chunking_service import ChunkingService
from app.services.conversation_store import ConversationStore
from app.services.embedding_service import EmbeddingService
from app.services.extraction_service import ExtractionService
from app.services.ingestion_service import IngestionService
from app.services.retrieval_service import RetrievalService

AdminAuth = Depends(require_admin_key)


@lru_cache
def get_registry() -> DocumentRegistry:
    return DocumentRegistry(get_settings().registry_path)


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    settings = get_settings()
    return ChromaVectorStore(settings.chroma_dir, settings.chroma_collection)


@lru_cache
def get_conversation_store() -> ConversationStore:
    return ConversationStore()


def reset_runtime_caches() -> None:
    get_settings.cache_clear()
    get_registry.cache_clear()
    get_vector_store.cache_clear()
    get_conversation_store.cache_clear()


def get_embedding_service(settings: Settings = Depends(get_settings)) -> EmbeddingService:
    return EmbeddingService(build_embedding_provider(settings))


def get_chunking_service(settings: Settings = Depends(get_settings)) -> ChunkingService:
    return ChunkingService(
        settings.chunk_size_chars,
        settings.chunk_overlap_chars,
        section_headers=settings.chunk_section_headers,
    )


def get_ingestion_service(
    settings: Settings = Depends(get_settings),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    chunking_service: ChunkingService = Depends(get_chunking_service),
    vector_store: ChromaVectorStore = Depends(get_vector_store),
    registry: DocumentRegistry = Depends(get_registry),
) -> IngestionService:
    return IngestionService(
        settings=settings,
        extraction_service=ExtractionService(ocr_cache_dir=settings.ocr_cache_dir),
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        vector_store=vector_store,
        registry=registry,
    )


def get_retrieval_service(
    settings: Settings = Depends(get_settings),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: ChromaVectorStore = Depends(get_vector_store),
) -> RetrievalService:
    return RetrievalService(settings, embedding_service, vector_store)


def get_answer_service(
    settings: Settings = Depends(get_settings),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    conversation_store: ConversationStore = Depends(get_conversation_store),
) -> AnswerService:
    return AnswerService(
        retrieval_service=retrieval_service,
        generation_provider=build_generation_provider(settings),
        conversation_store=conversation_store,
    )
