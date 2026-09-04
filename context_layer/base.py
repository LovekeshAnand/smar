"""
context_layer/base.py
=====================
Abstract base interface for SMAR Context Layer storage providers.
Guarantees strict multi-user scoping across all implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class BaseMemoryStore(ABC):
    """Abstract interface defining the multi-user memory store contract."""

    @abstractmethod
    def upsert_triple(
        self,
        user_id: str,
        subject: str,
        predicate: str,
        object_val: str,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Upserts a relational fact for a specific user."""
        pass

    @abstractmethod
    def query_triples_for_entities(
        self,
        user_id: str,
        entities: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieves user-scoped relational facts involving specified entities."""
        pass

    @abstractmethod
    def get_all_triples(
        self,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Returns recent relational facts for inspection."""
        pass

    @abstractmethod
    def upsert_semantic(
        self,
        user_id: str,
        text: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.85
    ) -> Tuple[int, bool]:
        """Upserts an embedding memory chunk with duplicate coalescing for a specific user."""
        pass

    @abstractmethod
    def search_semantic(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.20
    ) -> List[Dict[str, Any]]:
        """Searches user-scoped semantic memory via similarity ranking."""
        pass

    @abstractmethod
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Synthesizes known key attributes for the specified user (name, email, preferences)."""
        pass
