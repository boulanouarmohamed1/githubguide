from __future__ import annotations

from functools import lru_cache
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except Exception:  # pragma: no cover - lets lightweight tests import without deps
    BaseSettings = object
    SettingsConfigDict = dict


class Settings(BaseSettings):
    app_name: str = "GithubGuide"
    data_dir: Path = Path("../data")
    ollama_base_url: str = "http://localhost:11434"
    chat_model: str = "llama3.1:8b"
    embed_model: str = "nomic-embed-text"
    allow_fallback_embeddings: bool = True
    allow_fallback_chat: bool = True
    max_file_bytes: int = 750_000
    max_search_results: int = 8
    vector_collection: str = "githubguide_chunks"

    model_config = SettingsConfigDict(
        env_prefix="GITHUBGUIDE_",
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    @property
    def repos_dir(self) -> Path:
        return self.data_dir / "repos"

    @property
    def qdrant_dir(self) -> Path:
        return self.data_dir / "qdrant"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "githubguide.sqlite3"

    @property
    def vector_fallback_path(self) -> Path:
        return self.data_dir / "vectors.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.repos_dir.mkdir(parents=True, exist_ok=True)
    settings.qdrant_dir.mkdir(parents=True, exist_ok=True)
    return settings
