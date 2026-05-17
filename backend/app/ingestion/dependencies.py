from __future__ import annotations

import posixpath
from pathlib import Path


def resolve_dependency(import_ref: str, source_file: str, known_files: set[str]) -> str | None:
    if import_ref.startswith("."):
        return resolve_relative_import(import_ref, source_file, known_files)
    dotted = import_ref.replace(".", "/")
    candidates = [
        f"{dotted}.py",
        f"{dotted}.ts",
        f"{dotted}.tsx",
        f"{dotted}.js",
        f"{dotted}.jsx",
        f"{dotted}/__init__.py",
        f"{dotted}/index.ts",
        f"{dotted}/index.tsx",
        f"{dotted}/index.js",
        f"{dotted}/index.jsx",
    ]
    return next((candidate for candidate in candidates if candidate in known_files), None)


def resolve_relative_import(import_ref: str, source_file: str, known_files: set[str]) -> str | None:
    if "/" in import_ref:
        stem = posixpath.normpath(posixpath.join(posixpath.dirname(source_file), import_ref))
        candidates = [
            stem,
            f"{stem}.py",
            f"{stem}.ts",
            f"{stem}.tsx",
            f"{stem}.js",
            f"{stem}.jsx",
            f"{stem}/__init__.py",
            f"{stem}/index.ts",
            f"{stem}/index.tsx",
            f"{stem}/index.js",
            f"{stem}/index.jsx",
        ]
        return next((candidate for candidate in candidates if candidate in known_files), None)

    source_dir = Path(source_file).parent
    depth = len(import_ref) - len(import_ref.lstrip("."))
    tail = import_ref.lstrip(".").replace(".", "/")
    base = source_dir
    for _ in range(max(0, depth - 1)):
        base = base.parent
    stem = (base / tail).as_posix() if tail else base.as_posix()
    candidates = [
        f"{stem}.py",
        f"{stem}.ts",
        f"{stem}.tsx",
        f"{stem}.js",
        f"{stem}.jsx",
        f"{stem}/__init__.py",
        f"{stem}/index.ts",
        f"{stem}/index.tsx",
        f"{stem}/index.js",
        f"{stem}/index.jsx",
    ]
    return next((candidate for candidate in candidates if candidate in known_files), None)
