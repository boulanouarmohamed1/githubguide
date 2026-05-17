# GithubGuide

GithubGuide is a local oriented system for onboarding into unfamiliar GitHub repositories. It indexes source code on your machine, retrieves relevant chunks with citations, and answers questions through a traceable agent workflow backed by a local LLM.

## Problem

Contributing to or reviewing a large repository is slow when the codebase is unfamiliar. Typical friction includes:

- Understanding where execution starts and how requests or jobs flow through modules
- Finding the files and symbols that implement a feature without reading the entire tree
- Verifying answers from generic chat tools that do not cite file paths and line ranges
- Sending proprietary code to hosted APIs during exploration

GithubGuide addresses this by cloning or mounting a repository locally, building a searchable index with structural metadata, and running an agent that plans searches, gathers evidence, and responds with citations and optional diagrams. All inference and storage can remain on your machine.

## How It Works

1. **Ingest** — Provide a public GitHub URL or a path to a local checkout. The backend clones or copies the repository under `data/repos/`.
2. **Index** — Supported source files are parsed into function- and class-level chunks. Symbols, imports, and dependency hints are stored in SQLite; embeddings are stored in Qdrant (or a JSON fallback when Qdrant is unavailable).
3. **Query** — Ask questions in one of three modes. The agent searches the index, records a trace of relevant locations, and synthesizes an answer with file and line citations. Diagram mode can emit Mermaid sequence diagrams.

Supported languages during indexing: Python (`.py`), JavaScript (`.js`, `.jsx`), and TypeScript (`.ts`, `.tsx`). Common vendor and build directories are excluded automatically.

## Features

- FastAPI backend with repository ingestion, Tree-sitter-oriented chunking, dependency metadata, and vector search
- LangGraph-style agent loop (architect, explorer, summarizer) with a sequential fallback when LangGraph is unavailable
- Next.js UI for ingesting repositories, browsing the file tree, inspecting hotspots, asking questions, and rendering Mermaid output
- Ollama integration for local chat and embeddings, with optional deterministic fallbacks for tests and development
- Qdrant local-mode storage when `qdrant-client` is installed, with a JSON vector fallback otherwise
- Persistent runtime data under `data/` (repositories, SQLite metadata, vector store)

## Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer
- [Ollama](https://ollama.com/) for local chat and embeddings (recommended for normal use)
- Git (for ingesting remote repositories)

## Project Layout

```text
githubguide/
  backend/          FastAPI app, indexer, agent, tests
  frontend/         Next.js UI
  data/             Local repos, SQLite DB, Qdrant data (created at runtime)
  .env.example      Shared environment template
```

## Configuration

Copy the example environment file and adjust as needed:

```bash
cp .env.example backend/.env
```

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUBGUIDE_APP_NAME` | Application title | `GithubGuide` |
| `GITHUBGUIDE_DATA_DIR` | Root for repos, SQLite, and vectors | `../data` |
| `GITHUBGUIDE_OLLAMA_BASE_URL` | Ollama API base URL | `http://localhost:11434` |
| `GITHUBGUIDE_CHAT_MODEL` | Chat model name in Ollama | `qwen2.5-coder:3b` (in example) |
| `GITHUBGUIDE_EMBED_MODEL` | Embedding model in Ollama | `nomic-embed-text` |
| `GITHUBGUIDE_ALLOW_FALLBACK_EMBEDDINGS` | Use deterministic embeddings when Ollama is unavailable | `false` in example |
| `GITHUBGUIDE_ALLOW_FALLBACK_CHAT` | Use deterministic chat when Ollama is unavailable | `false` in example |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend API base URL | `http://localhost:8000` |

Set `GITHUBGUIDE_ALLOW_FALLBACK_*` to `true` only for offline tests or first-run development without Ollama.

## Quick Start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The UI expects the API at `http://localhost:8000` unless you override `NEXT_PUBLIC_API_BASE_URL`.

Verify the backend with:

```bash
curl http://localhost:8000/health
```

## Local LLM Setup

Install Ollama, then pull the recommended models:

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5-coder:3b
```

`qwen2.5-coder:3b` is a practical default on Apple Silicon with limited memory. If you have more RAM, set `GITHUBGUIDE_CHAT_MODEL` to a larger model you have already pulled, for example `llama3.1:8b`.

If `ollama serve` reports `address already in use`, Ollama is already running. Confirm available models with:

```bash
curl http://127.0.0.1:11434/api/tags
```

## Usage

1. Start the backend and frontend.
2. In the sidebar, enter a **GitHub URL** or **local path** and ingest the repository. Use `auto`, `url`, or `path` to control how the source string is interpreted.
3. Select the repository from the list and browse the file tree or hotspot list.
4. Choose a query mode and submit a question:
   - **overview** — High-level structure and main components
   - **trace** — Execution paths, handlers, and related symbols (default)
   - **diagram** — Answer plus a Mermaid sequence diagram when applicable
5. Review the answer, citations, trace steps, and any rendered diagram.

On small local models, the first ingest and query for a medium repository may take 30–90 seconds while the system clones, chunks files, generates embeddings, and runs the chat model.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health and configured models |
| `POST` | `/api/repos/ingest` | Clone or register a repository and index it |
| `GET` | `/api/repos` | List ingested repositories |
| `GET` | `/api/repos/{repo_id}/tree` | File tree for a repository |
| `GET` | `/api/repos/{repo_id}/files/content?path=...` | File contents |
| `GET` | `/api/repos/{repo_id}/hotspots` | Frequently referenced symbols and files |
| `POST` | `/api/repos/{repo_id}/query` | Run the agent (`query`, `mode` in JSON body) |

Example ingest request body:

```json
{
  "source": "https://github.com/org/example.git",
  "source_type": "url",
  "reindex": false
}
```

Example query request body:

```json
{
  "query": "How does authentication work?",
  "mode": "trace"
}
```

## Data Storage

Runtime artifacts are written under `GITHUBGUIDE_DATA_DIR` (default: `data/`):

- `data/repos/` — Cloned or copied repositories
- `data/githubguide.sqlite3` — Repository metadata, file tree, chunks, and symbols
- `data/qdrant/` — Vector index (when using Qdrant)
- `data/vectors.json` — Vector fallback (when Qdrant is not used)

This directory is gitignored. 

## Tests

```bash
cd backend
source .venv/bin/activate
python3 -m pytest
```

Tests use in-memory or temporary stores and may enable embedding and chat fallbacks independent of your `.env` settings.

## Manual Test

1. Start the backend and frontend.
2. Open [http://localhost:3000](http://localhost:3000).
3. Ingest a public repository, for example:

```text
https://github.com/boulanouarmohamed1/ResearchPaperAgent.git
```

4. Wait for indexing to complete, then ask: `Give me an overview of the project structure.` in **overview** mode.
5. Confirm that the response includes citations with file paths and line ranges.

## Limitations

- Indexing is limited to Python and JavaScript/TypeScript sources; other languages are skipped.
- Quality and latency depend on the Ollama models you configure.
- Very large files are skipped when they exceed `GITHUBGUIDE_MAX_FILE_BYTES` (default 750 KB).
- Renaming the vector collection or SQLite filename after indexing existing data requires re-ingesting repositories or migrating stored data manually.
