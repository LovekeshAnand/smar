"""
context_layer/config.py
=======================
Configuration and defaults for the SMAR Context Layer.
Supports multi-user scoping, token budgeting, and hybrid retrieval weights.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ContextConfig:
    # Storage settings
    db_path: str = field(
        default_factory=lambda: os.getenv(
            "SMAR_DB_PATH",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "smar_memory.db")
        )
    )
    
    # Default user & agent identities
    default_user_id: str = "default_user"
    assistant_name: str = "SMAR"
    
    # Hybrid Retrieval weights
    graph_weight: float = 0.55
    vector_weight: float = 0.35
    recency_weight: float = 0.10
    
    # Retrieval limits
    top_k_triples: int = 8
    top_k_vectors: int = 4
    vector_similarity_threshold: float = 0.20
    max_context_tokens: int = 350
    
    # Engine provider: 'native' | 'mem0' | 'auto'
    provider: str = os.getenv("SMAR_MEMORY_PROVIDER", "auto")
    
    # LLM inference endpoint for Mem0 / local embedding
    epsilon_api_base: str = os.getenv("EPSILON_API_BASE", "http://127.0.0.1:8088/v1")
    epsilon_model: str = "qwen2.5-coder-7b-instruct"
