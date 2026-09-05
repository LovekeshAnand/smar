"""
Structured Data Layer for SMAR v2
=================================
High-performance deterministic bulk ingestion, ETL pipeline,
primary indexed SQLite database, and entity search for 100,000+ Kirana inventory records.
"""

from .models import InventoryItem, ValidationResult, ETLBatchResult
from .db import InventoryDatabaseManager
from .etl import InventoryETLPipeline
from .generator import KiranaInventoryDataGenerator

__all__ = [
    "InventoryItem",
    "ValidationResult",
    "ETLBatchResult",
    "InventoryDatabaseManager",
    "InventoryETLPipeline",
    "KiranaInventoryDataGenerator",
]
