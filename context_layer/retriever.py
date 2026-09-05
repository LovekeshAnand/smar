"""
context_layer/retriever.py
==========================
Hybrid RAG Retriever for SMAR Context Layer.
Combines Knowledge Graph relational triples and Semantic Vector chunks,
computes weighted fusion scores with recency decay, and enforces strict token budgets.
"""

import time
import math
import logging
from typing import List, Dict, Any, Optional

from context_layer.base import BaseMemoryStore
from context_layer.config import ContextConfig
from context_layer.knowledge_formation import KnowledgeFormationPipeline

logger = logging.getLogger("smar.context_layer.retriever")


class HybridRetriever:
    """
    Retrieves and synthesizes relevant context for a user turn
    across relational graph triples and semantic vector nodes.
    """

    def __init__(
        self,
        store: BaseMemoryStore,
        config: Optional[ContextConfig] = None,
        formation_pipeline: Optional[KnowledgeFormationPipeline] = None
    ):
        self.store = store
        self.config = config or ContextConfig()
        self.pipeline = formation_pipeline or KnowledgeFormationPipeline(assistant_name=self.config.assistant_name)

    def _estimate_tokens(self, text: str) -> int:
        """Heuristic token estimator: ~4 characters per token."""
        return max(1, len(text) // 4)

    def retrieve_context(
        self,
        user_id: str,
        query: str,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes hybrid retrieval scoped to user_id.
        Returns a dict containing:
          - structured_facts: List of formatted triple strings
          - semantic_memories: List of retrieved semantic strings
          - user_profile: Structured user attributes dict
          - estimated_tokens: Total tokens consumed
        """
        budget = max_tokens or self.config.max_context_tokens
        user_clean = user_id.strip() or self.config.default_user_id

        # 1. Fetch user profile (always included first in budget)
        profile = self.store.get_user_profile(user_clean)

        # 2. Extract salient entities from the query + user reference
        query_entities = self.pipeline.extract_entities(query)
        # Always include user's id and resolved name if known
        search_entities = list(query_entities)
        if user_clean not in search_entities:
            search_entities.append(user_clean)
        if profile.get("name") and profile["name"] not in search_entities:
            search_entities.append(profile["name"])

        # 3. Retrieve relational triples from graph
        triples = self.store.query_triples_for_entities(
            user_id=user_clean,
            entities=search_entities,
            limit=self.config.top_k_triples
        )

        # 4. Retrieve semantic memory chunks
        vectors = self.store.search_semantic(
            user_id=user_clean,
            query=query,
            top_k=self.config.top_k_vectors,
            min_similarity=self.config.vector_similarity_threshold
        )

        # 5. Score & Rank Graph Triples
        now = time.time()
        scored_triples = []
        for t in triples:
            # Recency decay (half-life of 7 days ~ 604800s)
            age_days = (now - t.get("updated_at", now)) / 86400.0
            recency_score = math.exp(-0.1 * min(age_days, 30.0))
            score = (
                self.config.graph_weight * t.get("confidence", 1.0) +
                self.config.recency_weight * recency_score
            )
            triple_str = f"{t['subject']} -> {t['predicate']} -> {t['object']}"
            scored_triples.append((score, triple_str))

        scored_triples.sort(key=lambda x: x[0], reverse=True)

        # 6. Score & Rank Semantic Chunks
        scored_vectors = []
        for v in vectors:
            age_days = (now - v.get("updated_at", now)) / 86400.0
            recency_score = math.exp(-0.1 * min(age_days, 30.0))
            score = (
                self.config.vector_weight * v.get("similarity", 0.5) +
                self.config.recency_weight * recency_score
            )
            scored_vectors.append((score, v["content"]))

        scored_vectors.sort(key=lambda x: x[0], reverse=True)

        # 7. Assemble within token budget
        selected_facts: List[str] = []
        selected_semantic: List[str] = []
        current_tokens = 0

        # Profile tokens
        profile_parts = []
        if profile.get("name"):
            profile_parts.append(f"Name: {profile['name']}")
        if profile.get("location"):
            profile_parts.append(f"Location: {profile['location']}")
        if profile.get("profession"):
            profile_parts.append(f"Profession: {profile['profession']}")
        if profile.get("email"):
            profile_parts.append(f"Email: {profile['email']}")
        for pref in profile.get("preferences", []):
            profile_parts.append(pref)

        profile_text = " | ".join(profile_parts)
        if profile_text:
            current_tokens += self._estimate_tokens(profile_text)

        # Add top graph triples
        for _, fact in scored_triples:
            tokens = self._estimate_tokens(fact)
            if current_tokens + tokens <= budget:
                selected_facts.append(fact)
                current_tokens += tokens
            else:
                break

        # Add top semantic memories
        for _, chunk in scored_vectors:
            tokens = self._estimate_tokens(chunk)
            if current_tokens + tokens <= budget:
                selected_semantic.append(chunk)
                current_tokens += tokens
            else:
                break

        # 8. Check for session conversation recall queries
        lower_q = query.lower()
        is_history_query = any(k in lower_q for k in [
            "first question", "1st question", "earlier", "previous question",
            "what did i ask", "what i asked", "past question", "first thing",
            "what was the first", "what was the 1st"
        ])
        session_history = {}
        if is_history_query:
            if hasattr(self.store, "get_first_turn"):
                first_turn = self.store.get_first_turn(user_clean)
                if first_turn:
                    session_history["first_question"] = first_turn.get("content")
            if hasattr(self.store, "get_all_user_questions"):
                all_q = self.store.get_all_user_questions(user_clean, limit=10)
                if all_q:
                    session_history["all_questions"] = all_q

        return {
            "user_id": user_clean,
            "user_profile": profile,
            "structured_facts": selected_facts,
            "semantic_memories": selected_semantic,
            "session_history": session_history,
            "estimated_tokens": current_tokens
        }

