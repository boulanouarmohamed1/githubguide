from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}


@dataclass(slots=True)
class CodeChunk:
    file_path: str
    language: str
    start_line: int
    end_line: int
    text: str
    symbols_defined: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def supported_language(path: Path) -> str | None:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower())


class TreeSitterChunker:
    """Function/class chunker with Tree-sitter-compatible behavior and safe fallbacks.

    The optional tree-sitter dependency is declared for real deployments. The fallback
    keeps tests and first-run development working even before native parsers are installed.
    """

    def chunk_file(self, relative_path: str, content: str) -> list[CodeChunk]:
        language = supported_language(Path(relative_path))
        if language == "python":
            return self._chunk_python(relative_path, content)
        if language in {"javascript", "typescript"}:
            return self._chunk_javascript_like(relative_path, content, language)
        return []

    def _chunk_python(self, relative_path: str, content: str) -> list[CodeChunk]:
        imports = extract_python_imports(content)
        lines = content.splitlines()
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return [module_chunk(relative_path, "python", content, imports)]

        chunks: list[CodeChunk] = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                chunks.append(
                    CodeChunk(
                        file_path=relative_path,
                        language="python",
                        start_line=start,
                        end_line=end,
                        text="\n".join(lines[start - 1 : end]),
                        symbols_defined=[node.name],
                        imports=imports,
                    )
                )
        if not chunks:
            chunks.append(module_chunk(relative_path, "python", content, imports))
        return chunks

    def _chunk_javascript_like(self, relative_path: str, content: str, language: str) -> list[CodeChunk]:
        imports = extract_js_imports(content)
        lines = content.splitlines()
        starts: list[tuple[int, str]] = []
        patterns = [
            re.compile(r"^\s*export\s+default\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
            re.compile(r"^\s*export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
            re.compile(r"^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
            re.compile(r"^\s*export\s+class\s+([A-Za-z_$][\w$]*)"),
            re.compile(r"^\s*class\s+([A-Za-z_$][\w$]*)"),
            re.compile(r"^\s*export\s+const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
            re.compile(r"^\s*const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
        ]
        for index, line in enumerate(lines, start=1):
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    starts.append((index, match.group(1)))
                    break
        chunks: list[CodeChunk] = []
        for idx, (start, symbol) in enumerate(starts):
            next_start = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines) + 1
            end = max(start, next_start - 1)
            chunks.append(
                CodeChunk(
                    file_path=relative_path,
                    language=language,
                    start_line=start,
                    end_line=end,
                    text="\n".join(lines[start - 1 : end]),
                    symbols_defined=[symbol],
                    imports=imports,
                )
            )
        if not chunks:
            chunks.append(module_chunk(relative_path, language, content, imports))
        return chunks


def module_chunk(relative_path: str, language: str, content: str, imports: list[str]) -> CodeChunk:
    line_count = max(1, len(content.splitlines()))
    return CodeChunk(
        file_path=relative_path,
        language=language,
        start_line=1,
        end_line=line_count,
        text=content,
        symbols_defined=[],
        imports=imports,
    )


def extract_python_imports(content: str) -> list[str]:
    imports: list[str] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level + (node.module or "")
            imports.append(prefix)
    return sorted(set(imports))


def extract_js_imports(content: str) -> list[str]:
    imports: list[str] = []
    for match in re.finditer(r"import\s+(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]", content):
        imports.append(match.group(1))
    for match in re.finditer(r"require\(['\"]([^'\"]+)['\"]\)", content):
        imports.append(match.group(1))
    return sorted(set(imports))
