from pathlib import Path

from app.agent.graph import GithubGuideAgent
from app.config import Settings
from app.embeddings import OllamaEmbeddings
from app.indexer import RepoIndexer
from app.llm import OllamaChat
from app.repo_manager import PreparedRepo
from app.retrieval.tools import CodebaseTools
from app.storage import SQLiteStore
from app.vector_store import VectorStore


def make_stack(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path / "data",
        allow_fallback_embeddings=True,
        allow_fallback_chat=True,
        max_search_results=6,
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.qdrant_dir.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(settings.sqlite_path)
    vector_store = VectorStore(settings)
    embeddings = OllamaEmbeddings(settings)
    return settings, store, vector_store, embeddings


def test_indexer_stores_symbols_and_hotspots(tmp_path):
    settings, store, vector_store, embeddings = make_stack(tmp_path)
    fixture = Path(__file__).parent / "fixtures" / "sample_repo"
    repo = PreparedRepo("fixture", "sample", str(fixture), "path", fixture)

    stats = RepoIndexer(settings, store, vector_store, embeddings).index(repo)
    store.upsert_repo(repo.repo_id, repo.name, repo.source, repo.source_type, str(repo.root_path))

    assert stats.files_indexed >= 5
    assert store.find_symbol("fixture", "PaymentService")
    assert any(item.file_path == "services/payment_service.py" for item in store.hotspots("fixture"))


def test_tools_and_agent_return_traceable_answer(tmp_path):
    settings, store, vector_store, embeddings = make_stack(tmp_path)
    fixture = Path(__file__).parent / "fixtures" / "sample_repo"
    repo = PreparedRepo("fixture", "sample", str(fixture), "path", fixture)
    RepoIndexer(settings, store, vector_store, embeddings).index(repo)
    store.upsert_repo(repo.repo_id, repo.name, repo.source, repo.source_type, str(repo.root_path))

    tools = CodebaseTools("fixture", settings, store, vector_store, embeddings)
    results = tools.search_codebase("payment authorization transaction")

    assert results
    assert tools.get_symbol_definition("PaymentService")

    agent = GithubGuideAgent(settings, store, tools, OllamaChat(settings))
    response = agent.run("How does payment authorization work?", "trace")

    assert response.trace
    assert response.citations
    assert "retrieved evidence" in response.answer or "payment" in response.answer.lower()


def test_agent_generates_mermaid(tmp_path):
    settings, store, vector_store, embeddings = make_stack(tmp_path)
    fixture = Path(__file__).parent / "fixtures" / "sample_repo"
    repo = PreparedRepo("fixture", "sample", str(fixture), "path", fixture)
    RepoIndexer(settings, store, vector_store, embeddings).index(repo)
    store.upsert_repo(repo.repo_id, repo.name, repo.source, repo.source_type, str(repo.root_path))

    tools = CodebaseTools("fixture", settings, store, vector_store, embeddings)
    agent = GithubGuideAgent(settings, store, tools, OllamaChat(settings))
    response = agent.run("Visualize user registration flow", "diagram")

    assert response.mermaid
    assert response.mermaid.startswith("sequenceDiagram")

