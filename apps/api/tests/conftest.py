from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

os.environ.setdefault("EMBEDDING_PROVIDER", "fake")
os.environ.setdefault("GENERATION_PROVIDER", "fake")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key-not-default")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("CHAT_RATE_LIMIT_PER_MINUTE", "1000")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

from tests.fixtures.pdf_factory import PROSPECTUS_PAGES, write_fixture_pdf  # noqa: E402


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    chroma = tmp_path / "chroma"
    documents = tmp_path / "documents"
    chroma.mkdir()
    documents.mkdir()
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("GENERATION_PROVIDER", "fake")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key-not-default")
    monkeypatch.setenv("CHROMA_DIR", str(chroma))
    monkeypatch.setenv("DOCUMENTS_DIR", str(documents))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RETRIEVAL_MAX_DISTANCE", "0.72")
    monkeypatch.setenv("RETRIEVAL_TOP_K", "6")
    from app.api.dependencies import reset_runtime_caches
    from app.core.config import get_settings

    reset_runtime_caches()
    settings = get_settings()
    yield {"settings": settings, "chroma": chroma, "documents": documents, "root": tmp_path}
    reset_runtime_caches()


@pytest.fixture
def fixture_pdf(tmp_path) -> Path:
    path = tmp_path / "ned-test-fixture.pdf"
    write_fixture_pdf(path, PROSPECTUS_PAGES)
    return path


@pytest.fixture
def services(tmp_env):
    from app.providers.embeddings import FakeEmbeddingProvider
    from app.providers.generation import FakeGenerationProvider
    from app.repositories.document_registry import DocumentRegistry
    from app.repositories.vector_store import ChromaVectorStore
    from app.services.answer_service import AnswerService
    from app.services.chunking_service import ChunkingService
    from app.services.conversation_store import ConversationStore
    from app.services.embedding_service import EmbeddingService
    from app.services.extraction_service import ExtractionService
    from app.services.ingestion_service import IngestionService
    from app.services.retrieval_service import RetrievalService

    settings = tmp_env["settings"]
    embedding = EmbeddingService(FakeEmbeddingProvider())
    vector_store = ChromaVectorStore(settings.chroma_dir, settings.chroma_collection)
    registry = DocumentRegistry(settings.registry_path)
    chunking = ChunkingService(settings.chunk_size_chars, settings.chunk_overlap_chars)
    ingestion = IngestionService(
        settings=settings,
        extraction_service=ExtractionService(),
        chunking_service=chunking,
        embedding_service=embedding,
        vector_store=vector_store,
        registry=registry,
    )
    retrieval = RetrievalService(settings, embedding, vector_store)
    answers = AnswerService(retrieval, FakeGenerationProvider(), ConversationStore())
    return {
        "settings": settings,
        "ingestion": ingestion,
        "retrieval": retrieval,
        "answers": answers,
        "registry": registry,
        "chunking": chunking,
        "extraction": ExtractionService(),
    }


@pytest.fixture
def client(tmp_env):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
