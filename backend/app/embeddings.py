from __future__ import annotations

import hashlib
import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.config import Settings


class EmbeddingUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class EmbeddingResult:
    vector: list[float]
    provider: str


class OllamaEmbeddings:
    def __init__(self, settings: Settings):
        self.settings = settings

    def embed(self, text: str) -> EmbeddingResult:
        try:
            return EmbeddingResult(
                vector=self._ollama_embed(text),
                provider=f"ollama:{self.settings.embed_model}",
            )
        except Exception as exc:
            if not self.settings.allow_fallback_embeddings:
                raise EmbeddingUnavailable(
                    f"Ollama embeddings unavailable at {self.settings.ollama_base_url}: {exc}"
                ) from exc
            return EmbeddingResult(vector=hash_embedding(text), provider="local-hash")

    def embed_many(self, texts: list[str]) -> list[EmbeddingResult]:
        if not texts:
            return []
        try:
            vectors = self._ollama_embed_many(texts)
            return [
                EmbeddingResult(vector=vector, provider=f"ollama:{self.settings.embed_model}")
                for vector in vectors
            ]
        except Exception as exc:
            if not self.settings.allow_fallback_embeddings:
                raise EmbeddingUnavailable(
                    f"Ollama embeddings unavailable at {self.settings.ollama_base_url}: {exc}"
                ) from exc
            return [EmbeddingResult(vector=hash_embedding(text), provider="local-hash") for text in texts]

    def _ollama_embed(self, text: str) -> list[float]:
        return self._ollama_embed_many([text])[0]

    def _ollama_embed_many(self, texts: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.settings.embed_model, "input": texts}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.settings.ollama_base_url.rstrip('/')}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise EmbeddingUnavailable(str(exc)) from exc
        embeddings = body.get("embeddings")
        if not embeddings:
            raise EmbeddingUnavailable(f"Ollama returned no embeddings: {body}")
        return embeddings


def hash_embedding(text: str, dimensions: int = 384) -> list[float]:
    """Deterministic, local embedding fallback for tests and offline demos."""
    vector = [0.0] * dimensions
    tokens = text.lower().replace("_", " ").replace("-", " ").split()
    if not tokens:
        tokens = [text[:64] or "empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i, byte in enumerate(digest):
            index = (byte + i * 31) % dimensions
            vector[index] += 1.0 if byte % 2 == 0 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]

