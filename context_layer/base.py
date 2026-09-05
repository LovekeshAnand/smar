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
    def get_all_semantic(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Returns recent semantic memory chunks."""
        pass

    @abstractmethod
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Synthesizes known key attributes for the specified user (name, email, preferences)."""
        pass

    @abstractmethod
    def save_turn(self, user_id: str, role: str, content: str) -> None:
        """Stores a conversation turn in the user's conversation buffer."""
        pass

    @abstractmethod
    def get_recent_turns(self, user_id: str, limit: int = 6) -> List[Dict[str, str]]:
        """Returns the most recent conversation turns in chronological order."""
        pass

    def get_first_turn(self, user_id: str) -> Optional[Dict[str, str]]:
        """Returns the first user question of the conversation session."""
        return None

    def get_all_user_questions(self, user_id: str, limit: int = 20) -> List[str]:
        """Returns chronological list of user questions from the conversation session."""
        return []


