from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SourceType = Literal["url", "path"]
QueryMode = Literal["overview", "trace", "diagram"]


class RepoIngestRequest(BaseModel):
    source: str = Field(..., min_length=1)
    source_type: SourceType | None = None
    display_name: str | None = None
    reindex: bool = False


class RepoSummary(BaseModel):
    repo_id: str
    name: str
    source: str
    source_type: SourceType
    root_path: str
    indexed_at: datetime | None = None
    status: str = "indexed"
    error: str | None = None


class IngestResponse(BaseModel):
    repo: RepoSummary
    files_indexed: int
    chunks_indexed: int
    symbols_indexed: int


class FileNode(BaseModel):
    path: str
    kind: Literal["file", "directory"]
    language: str | None = None
    children: list["FileNode"] = Field(default_factory=list)


class FileContentResponse(BaseModel):
    path: str
    content: str
    language: str | None = None
    line_count: int


class Citation(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    label: str | None = None


class TraceStep(BaseModel):
    file_path: str
    symbol: str | None = None
    line_range: tuple[int, int]
    summary: str


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    mode: QueryMode = "trace"


class QueryResponse(BaseModel):
    answer: str
    mode: QueryMode
    trace: list[TraceStep] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    mermaid: str | None = None
    search_history: list[str] = Field(default_factory=list)


class Hotspot(BaseModel):
    file_path: str
    imports_count: int
    imported_by_count: int
    symbols_count: int
    score: int

