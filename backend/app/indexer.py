from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.embeddings import OllamaEmbeddings
from app.ingestion.chunker import TreeSitterChunker, supported_language
from app.ingestion.dependencies import resolve_dependency
from app.repo_manager import PreparedRepo
from app.storage import SQLiteStore
from app.vector_store import VectorStore


EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".next",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
}


@dataclass(slots=True)
class IndexStats:
    files_indexed: int
    chunks_indexed: int
    symbols_indexed: int


class RepoIndexer:
    def __init__(
        self,
        settings: Settings,
        store: SQLiteStore,
        vector_store: VectorStore,
        embeddings: OllamaEmbeddings,
    ):
        self.settings = settings
        self.store = store
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.chunker = TreeSitterChunker()

    def index(self, repo: PreparedRepo) -> IndexStats:
        self.store.clear_repo_index(repo.repo_id)
        self.vector_store.reset_repo(repo.repo_id)
        files = list(iter_supported_files(repo.root_path, self.settings.max_file_bytes))
        known_files = {relative for relative, _ in files}
        all_chunks = []
        symbols_count = 0

        for relative_path, absolute_path in files:
            content = absolute_path.read_text("utf-8", errors="replace")
            chunks = self.chunker.chunk_file(relative_path, content)
            imports = sorted({item for chunk in chunks for item in chunk.imports})
            dependencies = sorted(
                {
                    resolved
                    for item in imports
                    if (resolved := resolve_dependency(item, relative_path, known_files)) is not None
                }
            )
            language = supported_language(absolute_path) or "text"
            self.store.add_file(repo.repo_id, relative_path, language, content, imports, dependencies)
            for import_ref in imports:
                self.store.add_dependency_edge(
                    repo.repo_id,
                    relative_path,
                    import_ref,
                    resolve_dependency(import_ref, relative_path, known_files),
                )
            for chunk in chunks:
                chunk_id = stable_chunk_id(repo.repo_id, chunk.file_path, chunk.start_line, chunk.end_line)
                self.store.add_chunk(
                    chunk_id,
                    repo.repo_id,
                    chunk.file_path,
                    chunk.language,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.text,
                    chunk.symbols_defined,
                    dependencies,
                )
                for symbol in chunk.symbols_defined:
                    symbols_count += 1
                    self.store.add_symbol(
                        repo.repo_id,
                        symbol,
                        "symbol",
                        chunk.file_path,
                        chunk.start_line,
                        chunk.end_line,
                    )
                all_chunks.append((chunk_id, chunk, dependencies))

        vectors = self.embeddings.embed_many([chunk.text for _, chunk, _ in all_chunks])
        self.vector_store.upsert(
            [
                (
                    chunk_id,
                    embedding.vector,
                    {
                        "chunk_id": chunk_id,
                        "repo_id": repo.repo_id,
                        "file_path": chunk.file_path,
                        "language": chunk.language,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "symbols": chunk.symbols_defined,
                        "dependencies": dependencies,
                        "embedding_provider": embedding.provider,
                    },
                )
                for (chunk_id, chunk, dependencies), embedding in zip(all_chunks, vectors)
            ]
        )
        return IndexStats(files_indexed=len(files), chunks_indexed=len(all_chunks), symbols_indexed=symbols_count)


def iter_supported_files(root: Path, max_file_bytes: int) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if supported_language(path) is None:
            continue
        if path.stat().st_size > max_file_bytes:
            continue
        relative = path.relative_to(root).as_posix()
        files.append((relative, path))
    return sorted(files)


def stable_chunk_id(repo_id: str, path: str, start_line: int, end_line: int) -> str:
    raw = f"{repo_id}:{path}:{start_line}:{end_line}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

