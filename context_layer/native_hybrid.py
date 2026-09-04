"""
context_layer/native_hybrid.py
==============================
Zero-dependency, multi-tenant SQLite Knowledge Graph + Semantic Vector Store.
Implements BaseMemoryStore with user_id scoping, atomic upsert-by-similarity,
subgraph retrieval, and relational contradiction resolution.
"""

import re
import sqlite3
import json
import time
import math
import logging
from typing import List, Dict, Any, Optional, Tuple

from context_layer.base import BaseMemoryStore
from context_layer.config import ContextConfig

logger = logging.getLogger("smar.context_layer.native_hybrid")

# Single-valued predicates where a new object supersedes the old object
SINGLE_VALUED_PREDICATES = {
    "livesin", "currentcity", "location", "worksat", "company", "employer",
    "role", "jobtitle", "title", "name", "primaryemail", "email",
    "phone", "phonenumber", "timezone", "status"
}


def compute_bow_embedding(text: str, dim: int = 256) -> List[float]:
    """
    Lightweight, deterministic normalized hashing vectorizer for semantic text recall.
    Uses word hashes + character 3-grams for morphological and subword clustering.
    """
    vec = [0.0] * dim
    words = text.lower().replace(".", " ").replace(",", " ").replace("!", " ").replace("?", " ").split()
    if not words:
        return vec

    for w in words:
        # Word-level hash
        h = abs(hash(w)) % dim
        vec[h] += 1.0
        # 3-gram char hashes for fuzzy root similarity
        if len(w) >= 3:
            for i in range(len(w) - 2):
                tri = w[i:i + 3]
                h_tri = abs(hash(tri)) % dim
                vec[h_tri] += 0.5

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    return sum(a * b for a, b in zip(v1, v2))


