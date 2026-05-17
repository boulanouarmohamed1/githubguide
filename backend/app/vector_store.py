from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.config import Settings


class VectorStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._qdrant = None
        self._qdrant_models = None
        self._vector_size: int | None = None
        try:
            from qdrant_client import QdrantClient, models

            self._qdrant = QdrantClient(path=str(settings.qdrant_dir))
            self._qdrant_models = models
        except Exception:
            self.settings.vector_fallback_path.parent.mkdir(parents=True, exist_ok=True)

    def reset_repo(self, repo_id: str) -> None:
        if self._qdrant is not None:
            collections = self._qdrant.get_collections().collections
            exists = any(collection.name == self.settings.vector_collection for collection in collections)
            if not exists:
                return
            self._qdrant.delete(
                collection_name=self.settings.vector_collection,
                points_selector=self._qdrant_models.FilterSelector(
                    filter=self._qdrant_models.Filter(
                        must=[
                            self._qdrant_models.FieldCondition(
                                key="repo_id",
                                match=self._qdrant_models.MatchValue(value=repo_id),
                            )
                        ]
                    )
                ),
            )
            return
        records = [record for record in self._load_fallback() if record["payload"]["repo_id"] != repo_id]
        self._save_fallback(records)

    def upsert(self, vectors: list[tuple[str, list[float], dict[str, Any]]]) -> None:
        if not vectors:
            return
        if self._qdrant is not None:
            self._ensure_collection(len(vectors[0][1]))
            points = [
                self._qdrant_models.PointStruct(id=stable_point_id(point_id), vector=vector, payload=payload)
                for point_id, vector, payload in vectors
            ]
            self._qdrant.upsert(collection_name=self.settings.vector_collection, points=points)
            return
        records = self._load_fallback()
        by_id = {record["id"]: record for record in records}
        for point_id, vector, payload in vectors:
            by_id[point_id] = {"id": point_id, "vector": vector, "payload": payload}
        self._save_fallback(list(by_id.values()))

    def search(self, repo_id: str, query_vector: list[float], limit: int) -> list[dict]:
        if self._qdrant is not None:
            self._ensure_collection(len(query_vector))
            results = self._qdrant.query_points(
                collection_name=self.settings.vector_collection,
                query=query_vector,
                query_filter=self._qdrant_models.Filter(
                    must=[
                        self._qdrant_models.FieldCondition(
                            key="repo_id",
                            match=self._qdrant_models.MatchValue(value=repo_id),
                        )
                    ]
                ),
                limit=limit,
            )
            return [
                {"score": point.score, "payload": point.payload}
                for point in getattr(results, "points", results)
            ]
        scored = []
        for record in self._load_fallback():
            if record["payload"]["repo_id"] != repo_id:
                continue
            scored.append(
                {
                    "score": cosine(query_vector, record["vector"]),
                    "payload": record["payload"],
                }
            )
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]

    def close(self) -> None:
        if self._qdrant is not None:
            self._qdrant.close()

    def _ensure_collection(self, vector_size: int) -> None:
        if self._qdrant is None:
            return
        if self._vector_size == vector_size:
            return
        collections = self._qdrant.get_collections().collections
        exists = any(collection.name == self.settings.vector_collection for collection in collections)
        if exists:
            collection = self._qdrant.get_collection(collection_name=self.settings.vector_collection)
            existing_size = collection_vector_size(collection)
            if existing_size == vector_size:
                self._vector_size = vector_size
                return
            self._qdrant.delete_collection(collection_name=self.settings.vector_collection)

        if not exists or existing_size != vector_size:
            self._qdrant.create_collection(
                collection_name=self.settings.vector_collection,
                vectors_config=self._qdrant_models.VectorParams(
                    size=vector_size,
                    distance=self._qdrant_models.Distance.COSINE,
                ),
            )
        self._vector_size = vector_size

    def _load_fallback(self) -> list[dict]:
        if not self.settings.vector_fallback_path.exists():
            return []
        return json.loads(self.settings.vector_fallback_path.read_text("utf-8"))

    def _save_fallback(self, records: list[dict]) -> None:
        self.settings.vector_fallback_path.write_text(json.dumps(records), encoding="utf-8")


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (left_norm * right_norm)


def stable_point_id(value: str) -> str:
    import hashlib

    digest = hashlib.md5(value.encode("utf-8")).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def collection_vector_size(collection: Any) -> int | None:
    vectors = collection.config.params.vectors
    if hasattr(vectors, "size"):
        return vectors.size
    if isinstance(vectors, dict):
        first_vector = next(iter(vectors.values()), None)
        if hasattr(first_vector, "size"):
            return first_vector.size
    return None
