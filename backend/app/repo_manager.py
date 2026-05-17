from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.config import Settings


@dataclass(slots=True)
class PreparedRepo:
    repo_id: str
    name: str
    source: str
    source_type: str
    root_path: Path


class RepoManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def prepare(self, source: str, source_type: str | None, display_name: str | None, reindex: bool) -> PreparedRepo:
        inferred_type = source_type or infer_source_type(source)
        if inferred_type == "url":
            return self._prepare_url(source, display_name, reindex)
        return self._prepare_path(source, display_name)

    def _prepare_url(self, source: str, display_name: str | None, reindex: bool) -> PreparedRepo:
        repo_id = stable_repo_id(source)
        name = display_name or repo_name_from_source(source)
        target = self.settings.repos_dir / repo_id
        if target.exists() and reindex:
            raise RuntimeError(
                "Reindex with reclone is intentionally conservative. Remove the cloned repo under data/repos manually."
            )
        if not target.exists():
            subprocess.run(
                ["git", "clone", "--depth", "1", source, str(target)],
                check=True,
                capture_output=True,
                text=True,
            )
        return PreparedRepo(repo_id=repo_id, name=name, source=source, source_type="url", root_path=target)

    def _prepare_path(self, source: str, display_name: str | None) -> PreparedRepo:
        root = Path(source).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Repository path does not exist or is not a directory: {source}")
        repo_id = stable_repo_id(str(root))
        name = display_name or root.name
        return PreparedRepo(repo_id=repo_id, name=name, source=str(root), source_type="path", root_path=root)


def infer_source_type(source: str) -> str:
    parsed = urlparse(source)
    return "url" if parsed.scheme in {"http", "https", "ssh", "git"} or source.endswith(".git") else "path"


def stable_repo_id(source: str) -> str:
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]


def repo_name_from_source(source: str) -> str:
    parsed = urlparse(source)
    candidate = Path(parsed.path or source).name
    return candidate.removesuffix(".git") or "repository"

