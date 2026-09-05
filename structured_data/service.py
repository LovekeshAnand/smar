"""
structured_data/service.py
===========================
Unified Structured Data Service Facade for SMAR v2.
Provides clean service APIs for downstream Smart Data Layer integration
(Intent Classifiers, Entity Extractors, and Cognitive Context engines) by orchestrating
the Cache Layer, Materialized Read Models, and Indexed Primary Database.
"""

import logging
from typing import Optional, Dict, Any, List
from .db import InventoryDatabaseManager
from .read_models import ReadModelManager
from .cache import HotDataCacheManager

logger = logging.getLogger("smar.structured_data.service")


class StructuredDataService:
    """
    Unified Facade providing access to the Structured Data Layer.
    Orchestrates: Cache HIT -> Read Model / Primary DB -> Cache MISS Population -> Invalidation.
    """

    def __init__(
        self,
        db_manager: Optional[InventoryDatabaseManager] = None,
        read_model_manager: Optional[ReadModelManager] = None,
        cache_manager: Optional[HotDataCacheManager] = None
    ):
        self.db = db_manager or InventoryDatabaseManager()
        self.read_models = read_model_manager or ReadModelManager(db_manager=self.db)
        self.cache = cache_manager or HotDataCacheManager()

    # --- ITEM LOOKUP (CACHE-ASIDE STRATEGY) ---
    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve inventory item details by Primary Key item_id.
        
        Cache-Aside Flow:
            1. Cache lookup (`smar:item:full:{item_id}`)
            2. On HIT -> return cached data
            3. On MISS -> query Primary Database
            4. Populate Cache with volatile TTL policy
            5. Return result
        """
        if not item_id:
            return None

        key = self.cache.get_key_full_item(item_id)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Cache MISS: Query Primary Database (Source of Truth)
        item = self.db.get_item_by_id(item_id)
        if item:
            self.cache.set(key, item, ttl_seconds=HotDataCacheManager.TTL_VOLATILE_ITEM)

        return item

    def get_item_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        POS Scanner lookup by barcode string using Cache-Aside.
        """
        if not barcode:
            return None

        key = self.cache.get_key_barcode(barcode)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Cache MISS: Query Primary Database
        item = self.db.get_item_by_barcode(barcode)
        if item:
            self.cache.set(key, item, ttl_seconds=HotDataCacheManager.TTL_BARCODE_LOOKUP)

        return item

    def search_items(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Sub-millisecond Full-Text / Fuzzy item search using SQLite FTS5 index.
        Used by Smart Data Layer during entity resolution and voice matching.
        """
        return self.db.search_full_text(query=query, limit=limit)

    # --- READ MODELS & MATERIALIZED VIEWS ---
    def get_category_summary(self, category: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve category aggregations from Materialized View using Cache-Aside.
        """
        if not category:
            return None

        key = self.cache.get_key_category_summary(category)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Cache MISS: Query Materialized View
        summary = self.read_models.get_category_summary(category)
        if summary:
            self.cache.set(key, summary, ttl_seconds=HotDataCacheManager.TTL_CATEGORY_SUMMARY)

        return summary

    def get_low_stock_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve prioritized reorder alert items from Materialized Read Model.
        """
        key = self.cache.get_key_low_stock()
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Cache MISS: Query Low-Stock Materialized View
        alerts = self.read_models.get_low_stock_alerts(limit=limit)
        if alerts:
            self.cache.set(key, alerts, ttl_seconds=HotDataCacheManager.TTL_LOW_STOCK_LIST)

        return alerts

    # --- MUTATION & IMMEDIATE CACHE INVALIDATION ---
    def update_item_stock_or_price(
        self,
        item_id: str,
        new_quantity: Optional[float] = None,
        new_unit_price: Optional[float] = None
    ) -> bool:
        """
        Mutates volatile stock or price in Primary Database (Source of Truth),
        triggers Materialized View refresh, and selectively invalidates cache entries.
        """
        item = self.db.get_item_by_id(item_id)
        if not item:
            return False

        conn = self.db.get_connection()
        try:
            updates = []
            params = []
            if new_quantity is not None and new_quantity >= 0:
                updates.append("quantity = ?")
                params.append(new_quantity)
            if new_unit_price is not None and new_unit_price > 0:
                updates.append("unit_price = ?")
                params.append(new_unit_price)

            if not updates:
                return False

            updates.append("updated_at = datetime('now')")
            params.append(item_id)

            sql = f"UPDATE inventory_items SET {', '.join(updates)} WHERE item_id = ?"
            conn.execute(sql, tuple(params))
            conn.commit()
        finally:
            conn.close()

        # Refresh Materialized Read Models
        self.read_models.refresh_all_materialized_views()

        # Invalidate Cache Entries for this item
        self.cache.invalidate_item(
            item_id=item_id,
            barcode=item.get("barcode"),
            category=item.get("category")
        )
        logger.info(f"Item '{item_id}' updated in Primary DB and invalidated in Cache Layer.")
        return True