class NativeHybridStore(BaseMemoryStore):
    """
    Production-grade SQLite implementation of BaseMemoryStore.
    Maintains user isolation across entities, triples, and semantic chunks.
    """

    def __init__(self, db_path: Optional[str] = None, dim: int = 256):
        config = ContextConfig()
        self.db_path = db_path or config.db_path
        self.dim = dim
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        """Initializes tables and migrates older schemas if user_id is missing."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 1. kg_entities
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kg_entities (
                    id TEXT NOT NULL,
                    user_id TEXT NOT NULL DEFAULT 'default_user',
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    attributes_json TEXT DEFAULT '{}',
                    created_at REAL,
                    updated_at REAL,
                    PRIMARY KEY(user_id, id)
                )
            """)

            # 2. kg_triples
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kg_triples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'default_user',
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    metadata_json TEXT DEFAULT '{}',
                    created_at REAL,
                    updated_at REAL
                )
            """)

            # 3. semantic_memories
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'default_user',
                    content TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    access_count INTEGER DEFAULT 1,
                    metadata_json TEXT DEFAULT '{}',
                    created_at REAL,
                    updated_at REAL
                )
            """)

            # 4. conversation_turns (multi-turn sliding window buffer)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'default_user',
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL
                )
            """)

            # Ensure user_id column exists if tables were created with earlier schema
            for table in ["kg_entities", "kg_triples", "semantic_memories", "conversation_turns"]:
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [row["name"] for row in cursor.fetchall()]
                if "user_id" not in cols:
                    try:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default_user'")
                    except Exception as e:
                        logger.warning(f"Failed to add user_id column to {table}: {e}")

            # Indexes for low-latency multi-user filtering
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_user_sub ON kg_triples(user_id, subject)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_user_obj ON kg_triples(user_id, object)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_user_pred ON kg_triples(user_id, predicate)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_semantic_user ON semantic_memories(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_turns_user ON conversation_turns(user_id, id)")
            conn.commit()

    def upsert_triple(
        self,
        user_id: str,
        subject: str,
        predicate: str,
        object_val: str,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Upserts a relational fact for a specific user.
        Resolves contradictions for single-valued predicates (e.g. updating location/company).
        """
        now = time.time()
        sub_clean = subject.strip()
        pred_clean = predicate.strip()
        obj_clean = object_val.strip()
        user_clean = user_id.strip() or "default_user"
        meta_str = json.dumps(metadata or {})

        if not sub_clean or not pred_clean or not obj_clean:
            return False

        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Upsert entities safely
            for ent in [sub_clean, obj_clean]:
                ent_id = f"{user_clean}:{ent.lower()}"
                cursor.execute("""
                    SELECT id FROM kg_entities WHERE id = ?
                """, (ent_id,))
                if cursor.fetchone():
                    cursor.execute("""
                        UPDATE kg_entities SET updated_at = ?, name = ?, user_id = ?
                        WHERE id = ?
                    """, (now, ent, user_clean, ent_id))
                else:
                    cursor.execute("""
                        INSERT INTO kg_entities (id, user_id, name, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (ent_id, user_clean, ent, now, now))

            # Contradiction check: single-valued predicates
            pred_key = pred_clean.lower().replace(" ", "").replace("_", "")
            is_single_valued = pred_key in SINGLE_VALUED_PREDICATES

            if is_single_valued:
                cursor.execute("""
                    SELECT id, object FROM kg_triples
                    WHERE user_id = ? AND LOWER(subject) = LOWER(?) AND LOWER(predicate) = LOWER(?)
                """, (user_clean, sub_clean, pred_clean))
                existing = cursor.fetchall()
                if existing:
                    # Update the existing triple to the new object (superseding older fact)
                    row_id = existing[0]["id"]
                    cursor.execute("""
                        UPDATE kg_triples
                        SET object = ?, confidence = ?, metadata_json = ?, updated_at = ?
                        WHERE id = ?
                    """, (obj_clean, confidence, meta_str, now, row_id))
                    conn.commit()
                    return True

            # Multi-valued or new predicate: check exact match
            cursor.execute("""
                SELECT id FROM kg_triples
                WHERE user_id = ? AND LOWER(subject) = LOWER(?) AND LOWER(predicate) = LOWER(?) AND LOWER(object) = LOWER(?)
            """, (user_clean, sub_clean, pred_clean, obj_clean))
            match = cursor.fetchone()

            if match:
                cursor.execute("""
                    UPDATE kg_triples
                    SET confidence = ?, metadata_json = ?, updated_at = ?
                    WHERE id = ?
                """, (confidence, meta_str, now, match["id"]))
            else:
                cursor.execute("""
                    INSERT INTO kg_triples (user_id, subject, predicate, object, confidence, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_clean, sub_clean, pred_clean, obj_clean, confidence, meta_str, now, now))

            conn.commit()
            return True

    def query_triples_for_entities(
        self,
        user_id: str,
        entities: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Traverses 1-hop and 2-hop user-scoped knowledge graph around the target entities.
        """
        user_clean = user_id.strip() or "default_user"
        if not entities:
            return []

        ent_lowers = [e.strip().lower() for e in entities if e.strip()]
        if not ent_lowers:
            return []

        placeholders = ",".join("?" * len(ent_lowers))
        results = []
        seen_ids = set()

        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 1-Hop query
            sql = f"""
                SELECT id, subject, predicate, object, confidence, updated_at
                FROM kg_triples
                WHERE user_id = ? AND (LOWER(subject) IN ({placeholders}) OR LOWER(object) IN ({placeholders}))
                ORDER BY updated_at DESC LIMIT ?
            """
            cursor.execute(sql, [user_clean] + ent_lowers + ent_lowers + [limit])
            rows = cursor.fetchall()

            connected_entities = set()
            for r in rows:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    results.append(dict(r))
                    connected_entities.add(r["subject"].lower())
                    connected_entities.add(r["object"].lower())

            # 2-Hop expansion if budget remains
            remaining = limit - len(results)
            new_entities = list(connected_entities - set(ent_lowers))
            if remaining > 0 and new_entities:
                sub_placeholders = ",".join("?" * len(new_entities))
                sql_2 = f"""
                    SELECT id, subject, predicate, object, confidence, updated_at
                    FROM kg_triples
                    WHERE user_id = ? AND (LOWER(subject) IN ({sub_placeholders}) OR LOWER(object) IN ({sub_placeholders}))
                    ORDER BY updated_at DESC LIMIT ?
                """
                cursor.execute(sql_2, [user_clean] + new_entities + new_entities + [remaining])
                for r in cursor.fetchall():
                    if r["id"] not in seen_ids:
                        seen_ids.add(r["id"])
                        results.append(dict(r))

        return results

    def get_all_triples(
        self,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Returns recent relational facts, optionally filtered by user_id."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("""
                    SELECT id, user_id, subject, predicate, object, confidence, updated_at
                    FROM kg_triples
                    WHERE user_id = ?
                    ORDER BY updated_at DESC LIMIT ?
                """, (user_id.strip(), limit))
            else:
                cursor.execute("""
                    SELECT id, user_id, subject, predicate, object, confidence, updated_at
                    FROM kg_triples
                    ORDER BY updated_at DESC LIMIT ?
                """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def upsert_semantic(
        self,
        user_id: str,
        text: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.85
    ) -> Tuple[int, bool]:
        """
        Upsert-by-similarity for user-scoped semantic memory chunks.
        If an existing chunk has cosine similarity >= similarity_threshold, merges content
        and bumps access count / updated_at rather than duplicating.
        """
        text_clean = text.strip()
        if not text_clean:
            return -1, False

        user_clean = user_id.strip() or "default_user"
        new_vec = compute_bow_embedding(text_clean, dim=self.dim)
        now = time.time()
        meta = metadata or {}

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, content, embedding_json, access_count, metadata_json
                FROM semantic_memories
                WHERE user_id = ?
                ORDER BY updated_at DESC LIMIT 50
            """, (user_clean,))
            candidates = cursor.fetchall()

            best_match_id = None
            best_sim = -1.0

            for cand in candidates:
                cand_vec = json.loads(cand["embedding_json"])
                sim = cosine_similarity(new_vec, cand_vec)
                if sim > best_sim:
                    best_sim = sim
                    best_match_id = cand["id"]

            if best_match_id and best_sim >= similarity_threshold:
                # Merge into existing memory node
                cursor.execute("""
                    UPDATE semantic_memories
                    SET content = ?, embedding_json = ?, access_count = access_count + 1,
                        metadata_json = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                """, (text_clean, json.dumps(new_vec), json.dumps(meta), now, best_match_id, user_clean))
                conn.commit()
                return best_match_id, True

            # Insert as a new memory node
            cursor.execute("""
                INSERT INTO semantic_memories (user_id, content, embedding_json, category, access_count, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            """, (user_clean, text_clean, json.dumps(new_vec), category, json.dumps(meta), now, now))
            row_id = cursor.lastrowid
            conn.commit()
            return row_id, False

    def search_semantic(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.20
    ) -> List[Dict[str, Any]]:
        """Searches user-scoped semantic memory via cosine similarity."""
        query_clean = query.strip()
        if not query_clean:
            return []

        user_clean = user_id.strip() or "default_user"
        q_vec = compute_bow_embedding(query_clean, dim=self.dim)

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, content, category, embedding_json, access_count, updated_at
                FROM semantic_memories
                WHERE user_id = ?
            """, (user_clean,))
            rows = cursor.fetchall()

        q_words = set(w.lower() for w in re.findall(r"\w+", query_clean) if len(w) > 2)

        scored = []
        for r in rows:
            emb = json.loads(r["embedding_json"])
            cos_sim = cosine_similarity(q_vec, emb)
            c_words = set(w.lower() for w in re.findall(r"\w+", r["content"]))
            overlap = len(q_words & c_words) / max(len(q_words), 1) if q_words else 0.0
            # Blended score: cosine similarity + keyword match
            blended = 0.65 * cos_sim + 0.35 * overlap
            if blended >= min_similarity or overlap >= 0.25:
                scored.append({
                    "id": r["id"],
                    "content": r["content"],
                    "category": r["category"],
                    "similarity": round(blended, 4),
                    "access_count": r["access_count"],
                    "updated_at": r["updated_at"]
                })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    def get_all_semantic(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Returns recent semantic memory chunks, optionally filtered by user_id."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT id, user_id, content, category, access_count, updated_at FROM semantic_memories WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                    (user_id.strip(), limit)
                )
            else:
                cursor.execute(
                    "SELECT id, user_id, content, category, access_count, updated_at FROM semantic_memories ORDER BY updated_at DESC LIMIT ?",
                    (limit,)
                )
            return [dict(r) for r in cursor.fetchall()]

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Synthesizes known structured attributes for the specified user."""
        user_clean = user_id.strip() or "default_user"
        profile: Dict[str, Any] = {
            "user_id": user_clean,
            "name": None,
            "email": None,
            "location": None,
            "profession": None,
            "project": None,
            "preferences": []
        }

        with self._get_conn() as conn:
            cursor = conn.cursor()
            # 1. First find if user has a verified Name triple
            cursor.execute("""
                SELECT object FROM kg_triples
                WHERE user_id = ? AND LOWER(predicate) IN ('name', 'named', 'fullname')
                ORDER BY updated_at DESC LIMIT 1
            """, (user_clean,))
            name_row = cursor.fetchone()
            if name_row:
                profile["name"] = name_row["object"]

            subjects = [user_clean.lower(), 'user', 'i', 'me']
            if profile["name"]:
                subjects.append(profile["name"].lower())

            placeholders = ",".join("?" * len(subjects))
            cursor.execute(f"""
                SELECT predicate, object FROM kg_triples
                WHERE user_id = ? AND LOWER(subject) IN ({placeholders})
                ORDER BY updated_at DESC
            """, [user_clean] + subjects)
            rows = cursor.fetchall()

            for r in rows:
                pred = r["predicate"].lower().replace("_", "").replace(" ", "")
                val = r["object"]
                if pred in ("name", "fullname", "username", "named") and not profile["name"]:
                    profile["name"] = val
                elif pred in ("email", "primaryemail", "mail", "hasemail") and not profile["email"]:
                    profile["email"] = val
                elif pred in ("location", "livesin", "currentcity", "city") and not profile["location"]:
                    profile["location"] = val
                elif pred in ("role", "jobtitle", "profession", "worksat", "title", "isa") and not profile["profession"]:
                    profile["profession"] = val
                elif pred in ("building", "workson", "project", "product") and not profile["project"]:
                    profile["project"] = val
                elif pred in ("prefers", "likes", "favorite", "interest", "speaks", "usestechnology", "hasskill"):
                    pref_str = f"{r['predicate']}: {val}"
                    if pref_str not in profile["preferences"]:
                        profile["preferences"].append(pref_str)

        return profile

    def save_turn(self, user_id: str, role: str, content: str) -> None:
        """Stores a conversation turn in the user's conversation buffer."""
        user_clean = user_id.strip() or "default_user"
        content_clean = content.strip()
        if not content_clean:
            return
        now = time.time()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversation_turns (user_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_clean, role, content_clean, now))
            conn.commit()

    def get_recent_turns(self, user_id: str, limit: int = 6) -> List[Dict[str, str]]:
        """Returns the most recent conversation turns in chronological order."""
        user_clean = user_id.strip() or "default_user"
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content FROM conversation_turns
                WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
            """, (user_clean, limit))
            rows = cursor.fetchall()
            ordered = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
            return ordered

