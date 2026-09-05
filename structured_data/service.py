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

    STATIC_FIELDS = {
        "item_id", "barcode", "canonical_name", "normalized_name",
        "category", "brand", "unit_of_measure", "hsn_code", "created_at"
    }

    VOLATILE_FIELDS = {
        "quantity", "unit_price", "cost_price", "reorder_level",
        "is_active", "updated_at"
    }

    # --- ITEM LOOKUP (CACHE-ASIDE STRATEGY) ---
    def get_item(self, item_id: str, force_live_stock: bool = False) -> Optional[Dict[str, Any]]:
        """
        Retrieve inventory item details by Primary Key item_id.
        
        Cache-Aside Flow:
            1. If force_live_stock is True:
               - Fetches cached static attributes (1h TTL)
               - Directly queries Primary DB for real-time quantity/price (0 stale risk)
               - Combines both dictionaries.
            2. If force_live_stock is False:
               - Cache lookup (`smar:item:full:{item_id}`)
               - On HIT -> return cached data
               - On MISS -> query Primary Database (Source of Truth)
               - Populate Cache with volatile TTL policy (15s)
               - Return result
        """
        if not item_id:
            return None

        if force_live_stock:
            static_data = self.get_item_static(item_id)
            if not static_data:
                return None
            volatile_data = self.get_item_volatile(item_id, use_cache=False)
            if not volatile_data:
                return None
            combined = dict(static_data)
            combined.update(volatile_data)
            return combined

        key = self.cache.get_key_full_item(item_id)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Cache MISS: Query Primary Database (Source of Truth)
        item = self.db.get_item_by_id(item_id)
        if item:
            self.cache.set(key, item, ttl_seconds=HotDataCacheManager.TTL_VOLATILE_ITEM)

        return item

    def get_item_static(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve only static immutable item metadata (name, category, brand, UOM, HSN).
        Safe for long-duration caching (3,600 sec / 1 Hour TTL).
        """
        if not item_id:
            return None

        key = self.cache.get_key_static_item(item_id)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Cache MISS: Query Primary DB
        item = self.db.get_item_by_id(item_id)
        if not item:
            return None

        static_dict = {k: v for k, v in item.items() if k in self.STATIC_FIELDS}
        self.cache.set(key, static_dict, ttl_seconds=HotDataCacheManager.TTL_STATIC_ITEM)
        return static_dict

    def get_item_volatile(self, item_id: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Retrieve volatile stateful item fields (quantity, unit_price, cost_price, reorder_level).
        Uses short TTL (15 sec) or direct DB bypass to prevent serving stale stock.
        """
        if not item_id:
            return None

        key = self.cache.get_key_volatile_item(item_id)
        if use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                return cached

        # Query Primary DB directly
        item = self.db.get_item_by_id(item_id)
        if not item:
            return None

        volatile_dict = {k: v for k, v in item.items() if k in self.VOLATILE_FIELDS}
        if use_cache:
            self.cache.set(key, volatile_dict, ttl_seconds=HotDataCacheManager.TTL_VOLATILE_ITEM)
        return volatile_dict

    def get_current_inventory_info(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Convenience service method for voice assistant queries:
        Retrieves real-time stock quantity, selling price, and reorder status.
        """
        return self.get_item(item_id, force_live_stock=True)

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

    def get_all_category_summaries(self) -> List[Dict[str, Any]]:
        """
        Retrieve all category summaries from the Materialized View.
        """
        return self.read_models.get_all_category_summaries()

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

    # --- CACHE INTERFACES FOR SMART DATA LAYER ---
    def cache_lookup(self, key: str) -> Optional[Any]:
        """Direct cache lookup interface."""
        return self.cache.get(key)

    def cache_populate(self, key: str, value: Any, ttl_seconds: float) -> None:
        """Direct cache populate interface."""
        self.cache.set(key, value, ttl_seconds=ttl_seconds)

    def invalidate_item(self, item_id: str, barcode: Optional[str] = None, category: Optional[str] = None) -> None:
        """Invalidates all cached entries for an item."""
        self.cache.invalidate_item(item_id=item_id, barcode=barcode, category=category)

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
