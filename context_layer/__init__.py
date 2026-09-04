"""
context_layer
=============
Multi-User Context Layer for SMAR.
Combines Knowledge Graph, Semantic Vector Store, Hybrid RAG,
and Dynamic Prompt Composition.
"""

from context_layer.config import ContextConfig
from context_layer.base import BaseMemoryStore
from context_layer.native_hybrid import NativeHybridStore
from context_layer.mem0_adapter import Mem0StoreAdapter
from context_layer.knowledge_formation import KnowledgeFormationPipeline
from context_layer.retriever import HybridRetriever
from context_layer.prompt_composer import PromptComposer
from context_layer.engine import ContextLayerEngine

__all__ = [
    "ContextConfig",
    "BaseMemoryStore",
    "NativeHybridStore",
    "Mem0StoreAdapter",
    "KnowledgeFormationPipeline",
    "HybridRetriever",
    "PromptComposer",
    "ContextLayerEngine"
]
