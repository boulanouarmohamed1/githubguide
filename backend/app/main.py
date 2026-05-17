from __future__ import annotations

import atexit

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import GithubGuideAgent
from app.config import get_settings
from app.embeddings import OllamaEmbeddings
from app.indexer import RepoIndexer
from app.llm import OllamaChat
from app.models import (
    FileContentResponse,
    FileNode,
    Hotspot,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    RepoIngestRequest,
    RepoSummary,
)
from app.repo_manager import RepoManager
from app.retrieval.tools import CodebaseTools
from app.storage import SQLiteStore
from app.vector_store import VectorStore


settings = get_settings()
store = SQLiteStore(settings.sqlite_path)
vector_store = VectorStore(settings)
atexit.register(vector_store.close)
embeddings = OllamaEmbeddings(settings)
repo_manager = RepoManager(settings)
indexer = RepoIndexer(settings, store, vector_store, embeddings)
chat = OllamaChat(settings)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "chat_model": settings.chat_model,
        "embed_model": settings.embed_model,
    }


@app.post("/api/repos/ingest", response_model=IngestResponse)
def ingest_repo(request: RepoIngestRequest) -> IngestResponse:
    try:
        prepared = repo_manager.prepare(
            request.source,
            request.source_type,
            request.display_name,
            request.reindex,
        )
        repo = store.upsert_repo(
            prepared.repo_id,
            prepared.name,
            prepared.source,
            prepared.source_type,
            str(prepared.root_path),
            status="indexing",
        )
        stats = indexer.index(prepared)
        repo = store.upsert_repo(
            prepared.repo_id,
            prepared.name,
            prepared.source,
            prepared.source_type,
            str(prepared.root_path),
            status="indexed",
        )
        return IngestResponse(
            repo=repo,
            files_indexed=stats.files_indexed,
            chunks_indexed=stats.chunks_indexed,
            symbols_indexed=stats.symbols_indexed,
        )
    except Exception as exc:
        if "prepared" in locals():
            store.upsert_repo(
                prepared.repo_id,
                prepared.name,
                prepared.source,
                prepared.source_type,
                str(prepared.root_path),
                status="error",
                error=str(exc),
            )
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/repos", response_model=list[RepoSummary])
def list_repos() -> list[RepoSummary]:
    return store.list_repos()


@app.get("/api/repos/{repo_id}/tree", response_model=list[FileNode])
def repo_tree(repo_id: str) -> list[FileNode]:
    ensure_repo(repo_id)
    return store.get_tree(repo_id)


@app.get("/api/repos/{repo_id}/files/content", response_model=FileContentResponse)
def file_content(repo_id: str, path: str = Query(...)) -> FileContentResponse:
    ensure_repo(repo_id)
    try:
        return store.get_file(repo_id, path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/repos/{repo_id}/hotspots", response_model=list[Hotspot])
def hotspots(repo_id: str) -> list[Hotspot]:
    ensure_repo(repo_id)
    return store.hotspots(repo_id)


@app.post("/api/repos/{repo_id}/query", response_model=QueryResponse)
def query_repo(repo_id: str, request: QueryRequest) -> QueryResponse:
    ensure_repo(repo_id)
    tools = CodebaseTools(repo_id, settings, store, vector_store, embeddings)
    agent = GithubGuideAgent(settings, store, tools, chat)
    return agent.run(request.query, request.mode)


def ensure_repo(repo_id: str) -> RepoSummary:
    try:
        return store.get_repo(repo_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
