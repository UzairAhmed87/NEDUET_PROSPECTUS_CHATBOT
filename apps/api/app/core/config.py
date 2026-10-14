from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", Path(".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_timeout_seconds: float = 60.0
    groq_max_completion_tokens: int = 4096
    groq_reasoning_effort: str = "low"

    embedding_provider: str = "local"
    generation_provider: str = "groq"
    embedding_model: str = "all-MiniLM-L6-v2"

    admin_api_key: str = "change-me-to-a-long-random-string"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    data_dir: Path = ROOT_DIR / "data"
    documents_dir: Path = ROOT_DIR / "data" / "documents"
    chroma_dir: Path = ROOT_DIR / "data" / "chroma"
    registry_filename: str = "document_registry.json"
    ocr_cache_dir: Path = ROOT_DIR / "data" / "ocr_cache"

    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 200
    chunk_section_headers: bool = False

    retrieval_top_k: int = 12
    retrieval_max_distance: float = 0.72
    # vector: cosine search + lexical rerank; hybrid: cosine + BM25 fused with RRF
    retrieval_mode: str = "vector"
    retrieval_rrf_k: int = 60
    # Answerability gate: when the best distance is above this value, also require the
    # IDF-weighted share of query terms found in a top passage to reach min_coverage.
    retrieval_strict_distance: float | None = None
    retrieval_min_coverage: float = 0.0

    max_upload_mb: int = 50
    max_question_chars: int = 2000
    chat_rate_limit_per_minute: int = 30

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"

    chroma_collection: str = "ned_prospectus_chunks"

    @field_validator("embedding_provider")
    @classmethod
    def normalize_embedding_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"local", "fake"}:
            raise ValueError("EMBEDDING_PROVIDER must be 'local' or 'fake'.")
        return normalized

    @field_validator("retrieval_mode")
    @classmethod
    def normalize_retrieval_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"vector", "hybrid"}:
            raise ValueError("RETRIEVAL_MODE must be 'vector' or 'hybrid'.")
        return normalized

    @field_validator("retrieval_strict_distance", mode="before")
    @classmethod
    def empty_strict_distance(cls, value):
        return None if value in ("", None) else value

    @field_validator("generation_provider")
    @classmethod
    def normalize_generation_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"groq", "fake"}:
            raise ValueError("GENERATION_PROVIDER must be 'groq' or 'fake'.")
        return normalized

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def registry_path(self) -> Path:
        return self.chroma_dir / self.registry_filename

    def ensure_directories(self) -> None:
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
