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
from .read_models import ReadModelManager
from .cache import HotDataCacheManager, TieredHotCache, InMemoryLRUCache, hot_cache
from .service import StructuredDataService
from .sync_engine import UniversalDataSyncEngine
from .multi_table_manager import MultiTableWarehouseManager
from .schema_introspector import SchemaIntrospector

__all__ = [
    "InventoryItem",
    "ValidationResult",
    "ETLBatchResult",
    "InventoryDatabaseManager",
    "InventoryETLPipeline",
    "KiranaInventoryDataGenerator",
    "ReadModelManager",
    "HotDataCacheManager",
    "TieredHotCache",
    "InMemoryLRUCache",
    "hot_cache",
    "StructuredDataService",
    "UniversalDataSyncEngine",
    "MultiTableWarehouseManager",
    "SchemaIntrospector",
]
