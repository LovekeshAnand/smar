"""
structured_data/read_models.py
==============================
Read Models & Materialized Views Subsystem for SMAR v2.
Pre-calculates, materializes, and maintains aggregated inventory read projections
(e.g., category summary statistics, stock values, low-stock reorder lists)
to accelerate frequent application queries over 100,000+ items.
"""

import sqlite3
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from .db import InventoryDatabaseManager

logger = logging.getLogger("smar.structured_data.read_models")


class ReadModelManager:
    """
    Manages Materialized Views and Read Models built on top of the primary database.
    Provides fast aggregated read paths while maintaining the Primary Database as the single source of truth.
    """

    def __init__(self, db_manager: Optional[InventoryDatabaseManager] = None):
        self.db = db_manager or InventoryDatabaseManager()
        self.initialize_read_models()

    def initialize_read_models(self) -> None:
        """Create materialized summary tables, views, and automated sync triggers."""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            # 1. Materialized Table for Category Inventory Aggregations
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS mv_category_summary (
                category TEXT PRIMARY KEY,
                total_skus INTEGER NOT NULL,
                active_skus INTEGER NOT NULL,
                total_quantity REAL NOT NULL,
                low_stock_count INTEGER NOT NULL,
                total_stock_value_mrp REAL NOT NULL,
                total_stock_value_cost REAL NOT NULL,
                last_updated_at TEXT NOT NULL
            );
            """)

            # 2. Materialized Table for Low Stock Alerts
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS mv_low_stock_alerts (
                item_id TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                category TEXT NOT NULL,
                brand TEXT NOT NULL,
                quantity REAL NOT NULL,
                reorder_level INTEGER NOT NULL,
                deficit_quantity REAL NOT NULL,
                unit_price REAL NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # Index on low stock deficit for rapid sorting
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mv_low_stock_deficit 
            ON mv_low_stock_alerts(deficit_quantity DESC);
            """)

            conn.commit()
            logger.info("Materialized read models and tables initialized successfully.")
        finally:
            conn.close()
            
        # Initial refresh to populate materialized views
        self.refresh_all_materialized_views()

    def refresh_all_materialized_views(self) -> None:
        """Refresh all materialized view tables from the primary source of truth."""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()

            # A. Refresh Category Summary Materialized Table
            cursor.execute("DELETE FROM mv_category_summary;")
            cursor.execute("""
            INSERT INTO mv_category_summary (
                category, total_skus, active_skus, total_quantity,
                low_stock_count, total_stock_value_mrp, total_stock_value_cost, last_updated_at
            )
            SELECT 
                category,
                COUNT(*) AS total_skus,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_skus,
                COALESCE(SUM(quantity), 0.0) AS total_quantity,
                SUM(CASE WHEN is_active = 1 AND quantity <= reorder_level THEN 1 ELSE 0 END) AS low_stock_count,
                COALESCE(SUM(quantity * unit_price), 0.0) AS total_stock_value_mrp,
                COALESCE(SUM(quantity * cost_price), 0.0) AS total_stock_value_cost,
                ? AS last_updated_at
            FROM inventory_items
            GROUP BY category;
            """, (now_iso,))

            # B. Refresh Low Stock Alerts Materialized Table
            cursor.execute("DELETE FROM mv_low_stock_alerts;")
            cursor.execute("""
            INSERT INTO mv_low_stock_alerts (
                item_id, canonical_name, category, brand, quantity,
                reorder_level, deficit_quantity, unit_price, updated_at
            )
            SELECT 
                item_id,
                canonical_name,
                category,
                brand,
                quantity,
                reorder_level,
                (reorder_level - quantity) AS deficit_quantity,
                unit_price,
                updated_at
            FROM inventory_items
            WHERE is_active = 1 AND quantity <= reorder_level;
            """)

            conn.commit()
            logger.debug("Materialized views refreshed cleanly.")
        finally:
            conn.close()

    def get_category_summary(self, category: str) -> Optional[Dict[str, Any]]:
        """Retrieve pre-aggregated summary stats for a single category."""
        conn = self.db.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM mv_category_summary WHERE category = ?",
                (category,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_category_summaries(self) -> List[Dict[str, Any]]:
        """Retrieve all pre-aggregated category summary records."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute("SELECT * FROM mv_category_summary ORDER BY category ASC;").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_low_stock_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve prioritized low-stock items from the materialized view."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM mv_low_stock_alerts ORDER BY deficit_quantity DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
