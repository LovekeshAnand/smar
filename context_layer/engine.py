"""
context_layer/engine.py
=======================
Master Context Layer Engine for SMAR.
Integrates Knowledge Formation, Hybrid RAG Retrieval, Multi-User Memory Storage,
and Dynamic Prompt Composition into a cohesive, high-performance facade.
"""

import logging
from typing import Dict, Any, List, Optional

from context_layer.config import ContextConfig
from context_layer.base import BaseMemoryStore
from context_layer.native_hybrid import NativeHybridStore
from context_layer.mem0_adapter import Mem0StoreAdapter
from context_layer.knowledge_formation import KnowledgeFormationPipeline
from context_layer.retriever import HybridRetriever
from context_layer.prompt_composer import PromptComposer

logger = logging.getLogger("smar.context_layer.engine")


class ContextLayerEngine:
    """
    Unified entry point for SMAR Context Layer.
    Orchestrates ingestion, hybrid retrieval, and prompt generation for each conversation turn.
    """

    def __init__(self, config: Optional[ContextConfig] = None):
        self.config = config or ContextConfig()

        # Initialize storage provider
        if self.config.provider == "mem0":
            self.store: BaseMemoryStore = Mem0StoreAdapter(self.config)
        elif self.config.provider == "native":
            self.store = NativeHybridStore(db_path=self.config.db_path)
        else:
            # 'auto': Try Mem0StoreAdapter (which falls back seamlessly to Native)
            self.store = Mem0StoreAdapter(self.config)

        # Initialize sub-pipelines
        self.pipeline = KnowledgeFormationPipeline(assistant_name=self.config.assistant_name)
        self.retriever = HybridRetriever(self.store, self.config, self.pipeline)
        self.composer = PromptComposer(self.config)

        logger.info(f"ContextLayerEngine initialized (provider: {self.config.provider})")

    def process_user_turn(
        self,
        user_id: str,
        user_text: str,
        language_hint: str = "en-IN",
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes an incoming user message:
          1. Extracts and commits relational facts to the user's graph
          2. Commits semantic memory chunk if text contains substantive information
          3. Executes hybrid RAG retrieval for relevant facts and semantic memories
          4. Composes a tailored, identity-protected system prompt
        """
        user_clean = user_id.strip() or self.config.default_user_id

        # 1. Fact Extraction & Relational Ingestion
        extracted_facts = self.pipeline.extract_facts(user_text, user_id=user_clean)
        for fact in extracted_facts:
            self.store.upsert_triple(
                user_id=user_clean,
                subject=fact["subject"],
                predicate=fact["predicate"],
                object_val=fact["object"],
                confidence=fact.get("confidence", 1.0)
            )

        # 2. Semantic Memory Ingestion (for substantive statements)
        if self.pipeline.should_store_semantic(user_text):
            self.store.upsert_semantic(
                user_id=user_clean,
                text=user_text,
                category="conversation"
            )

        # 3. Hybrid Retrieval (Facts + Semantic Memories)
        retrieval_result = self.retriever.retrieve_context(
            user_id=user_clean,
            query=user_text
        )

        # 4. Fetch Recent Dialogue Turns (Short-term conversational memory buffer)
        recent_turns = self.store.get_recent_turns(user_clean, limit=6)

        # 5. Dynamic Prompt Composition
        system_prompt = self.composer.compose_system_prompt(
            retrieval_result=retrieval_result,
            language_hint=language_hint,
            custom_instructions=custom_instructions
        )

        return {
            "user_id": user_clean,
            "system_prompt": system_prompt,
            "retrieval": retrieval_result,
            "extracted_facts": extracted_facts,
            "recent_turns": recent_turns
        }

    def add_explicit_memory(
        self,
        user_id: str,
        text: str,
        category: str = "explicit",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Manually records an explicit note or memory for a user."""
        user_clean = user_id.strip() or self.config.default_user_id
        mem_id, is_update = self.store.upsert_semantic(
            user_id=user_clean,
            text=text,
            category=category,
            metadata=metadata
        )
        # Also attempt relational extraction on the explicit memory
        facts = self.pipeline.extract_facts(text, user_id=user_clean)
        for fact in facts:
            self.store.upsert_triple(
                user_id=user_clean,
                subject=fact["subject"],
                predicate=fact["predicate"],
                object_val=fact["object"]
            )
        return {"id": mem_id, "is_update": is_update, "extracted_facts": facts}

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Fetches the synthesized user profile."""
        user_clean = user_id.strip() or self.config.default_user_id
        return self.store.get_user_profile(user_clean)

    def get_memory_graph(self, user_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """Returns nodes and edges for the memory visualization UI."""
        triples = self.store.get_all_triples(user_id=user_id, limit=limit)
        nodes = {}
        edges = []

        for t in triples:
            sub = t["subject"]
            obj = t["object"]
            pred = t["predicate"]

            if sub not in nodes:
                nodes[sub] = {"id": sub, "label": sub, "category": "entity"}
            if obj not in nodes:
                nodes[obj] = {"id": obj, "label": obj, "category": "entity"}

            edges.append({
                "id": f"{sub}_{pred}_{obj}_{t.get('id', '')}",
                "source": sub,
                "target": obj,
                "label": pred,
                "confidence": t.get("confidence", 1.0)
            })

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "total_triples": len(triples)
        }
