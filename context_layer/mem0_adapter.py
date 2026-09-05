"""
context_layer/mem0_adapter.py
=============================
Adapter integrating the open-source Mem0 (mem0ai) library into the SMAR Context Layer.
Provides seamless graph + vector memory when Mem0 is installed, with automatic
fallback to NativeHybridStore if Mem0 is unavailable.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from context_layer.base import BaseMemoryStore
from context_layer.config import ContextConfig
from context_layer.native_hybrid import NativeHybridStore

logger = logging.getLogger("smar.context_layer.mem0_adapter")


class Mem0StoreAdapter(BaseMemoryStore):
    """
    Adapter implementing BaseMemoryStore on top of mem0ai.
    Falls back gracefully to NativeHybridStore if mem0 package is not installed.
    """

    def __init__(self, config: Optional[ContextConfig] = None):
        self.config = config or ContextConfig()
        self.fallback = NativeHybridStore(db_path=self.config.db_path)
        self.mem0_client = None
        self._init_mem0()

    def _init_mem0(self) -> None:
        try:
            from mem0 import Memory
            # Configure Mem0 with local SQLite or Qdrant vector backend if available
            custom_config = {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "path": self.config.db_path.replace(".db", "_qdrant")
                    }
                },
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": self.config.epsilon_model,
                        "openai_base_url": self.config.epsilon_api_base,
                        "api_key": "not-needed"
                    }
                }
            }
            try:
                self.mem0_client = Memory.from_config(custom_config)
                logger.info("Mem0 (mem0ai) client successfully initialized with local vector store.")
            except Exception as e:
                logger.warning(f"Mem0 custom configuration failed ({e}), attempting default Memory():")
                self.mem0_client = Memory()
        except ImportError:
            logger.info("mem0 package is not installed. Running on built-in NativeHybridStore.")
            self.mem0_client = None
        except Exception as e:
            logger.warning(f"Could not initialize Mem0: {e}. Defaulting to NativeHybridStore.")
            self.mem0_client = None

    def upsert_triple(
        self,
        user_id: str,
        subject: str,
        predicate: str,
        object_val: str,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        # Native store handles exact subject-predicate-object relational graph
        res = self.fallback.upsert_triple(user_id, subject, predicate, object_val, confidence, metadata)
        if self.mem0_client:
            try:
                fact_str = f"{subject} {predicate} {object_val}"
                self.mem0_client.add(fact_str, user_id=user_id, metadata=metadata)
            except Exception as e:
                logger.debug(f"Mem0 add triple error: {e}")
        return res

    def query_triples_for_entities(
        self,
        user_id: str,
        entities: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        return self.fallback.query_triples_for_entities(user_id, entities, limit)

    def get_all_triples(
        self,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        return self.fallback.get_all_triples(user_id, limit)

    def upsert_semantic(
        self,
        user_id: str,
        text: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.85
    ) -> Tuple[int, bool]:
        res = self.fallback.upsert_semantic(user_id, text, category, metadata, similarity_threshold)
        if self.mem0_client:
            try:
                self.mem0_client.add(text, user_id=user_id, metadata={"category": category, **(metadata or {})})
            except Exception as e:
                logger.debug(f"Mem0 add semantic error: {e}")
        return res

    def search_semantic(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.20
    ) -> List[Dict[str, Any]]:
        if self.mem0_client:
            try:
                mem0_results = self.mem0_client.search(query, user_id=user_id, limit=top_k)
                if mem0_results and isinstance(mem0_results, list):
                    formatted = []
                    for r in mem0_results:
                        formatted.append({
                            "id": r.get("id", 0),
                            "content": r.get("memory", r.get("text", "")),
                            "category": "mem0",
                            "similarity": r.get("score", 0.9),
                            "access_count": 1,
                            "updated_at": r.get("updated_at", 0)
                        })
                    return formatted
            except Exception as e:
                logger.debug(f"Mem0 search error ({e}), falling back to native vector search.")

        return self.fallback.search_semantic(user_id, query, top_k, min_similarity)

    def get_all_semantic(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        return self.fallback.get_all_semantic(user_id, limit)

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        return self.fallback.get_user_profile(user_id)

    def save_turn(self, user_id: str, role: str, content: str) -> None:
        self.fallback.save_turn(user_id, role, content)

    def get_recent_turns(self, user_id: str, limit: int = 6) -> List[Dict[str, str]]:
        return self.fallback.get_recent_turns(user_id, limit)

    def get_first_turn(self, user_id: str) -> Optional[Dict[str, str]]:
        return self.fallback.get_first_turn(user_id)

    def get_all_user_questions(self, user_id: str, limit: int = 20) -> List[str]:
        return self.fallback.get_all_user_questions(user_id, limit)

    def get_memory_graph(self, user_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        return self.fallback.get_memory_graph(user_id, limit)


