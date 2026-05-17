# Data directory

Runtime artifacts for GithubGuide. The repository tracks layout and index metadata only; large or machine-local files are gitignored.

| Path | Purpose |
|------|---------|
| `repos/` | Cloned repositories (created on ingest) |
| `githubguide.sqlite3` | Chunk and symbol metadata |
| `qdrant/` | Vector index (local Qdrant storage) |
| `logs/` | Optional application logs |

After cloning, ingest a repository from the UI or API to populate this directory.
