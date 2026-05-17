from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.models import FileContentResponse, FileNode, Hotspot, RepoSummary


class SQLiteStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                create table if not exists repos (
                    repo_id text primary key,
                    name text not null,
                    source text not null,
                    source_type text not null,
                    root_path text not null,
                    indexed_at text,
                    status text not null,
                    error text
                );
                create table if not exists files (
                    repo_id text not null,
                    path text not null,
                    language text,
                    content text not null,
                    imports_json text not null,
                    dependencies_json text not null,
                    line_count integer not null,
                    primary key (repo_id, path)
                );
                create table if not exists chunks (
                    chunk_id text primary key,
                    repo_id text not null,
                    file_path text not null,
                    language text not null,
                    start_line integer not null,
                    end_line integer not null,
                    text text not null,
                    symbols_json text not null,
                    dependencies_json text not null
                );
                create table if not exists symbols (
                    repo_id text not null,
                    symbol_name text not null,
                    symbol_kind text not null,
                    file_path text not null,
                    start_line integer not null,
                    end_line integer not null,
                    primary key (repo_id, symbol_name, file_path, start_line)
                );
                create table if not exists dependency_edges (
                    repo_id text not null,
                    source_path text not null,
                    target_ref text not null,
                    resolved_path text,
                    primary key (repo_id, source_path, target_ref)
                );
                """
            )

    def upsert_repo(
        self,
        repo_id: str,
        name: str,
        source: str,
        source_type: str,
        root_path: str,
        status: str = "indexed",
        error: str | None = None,
    ) -> RepoSummary:
        indexed_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                """
                insert into repos (repo_id, name, source, source_type, root_path, indexed_at, status, error)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(repo_id) do update set
                    name=excluded.name,
                    source=excluded.source,
                    source_type=excluded.source_type,
                    root_path=excluded.root_path,
                    indexed_at=excluded.indexed_at,
                    status=excluded.status,
                    error=excluded.error
                """,
                (repo_id, name, source, source_type, root_path, indexed_at, status, error),
            )
        return self.get_repo(repo_id)

    def get_repo(self, repo_id: str) -> RepoSummary:
        with self.connect() as db:
            row = db.execute("select * from repos where repo_id = ?", (repo_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown repo_id: {repo_id}")
        return repo_from_row(row)

    def list_repos(self) -> list[RepoSummary]:
        with self.connect() as db:
            rows = db.execute("select * from repos order by indexed_at desc").fetchall()
        return [repo_from_row(row) for row in rows]

    def clear_repo_index(self, repo_id: str) -> None:
        with self.connect() as db:
            for table in ("files", "chunks", "symbols", "dependency_edges"):
                db.execute(f"delete from {table} where repo_id = ?", (repo_id,))

    def add_file(
        self,
        repo_id: str,
        path: str,
        language: str,
        content: str,
        imports: list[str],
        dependencies: list[str],
    ) -> None:
        with self.connect() as db:
            db.execute(
                """
                insert or replace into files
                    (repo_id, path, language, content, imports_json, dependencies_json, line_count)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_id,
                    path,
                    language,
                    content,
                    json.dumps(imports),
                    json.dumps(dependencies),
                    max(1, len(content.splitlines())),
                ),
            )

    def add_chunk(
        self,
        chunk_id: str,
        repo_id: str,
        file_path: str,
        language: str,
        start_line: int,
        end_line: int,
        text: str,
        symbols: list[str],
        dependencies: list[str],
    ) -> None:
        with self.connect() as db:
            db.execute(
                """
                insert or replace into chunks
                    (chunk_id, repo_id, file_path, language, start_line, end_line, text, symbols_json, dependencies_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    repo_id,
                    file_path,
                    language,
                    start_line,
                    end_line,
                    text,
                    json.dumps(symbols),
                    json.dumps(dependencies),
                ),
            )

    def add_symbol(
        self,
        repo_id: str,
        symbol_name: str,
        symbol_kind: str,
        file_path: str,
        start_line: int,
        end_line: int,
    ) -> None:
        with self.connect() as db:
            db.execute(
                """
                insert or replace into symbols
                    (repo_id, symbol_name, symbol_kind, file_path, start_line, end_line)
                values (?, ?, ?, ?, ?, ?)
                """,
                (repo_id, symbol_name, symbol_kind, file_path, start_line, end_line),
            )

    def add_dependency_edge(
        self,
        repo_id: str,
        source_path: str,
        target_ref: str,
        resolved_path: str | None,
    ) -> None:
        with self.connect() as db:
            db.execute(
                """
                insert or replace into dependency_edges
                    (repo_id, source_path, target_ref, resolved_path)
                values (?, ?, ?, ?)
                """,
                (repo_id, source_path, target_ref, resolved_path),
            )

    def get_file(self, repo_id: str, path: str) -> FileContentResponse:
        with self.connect() as db:
            row = db.execute(
                "select path, language, content, line_count from files where repo_id = ? and path = ?",
                (repo_id, path),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown file: {path}")
        return FileContentResponse(
            path=row["path"],
            language=row["language"],
            content=row["content"],
            line_count=row["line_count"],
        )

    def list_files(self, repo_id: str, directory: str = "") -> list[dict]:
        directory = directory.strip("/")
        with self.connect() as db:
            rows = db.execute(
                "select path, language from files where repo_id = ? order by path",
                (repo_id,),
            ).fetchall()
        files = []
        for row in rows:
            path = row["path"]
            if directory and not path.startswith(f"{directory}/"):
                continue
            files.append({"path": path, "language": row["language"]})
        return files

    def get_tree(self, repo_id: str) -> list[FileNode]:
        files = self.list_files(repo_id)
        root: dict[str, dict] = {}
        languages: dict[str, str | None] = {}
        for file_info in files:
            parts = file_info["path"].split("/")
            cursor = root
            for part in parts:
                cursor = cursor.setdefault(part, {})
            languages[file_info["path"]] = file_info["language"]
        return build_nodes(root, "", languages)

    def find_symbol(self, repo_id: str, symbol_name: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                """
                select * from symbols
                where repo_id = ? and lower(symbol_name) = lower(?)
                order by file_path, start_line
                """,
                (repo_id, symbol_name),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_chunk(self, chunk_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("select * from chunks where chunk_id = ?", (chunk_id,)).fetchone()
        return decode_chunk_row(row) if row else None

    def get_chunks_for_repo(self, repo_id: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("select * from chunks where repo_id = ?", (repo_id,)).fetchall()
        return [decode_chunk_row(row) for row in rows]

    def hotspots(self, repo_id: str) -> list[Hotspot]:
        with self.connect() as db:
            files = db.execute("select path, imports_json from files where repo_id = ?", (repo_id,)).fetchall()
            symbols = db.execute(
                "select file_path, count(*) as count from symbols where repo_id = ? group by file_path",
                (repo_id,),
            ).fetchall()
            imported_by = db.execute(
                """
                select resolved_path as file_path, count(*) as count
                from dependency_edges
                where repo_id = ? and resolved_path is not null
                group by resolved_path
                """,
                (repo_id,),
            ).fetchall()
        symbol_counts = {row["file_path"]: row["count"] for row in symbols}
        imported_by_counts = {row["file_path"]: row["count"] for row in imported_by}
        hotspots = []
        for row in files:
            imports_count = len(json.loads(row["imports_json"]))
            imported_by_count = imported_by_counts.get(row["path"], 0)
            symbols_count = symbol_counts.get(row["path"], 0)
            score = imports_count + imported_by_count * 2 + symbols_count
            hotspots.append(
                Hotspot(
                    file_path=row["path"],
                    imports_count=imports_count,
                    imported_by_count=imported_by_count,
                    symbols_count=symbols_count,
                    score=score,
                )
            )
        return sorted(hotspots, key=lambda item: item.score, reverse=True)[:20]


def repo_from_row(row: sqlite3.Row) -> RepoSummary:
    indexed_at = datetime.fromisoformat(row["indexed_at"]) if row["indexed_at"] else None
    return RepoSummary(
        repo_id=row["repo_id"],
        name=row["name"],
        source=row["source"],
        source_type=row["source_type"],
        root_path=row["root_path"],
        indexed_at=indexed_at,
        status=row["status"],
        error=row["error"],
    )


def decode_chunk_row(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["symbols"] = json.loads(data.pop("symbols_json"))
    data["dependencies"] = json.loads(data.pop("dependencies_json"))
    return data


def build_nodes(tree: dict, prefix: str, languages: dict[str, str | None]) -> list[FileNode]:
    nodes: list[FileNode] = []
    for name, children in sorted(tree.items()):
        path = f"{prefix}/{name}".strip("/")
        if children:
            nodes.append(FileNode(path=path, kind="directory", children=build_nodes(children, path, languages)))
        else:
            nodes.append(FileNode(path=path, kind="file", language=languages.get(path)))
    return nodes

