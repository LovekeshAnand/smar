"""
structured_data/db.py
======================
Primary Database Manager for SMAR v2 Structured Data Layer.
Manages connection pooling, WAL mode pragmas, table DDL, indexing strategies,
FTS5 full-text search virtual tables, triggers, transaction processing, and
query plan explain output.
"""

import os
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
from .models import InventoryItem, ETLBatchResult

logger = logging.getLogger("smar.structured_data.db")


class InventoryDatabaseManager:
    """
    Manages SQLite Primary Database for Kirana inventory (smar_inventory.db).
    Acts as the single source of truth for cold structured inventory data.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = db_path
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.getenv("SMAR_INVENTORY_DB_PATH", os.path.join(base_dir, "data", "smar_inventory.db"))

        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self.initialize_database()

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a high-performance SQLite connection."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode and performance PRAGMAs
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")  # 64MB cache
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def transaction(self):
        """Context manager providing thread-safe transaction scope."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_database(self) -> None:
        """Create primary inventory table, indexes, FTS5 virtual table, and triggers."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # 1. Primary Inventory Table (Source of Truth)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_items (
                -- Static attributes
                item_id TEXT PRIMARY KEY,
                barcode TEXT,
                canonical_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                category TEXT NOT NULL,
                brand TEXT NOT NULL DEFAULT 'Generic',
                unit_of_measure TEXT NOT NULL DEFAULT 'piece',
                hsn_code TEXT,
                created_at TEXT NOT NULL,
                
                -- Volatile attributes (Stateful inventory/pricing)
                quantity REAL NOT NULL CHECK(quantity >= 0),
                unit_price REAL NOT NULL CHECK(unit_price > 0),
                cost_price REAL NOT NULL CHECK(cost_price > 0),
                reorder_level INTEGER NOT NULL DEFAULT 10,
                is_active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );
            """)

            # 2. Indexes for Query Performance & Entity Resolution
            # A. Barcode index (unique lookups via POS scanner)
            cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_barcode 
            ON inventory_items(barcode);
            """)

            # B. Category index (filtering products by section)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_category 
            ON inventory_items(category);
            """)

            # C. Normalized Name index (Fast exact & prefix match for entity resolution)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_normalized_name 
            ON inventory_items(normalized_name);
            """)

            # D. Composite index (Category + Brand queries)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_cat_brand 
            ON inventory_items(category, brand);
            """)

            # E. Volatile Stock Alert index (Reorder level checks)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_stock_alert 
            ON inventory_items(is_active, quantity);
            """)

            # 3. FTS5 Virtual Table for Instant Fuzzy/Full-Text Search
            cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS inventory_fts USING fts5(
                item_id UNINDEXED,
                canonical_name,
                category,
                brand,
                tokenize='unicode61 remove_diacritics 1'
            );
            """)

            # 4. Triggers to auto-sync FTS5 index on INSERT, UPDATE, DELETE
            cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_ai AFTER INSERT ON inventory_items BEGIN
                INSERT INTO inventory_fts(item_id, canonical_name, category, brand)
                VALUES (new.item_id, new.canonical_name, new.category, new.brand);
            END;
            """)

            cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_au AFTER UPDATE ON inventory_items BEGIN
                UPDATE inventory_fts 
                SET canonical_name = new.canonical_name, category = new.category, brand = new.brand
                WHERE item_id = new.item_id;
            END;
            """)

            cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_ad AFTER DELETE ON inventory_items BEGIN
                DELETE FROM inventory_fts WHERE item_id = old.item_id;
            END;
            """)

            # 5. Audit Log Table for ETL Execution Tracking
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS etl_batch_runs (
                batch_id TEXT PRIMARY KEY,
                total_rows INTEGER NOT NULL,
                valid_rows INTEGER NOT NULL,
                invalid_rows INTEGER NOT NULL,
                inserted_rows INTEGER NOT NULL,
                updated_rows INTEGER NOT NULL,
                skipped_duplicates INTEGER NOT NULL,
                failed_rows INTEGER NOT NULL,
                processing_time_seconds REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            conn.commit()
            logger.info(f"Database initialized successfully at '{self.db_path}'.")
        finally:
            conn.close()

    def record_etl_run(self, result: ETLBatchResult) -> None:
        """Record batch execution statistics into the audit log."""
        conn = self.get_connection()
        try:
            conn.execute("""
            INSERT OR REPLACE INTO etl_batch_runs (
                batch_id, total_rows, valid_rows, invalid_rows,
                inserted_rows, updated_rows, skipped_duplicates,
                failed_rows, processing_time_seconds, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'));
            """, (
                result.batch_id,
                result.total_rows,
                result.valid_rows,
                result.invalid_rows,
                result.inserted_rows,
                result.updated_rows,
                result.skipped_duplicates,
                result.failed_rows,
                result.processing_time_seconds
            ))
            conn.commit()
        finally:
            conn.close()

    def get_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Exact lookup by Primary Key item_id."""
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM inventory_items WHERE item_id = ?", (item_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_item_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """Exact lookup by Barcode index."""
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT * FROM inventory_items WHERE barcode = ?", (barcode,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def search_by_category_and_brand(self, category: str, brand: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Filter items by category and optional brand using composite index."""
        conn = self.get_connection()
        try:
            if brand:
                rows = conn.execute(
                    "SELECT * FROM inventory_items WHERE category = ? AND brand = ? LIMIT ?",
                    (category, brand, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM inventory_items WHERE category = ? LIMIT ?",
                    (category, limit)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def search_full_text(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Perform sub-millisecond full-text / fuzzy search using FTS5 index."""
        conn = self.get_connection()
        try:
            tokens = [token for token in query.strip().split() if token]
            if not tokens:
                return []

            sql = """
            SELECT i.* 
            FROM inventory_fts f
            JOIN inventory_items i ON f.item_id = i.item_id
            WHERE inventory_fts MATCH ?
            ORDER BY rank
            LIMIT ?;
            """
            # 1. Try strict AND first
            formatted_query = " ".join([f"{t}*" for t in tokens])
            rows = conn.execute(sql, (formatted_query, limit)).fetchall()

            # 2. If no exact match, fallback to ranking OR
            if not rows and len(tokens) > 1:
                formatted_query_or = " OR ".join([f"{t}*" for t in tokens])
                rows = conn.execute(sql, (formatted_query_or, limit)).fetchall()

            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_low_stock_items(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve items where stock quantity is at or below reorder level."""
        conn = self.get_connection()
        try:
            rows = conn.execute("""
            SELECT item_id, canonical_name, category, brand, quantity, reorder_level, unit_price
            FROM inventory_items
            WHERE is_active = 1 AND quantity <= reorder_level
            ORDER BY quantity ASC
            LIMIT ?;
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def explain_query(self, sql: str, params: tuple = ()) -> List[str]:
        """Run EXPLAIN QUERY PLAN to verify index usage."""
        conn = self.get_connection()
        try:
            explain_sql = f"EXPLAIN QUERY PLAN {sql}"
            rows = conn.execute(explain_sql, params).fetchall()
            return [f"SelectID {r[0]} | Order {r[1]} | From {r[2]} | Detail: {r[3]}" for r in rows]
        finally:
            conn.close()

    def get_total_count(self) -> int:
        """Get total record count in primary table."""
        conn = self.get_connection()
        try:
            row = conn.execute("SELECT COUNT(*) FROM inventory_items;").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()
