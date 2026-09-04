"""
memory/vector_store.py
======================
Semantic Vector Store for SMAR with self-updating upsert-by-similarity.
Avoids unbounded memory growth by merging similar memory nodes.
"""

import sqlite3
import json
import time
import math
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("smar.memory.vector_store")


def _compute_bow_embedding(text: str, dim: int = 256) -> List[float]:
    """
    Lightweight, zero-dependency normalized hashing vectorizer for semantic text recall.
    Uses subword hashing to ensure words with similar roots cluster together.
    """
    vec = [0.0] * dim
    words = text.lower().replace(".", " ").replace(",", " ").replace("!", " ").split()
    if not words:
        return vec

    for w in words:
        # Add word hash
        h = abs(hash(w)) % dim
        vec[h] += 1.0
        # Add 3-gram char hashes for fuzzy similarity
        if len(w) >= 3:
            for i in range(len(w) - 2):
                tri = w[i:i+3]
                h_tri = abs(hash(tri)) % dim
                vec[h_tri] += 0.5

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    return sum(a * b for a, b in zip(v1, v2))


class VectorStore:
    def __init__(self, db_path: str = "data/smar_memory.db", dim: int = 256):
        self.db_path = db_path
        self.dim = dim
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    access_count INTEGER DEFAULT 1,
                    metadata_json TEXT DEFAULT '{}',
                    created_at REAL,
                    updated_at REAL
                )
            """)
            conn.commit()

    def upsert_by_similarity(
        self,
        text: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.85
    ) -> Tuple[int, bool]:
        """
        Upsert-by-similarity (Section 8 Architecture):
        If an existing memory node has similarity >= threshold, updates its content and
        bumps its timestamp/count rather than duplicating it.
        Returns (memory_id, was_updated).
        """
        text_clean = text.strip()
        if not text_clean:
            return -1, False

        new_vec = _compute_bow_embedding(text_clean, dim=self.dim)
        now = time.time()
        meta = metadata or {}

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, content, embedding_json, access_count, metadata_json FROM semantic_memories")
            rows = cursor.fetchall()

            best_sim = -1.0
            best_id = None
            best_count = 0
            best_meta = {}

            for r in rows:
                try:
                    stored_vec = json.loads(r["embedding_json"])
                    sim = _cosine_similarity(new_vec, stored_vec)
                    if sim > best_sim:
                        best_sim = sim
                        best_id = r["id"]
                        best_count = r["access_count"]
                        try:
                            best_meta = json.loads(r["metadata_json"])
                        except Exception:
                            best_meta = {}
                except Exception:
                    continue

            # Check if threshold matched -> UPDATE existing node
            if best_sim >= similarity_threshold and best_id is not None:
                best_meta.update(meta)
                cursor.execute("""
                    UPDATE semantic_memories
                    SET content = ?,
                        embedding_json = ?,
                        access_count = ?,
                        metadata_json = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    text_clean,
                    json.dumps(new_vec),
                    best_count + 1,
                    json.dumps(best_meta),
                    now,
                    best_id
                ))
                conn.commit()
                logger.info(f"Upserted memory node #{best_id} with similarity {best_sim:.2f}")
                return best_id, True

            # Otherwise -> INSERT new memory node
            cursor.execute("""
                INSERT INTO semantic_memories (content, embedding_json, category, access_count, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """, (
                text_clean,
                json.dumps(new_vec),
                category,
                json.dumps(meta),
                now,
                now
            ))
            conn.commit()
            new_id = cursor.lastrowid
            logger.info(f"Inserted new memory node #{new_id}")
            return new_id, False

    def search(self, query: str, top_k: int = 3, min_similarity: float = 0.25) -> List[Dict[str, Any]]:
        """
        Search for memory items semantically related to query.
        """
        q_clean = query.strip()
        if not q_clean:
            return []

        q_vec = _compute_bow_embedding(q_clean, dim=self.dim)
        results = []

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, content, embedding_json, category, updated_at FROM semantic_memories")
            for r in cursor.fetchall():
                try:
                    stored_vec = json.loads(r["embedding_json"])
                    sim = _cosine_similarity(q_vec, stored_vec)
                    if sim >= min_similarity:
                        results.append({
                            "id": r["id"],
                            "content": r["content"],
                            "category": r["category"],
                            "similarity": sim,
                            "updated_at": r["updated_at"]
                        })
                except Exception:
                    continue

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
