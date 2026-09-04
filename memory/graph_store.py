"""
memory/graph_store.py
=====================
Persistent Knowledge Graph (KG) store for SMAR.
Stores structured relational facts as triples: (subject, predicate, object).
Supports upsert-by-similarity to prevent graph bloating.
"""

import sqlite3
import json
import time
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("smar.memory.graph_store")


class KnowledgeGraphStore:
    def __init__(self, db_path: str = "data/smar_memory.db"):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # Entities table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kg_entities (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT,
                    attributes_json TEXT DEFAULT '{}',
                    created_at REAL,
                    updated_at REAL
                )
            """)
            # Triples (Subject - Predicate - Object)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kg_triples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    metadata_json TEXT DEFAULT '{}',
                    created_at REAL,
                    updated_at REAL,
                    UNIQUE(subject, predicate, object)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_sub ON kg_triples(subject)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_obj ON kg_triples(object)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_triples_pred ON kg_triples(predicate)")
            conn.commit()

    def upsert_triple(
        self,
        subject: str,
        predicate: str,
        object_val: str,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Upserts a relational triple.
        If a relation between subject and predicate already exists with a different object
        (e.g., 'Sweta' 'LivesIn' 'Bangalore' updated to 'Sweta' 'LivesIn' 'Delhi'),
        it can update the existing fact or update the timestamp.
        """
        now = time.time()
        sub_norm = subject.strip()
        pred_norm = predicate.strip()
        obj_norm = object_val.strip()
        meta_str = json.dumps(metadata or {})

        with self._get_conn() as conn:
            cursor = conn.cursor()
            for ent in [sub_norm, obj_norm]:
                cursor.execute("""
                    INSERT INTO kg_entities (id, name, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at, name = excluded.name
                """, (ent.lower(), ent, now, now))


            # Check if an existing triple with same (subject, predicate) exists
            cursor.execute("""
                SELECT id, object FROM kg_triples 
                WHERE LOWER(subject) = LOWER(?) AND LOWER(predicate) = LOWER(?)
            """, (sub_norm, pred_norm))
            existing = cursor.fetchall()

            # If exact triple exists, bump updated_at
            cursor.execute("""
                INSERT INTO kg_triples (subject, predicate, object, confidence, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject, predicate, object) DO UPDATE SET
                    confidence = ?,
                    metadata_json = ?,
                    updated_at = ?
            """, (sub_norm, pred_norm, obj_norm, confidence, meta_str, now, now, confidence, meta_str, now))
            
            conn.commit()
            return True

    def query_entity_relations(self, entity_name: str) -> List[Dict[str, Any]]:
        """Find all facts where entity is either subject or object."""
        norm = entity_name.strip()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT subject, predicate, object, confidence, updated_at
                FROM kg_triples
                WHERE LOWER(subject) = LOWER(?) OR LOWER(object) = LOWER(?)
                ORDER BY updated_at DESC
            """, (norm, norm))
            rows = cursor.fetchall()
            return [
                {
                    "subject": r["subject"],
                    "predicate": r["predicate"],
                    "object": r["object"],
                    "confidence": r["confidence"],
                    "updated_at": r["updated_at"]
                }
                for r in rows
            ]

    def query_subgraph_for_entities(self, entities: List[str]) -> List[str]:
        """
        Returns a list of human-readable fact strings for the given set of entities.
        E.g. ["Sweta Likes Python programming language", "Sweta LocatedIn Bangalore"]
        """
        facts = []
        seen = set()
        for ent in entities:
            relations = self.query_entity_relations(ent)
            for r in relations:
                triple_repr = f"{r['subject']} --[{r['predicate']}]--> {r['object']}"
                if triple_repr not in seen:
                    seen.add(triple_repr)
                    facts.append(triple_repr)
        return facts

    def list_all_triples(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT subject, predicate, object, confidence, updated_at
                FROM kg_triples
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]
