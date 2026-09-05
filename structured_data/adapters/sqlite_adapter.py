"""
structured_data/adapters/sqlite_adapter.py
==========================================
High-performance SQLite storage adapter for SMAR v2.
Wraps primary inventory database with B-Tree indexes, FTS5 virtual tables,
and schema introspection.
"""

import sqlite3
from typing import List, Dict, Any, Optional
from .base import BaseStorageAdapter
from ..db import InventoryDatabaseManager


# Define known volatile fields for Kirana & Warehouse inventory
VOLATILE_FIELDS = {"quantity", "unit_price", "cost_price", "reorder_level", "is_active", "updated_at"}


class SQLiteStorageAdapter(BaseStorageAdapter):
    """
    Adapter for SQLite databases. Defaults to smar_inventory.db.
    """

    def __init__(self, db_manager: Optional[InventoryDatabaseManager] = None, db_path: Optional[str] = None):
        if db_manager:
            self.db_manager = db_manager
        else:
            self.db_manager = InventoryDatabaseManager(db_path=db_path)
        self.db_path = self.db_manager.db_path

    def get_source_name(self) -> str:
        return f"SQLite ({self.db_path})"

    def get_source_type(self) -> str:
        return "sqlite"

    def introspect_schema(self) -> Dict[str, Any]:
        """
        Dynamically introspects tables, columns, data types, indexes, and sample values.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            
            # Find all user tables (exclude sqlite internal and FTS auxiliary tables)
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                  AND name NOT LIKE 'sqlite_%' 
                  AND name NOT LIKE '%_fts%'
            """)
            table_names = [r[0] for r in cursor.fetchall()]

            tables = []
            for t_name in table_names:
                # Column info: cid, name, type, notnull, dflt_value, pk
                cursor.execute(f"PRAGMA table_info({t_name});")
                cols_info = cursor.fetchall()

                # Row count
                cursor.execute(f"SELECT COUNT(*) FROM {t_name};")
                row_cnt = cursor.fetchone()[0]

                # Index info
                cursor.execute(f"PRAGMA index_list({t_name});")
                indexes = [dict(idx) for idx in cursor.fetchall()]

                columns = []
                for col in cols_info:
                    col_name = col[1]
                    col_type = col[2] or "TEXT"
                    is_pk = bool(col[5])
                    is_volatile = col_name.lower() in VOLATILE_FIELDS

                    # Fetch a few sample values for semantic grounding
                    sample_vals = []
                    try:
                        cursor.execute(f"SELECT DISTINCT {col_name} FROM {t_name} WHERE {col_name} IS NOT NULL LIMIT 3;")
                        sample_vals = [r[0] for r in cursor.fetchall()]
                    except Exception:
                        pass

                    columns.append({
                        "name": col_name,
                        "type": col_type,
                        "is_primary_key": is_pk,
                        "is_volatile": is_volatile,
                        "sample_values": sample_vals
                    })

                tables.append({
                    "table_name": t_name,
                    "columns": columns,
                    "row_count": row_cnt,
                    "indexes": [idx.get("name") for idx in indexes]
                })

            return {
                "source_name": self.get_source_name(),
                "source_type": self.get_source_type(),
                "tables": tables
            }
        finally:
            conn.close()

    def get_item_by_id(self, item_id: str, table_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        # Fast path for primary inventory
        target_table = table_name or "inventory_items"
        if target_table == "inventory_items":
            return self.db_manager.get_item_by_id(item_id)

        conn = self.db_manager.get_connection()
        try:
            row = conn.execute(f"SELECT * FROM {target_table} WHERE item_id = ?", (item_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_item_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        return self.db_manager.get_item_by_barcode(barcode)

    def search_by_text(self, query: str, limit: int = 20, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        target_table = table_name or "inventory_items"
        if target_table == "inventory_items":
            return self.db_manager.search_full_text(query, limit=limit)

        # Fallback query with LIKE for custom tables
        conn = self.db_manager.get_connection()
        try:
            pattern = f"%{query.strip()}%"
            rows = conn.execute(
                f"SELECT * FROM {target_table} WHERE canonical_name LIKE ? OR category LIKE ? LIMIT ?",
                (pattern, pattern, limit)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def filter_items(
        self,
        filters: Dict[str, Any],
        limit: int = 50,
        table_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        target_table = table_name or "inventory_items"
        conn = self.db_manager.get_connection()
        try:
            where_clauses = []
            params = []
            for col, val in filters.items():
                where_clauses.append(f"{col} = ?")
                params.append(val)

            where_str = " AND ".join(where_clauses) if where_clauses else "1=1"
            sql = f"SELECT * FROM {target_table} WHERE {where_str} LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, tuple(params)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_aggregations(
        self,
        group_by: Optional[str] = None,
        table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        target_table = table_name or "inventory_items"
        conn = self.db_manager.get_connection()
        try:
            total_count = conn.execute(f"SELECT COUNT(*) FROM {target_table};").fetchone()[0]
            
            result: Dict[str, Any] = {"total_records": total_count}
            if group_by:
                rows = conn.execute(f"""
                    SELECT {group_by}, COUNT(*) as count 
                    FROM {target_table} 
                    GROUP BY {group_by} 
                    ORDER BY count DESC 
                    LIMIT 20;
                """).fetchall()
                result[f"by_{group_by}"] = {r[0]: r[1] for r in rows}

            return result
        finally:
            conn.close()

    def get_total_count(self, table_name: Optional[str] = None) -> int:
        target_table = table_name or "inventory_items"
        conn = self.db_manager.get_connection()
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {target_table};").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def close(self) -> None:
        pass
