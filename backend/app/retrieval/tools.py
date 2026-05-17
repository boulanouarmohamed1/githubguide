from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.embeddings import OllamaEmbeddings
from app.storage import SQLiteStore
from app.vector_store import VectorStore


@dataclass(slots=True)
class SearchResult:
    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    symbols: list[str]
    dependencies: list[str]
    text: str
    score: float


class CodebaseTools:
    def __init__(
        self,
        repo_id: str,
        settings: Settings,
        store: SQLiteStore,
        vector_store: VectorStore,
        embeddings: OllamaEmbeddings,
    ):
        self.repo_id = repo_id
        self.settings = settings
        self.store = store
        self.vector_store = vector_store
        self.embeddings = embeddings

    def search_codebase(self, query: str) -> list[SearchResult]:
        """Semantic search via the vector DB."""
        vector = self.embeddings.embed(query).vector
        matches = self.vector_store.search(self.repo_id, vector, self.settings.max_search_results)
        results: list[SearchResult] = []
        for match in matches:
            payload = match["payload"]
            chunk = self.store.get_chunk(payload["chunk_id"])
            if not chunk:
                continue
            results.append(
                SearchResult(
                    chunk_id=payload["chunk_id"],
                    file_path=chunk["file_path"],
                    start_line=chunk["start_line"],
                    end_line=chunk["end_line"],
                    symbols=chunk["symbols"],
                    dependencies=chunk["dependencies"],
                    text=chunk["text"],
                    score=float(match["score"]),
                )
            )
        return results

    def get_file_content(self, path: str) -> str:
        """Reads full file content."""
        return self.store.get_file(self.repo_id, path).content

    def get_symbol_definition(self, symbol_name: str) -> list[SearchResult]:
        """Uses the AST index to find class/function definitions."""
        definitions = self.store.find_symbol(self.repo_id, symbol_name)
        results: list[SearchResult] = []
        for definition in definitions:
            content = self.store.get_file(self.repo_id, definition["file_path"]).content
            lines = content.splitlines()
            start = definition["start_line"]
            end = definition["end_line"]
            text = "\n".join(lines[start - 1 : end])
            results.append(
                SearchResult(
                    chunk_id=f"symbol:{symbol_name}:{definition['file_path']}:{start}",
                    file_path=definition["file_path"],
                    start_line=start,
                    end_line=end,
                    symbols=[symbol_name],
                    dependencies=[],
                    text=text,
                    score=1.0,
                )
            )
        return results

    def list_files(self, directory: str = "") -> list[str]:
        """Shows the file tree for a folder."""
        return [file_info["path"] for file_info in self.store.list_files(self.repo_id, directory)]

