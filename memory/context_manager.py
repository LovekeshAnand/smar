"""
memory/context_manager.py
=========================
Context Layer coordinator for SMAR.
Coordinates the dual-store memory (Knowledge Graph + Vector Store),
executes hybrid retrieval, and runs self-updating ingestion.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from .graph_store import KnowledgeGraphStore
from .vector_store import VectorStore
from .extractor import FactExtractor

logger = logging.getLogger("smar.memory.context_manager")


class ContextManager:
    def __init__(self, db_path: Optional[str] = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db = db_path or os.getenv("SMAR_DB_PATH", os.path.join(base_dir, "data", "smar_memory.db"))
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(os.path.abspath(db)), exist_ok=True)
        
        self.kg = KnowledgeGraphStore(db_path=db)
        self.vectors = VectorStore(db_path=db)
        self.extractor = FactExtractor(default_user="User")

    def retrieve_context(self, user_query: str) -> str:
        """
        Hybrid retrieval combining precise KG relational facts and fuzzy Vector recall.
        Returns a formatted context block to inject into the LLM system prompt.
        """
        # 1. Knowledge Graph precision lookup
        entities = self.extractor.extract_potential_entities(user_query)
        kg_facts = self.kg.query_subgraph_for_entities(entities)

        # 2. Semantic Vector search
        vector_matches = self.vectors.search(user_query, top_k=3, min_similarity=0.20)

        if not kg_facts and not vector_matches:
            return ""

        context_lines = []

        if kg_facts:
            context_lines.append("Relational Facts (Knowledge Graph):")
            for fact in kg_facts:
                context_lines.append(f"  • {fact}")

        if vector_matches:
            context_lines.append("Semantic Context (Vector Memory):")
            for item in vector_matches:
                context_lines.append(f"  • {item['content']}")

        return "\n".join(context_lines)

    def ingest_turn(self, user_text: str, assistant_reply: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts new facts and updates both Knowledge Graph and Vector Store.
        Uses upsert-by-similarity to keep memory dense and avoid redundant growth.
        """
        # 1. Extract and upsert relational triples into KG
        extracted_facts = self.extractor.extract_facts(user_text)
        ingested_triples = []
        for sub, pred, obj in extracted_facts:
            self.kg.upsert_triple(sub, pred, obj)
            ingested_triples.append(f"{sub} --[{pred}]--> {obj}")

        # 2. Upsert semantic concept into Vector Store
        vector_id, was_updated = self.vectors.upsert_by_similarity(
            text=user_text,
            category="conversation",
            similarity_threshold=0.85
        )

        return {
            "triples": ingested_triples,
            "vector_id": vector_id,
            "vector_updated": was_updated
        }
