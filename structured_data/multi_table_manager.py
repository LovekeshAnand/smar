"""
structured_data/multi_table_manager.py
=======================================
Multi-Table Warehouse Manager for SMAR v2.
Handles 1,000,000+ rows across multiple interconnected or unexpected tables.

Features:
1. Universal streaming chunked ingestion for CSV, Excel (.xlsx, .xls), and SQLite.
2. High-performance SQLite engine with WAL mode, memory caching, and chunked batch commits.
3. Automatic schema detection: primary keys, foreign keys, text search columns.
4. Automatic FTS5 full-text search indexing on primary text columns.
5. Cross-table joining and aggregations without hardcoded column names.
6. Non-blocking asynchronous query interface.
"""

import os
import json
import sqlite3
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Generator
import pandas as pd

from structured_data.cache import hot_cache

logger = logging.getLogger("smar.multi_table")


class MultiTableWarehouseManager:
    """
    Manages multi-table relational storage and high-speed querying for SMAR v2.
    """

    def __init__(self, db_path: str = "data/warehouse.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_sqlite_pragmas()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite_pragmas(self):
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA cache_size = -64000;")  # 64MB cache
            conn.execute("PRAGMA foreign_keys = ON;")

    def list_tables(self) -> List[Dict[str, Any]]:
        """Returns all tables with row counts and column definitions."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%'
                ORDER BY name;
            """)
            table_names = [r["name"] for r in cur.fetchall()]

            results = []
            for tname in table_names:
                # Count rows
                try:
                    cur.execute(f"SELECT COUNT(*) as cnt FROM \"{tname}\";")
                    row_count = cur.fetchone()["cnt"]
                except Exception:
                    row_count = 0

                # Get columns
                cur.execute(f"PRAGMA table_info(\"{tname}\");")
                cols = [{"name": r["name"], "type": r["type"], "pk": bool(r["pk"])} for r in cur.fetchall()]

                results.append({
                    "table_name": tname,
                    "row_count": row_count,
                    "columns": cols
                })
            return results

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Returns detailed schema, foreign keys, and indexes for a table."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info(\"{table_name}\");")
            columns = {r["name"]: r["type"] for r in cur.fetchall()}

            cur.execute(f"PRAGMA foreign_key_list(\"{table_name}\");")
            fks = [{
                "from_col": r["from"],
                "to_table": r["table"],
                "to_col": r["to"]
            } for r in cur.fetchall()]

            cur.execute(f"SELECT COUNT(*) as cnt FROM \"{table_name}\";")
            total_rows = cur.fetchone()["cnt"]

            return {
                "table_name": table_name,
                "columns": columns,
                "foreign_keys": fks,
                "total_rows": total_rows
            }

    def ingest_file(
        self,
        file_path: str,
        table_name: Optional[str] = None,
        chunksize: int = 25000
    ) -> Dict[str, Any]:
        """
        Streams and ingests any unexpected file (CSV, Excel) into a high-performance SQLite table.
        Automatically indexes PKs and creates FTS5 virtual tables.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        base_name = os.path.splitext(os.path.basename(file_path))[0].lower().replace("-", "_").replace(" ", "_")
        target_table = table_name or base_name

        total_rows = 0
        text_cols = []
        pk_col = None

        logger.info(f"Starting chunked ingestion for '{file_path}' into table '{target_table}'...")

        with self._get_connection() as conn:
            # Temporary speed pragmas during bulk ingest
            conn.execute("PRAGMA synchronous = OFF;")

            if ext in [".csv", ".tsv", ".txt"]:
                sep = "\t" if ext == ".tsv" else None
                try:
                    reader = pd.read_csv(file_path, sep=sep, chunksize=chunksize, low_memory=False)
                except Exception:
                    reader = pd.read_csv(file_path, chunksize=chunksize, low_memory=False)
                for i, chunk in enumerate(reader):
                    chunk.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in chunk.columns]
                    if i == 0:
                        chunk.to_sql(target_table, conn, if_exists="replace", index=False)
                        for col, dtype in chunk.dtypes.items():
                            col_str = str(col).lower()
                            dtype_str = str(dtype).lower()
                            is_num = "int" in dtype_str or "float" in dtype_str or "bool" in dtype_str
                            if any(k in col_str for k in ["id", "code", "tag", "num", "key", "pk"]) and pk_col is None:
                                pk_col = col
                            if (not is_num) or "name" in col_str or "desc" in col_str or "title" in col_str:
                                text_cols.append(col)
                        if pk_col is None and len(chunk.columns) > 0:
                            pk_col = chunk.columns[0]
                    else:
                        chunk.to_sql(target_table, conn, if_exists="append", index=False)
                    total_rows += len(chunk)

            elif ext in [".xlsx", ".xls"]:
                xl = pd.ExcelFile(file_path)
                for sheet in xl.sheet_names:
                    sheet_table = target_table if len(xl.sheet_names) == 1 else f"{target_table}_{sheet.lower()}"
                    df = pd.read_excel(file_path, sheet_name=sheet)
                    df.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]
                    df.to_sql(sheet_table, conn, if_exists="replace", index=False)
                    total_rows += len(df)
                    target_table = sheet_table
                    for col, dtype in df.dtypes.items():
                        col_str = str(col).lower()
                        dtype_str = str(dtype).lower()
                        is_num = "int" in dtype_str or "float" in dtype_str or "bool" in dtype_str
                        if any(k in col_str for k in ["id", "code", "tag", "num", "key", "pk"]) and pk_col is None:
                            pk_col = col
                        if (not is_num) or "name" in col_str or "desc" in col_str or "title" in col_str:
                            text_cols.append(col)
                    if pk_col is None and len(df.columns) > 0:
                        pk_col = df.columns[0]

            elif ext == ".json":
                with open(file_path, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                elif isinstance(data, dict):
                    # Check if dict wraps list of rows
                    list_val = next((v for v in data.values() if isinstance(v, list)), None)
                    if list_val:
                        df = pd.DataFrame(list_val)
                    else:
                        df = pd.DataFrame([data])
                else:
                    raise ValueError(f"Invalid JSON data structure in {file_path}")
                df.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]
                df.to_sql(target_table, conn, if_exists="replace", index=False)
                total_rows = len(df)
                for col, dtype in df.dtypes.items():
                    col_str = str(col).lower()
                    dtype_str = str(dtype).lower()
                    is_num = "int" in dtype_str or "float" in dtype_str or "bool" in dtype_str
                    if any(k in col_str for k in ["id", "code", "tag", "num", "key", "pk"]) and pk_col is None:
                        pk_col = col
                    if (not is_num) or "name" in col_str or "desc" in col_str or "title" in col_str:
                        text_cols.append(col)
                if pk_col is None and len(df.columns) > 0:
                    pk_col = df.columns[0]

            elif ext in [".jsonl", ".ndjson"]:
                records = []
                with open(file_path, "r", encoding="utf-8") as jf:
                    for line in jf:
                        if line.strip():
                            records.append(json.loads(line))
                df = pd.DataFrame(records)
                df.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]
                df.to_sql(target_table, conn, if_exists="replace", index=False)
                total_rows = len(df)
                for col, dtype in df.dtypes.items():
                    col_str = str(col).lower()
                    dtype_str = str(dtype).lower()
                    is_num = "int" in dtype_str or "float" in dtype_str or "bool" in dtype_str
                    if any(k in col_str for k in ["id", "code", "tag", "num", "key", "pk"]) and pk_col is None:
                        pk_col = col
                    if (not is_num) or "name" in col_str or "desc" in col_str or "title" in col_str:
                        text_cols.append(col)
                if pk_col is None and len(df.columns) > 0:
                    pk_col = df.columns[0]

            elif ext == ".parquet":
                df = pd.read_parquet(file_path)
                df.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]
                df.to_sql(target_table, conn, if_exists="replace", index=False)
                total_rows = len(df)
                for col, dtype in df.dtypes.items():
                    col_str = str(col).lower()
                    dtype_str = str(dtype).lower()
                    is_num = "int" in dtype_str or "float" in dtype_str or "bool" in dtype_str
                    if any(k in col_str for k in ["id", "code", "tag", "num", "key", "pk"]) and pk_col is None:
                        pk_col = col
                    if (not is_num) or "name" in col_str or "desc" in col_str or "title" in col_str:
                        text_cols.append(col)
                if pk_col is None and len(df.columns) > 0:
                    pk_col = df.columns[0]

            elif ext in [".sqlite", ".db", ".sqlite3"]:
                # Ingest tables from external SQLite file into warehouse
                src_conn = sqlite3.connect(file_path)
                src_cursor = src_conn.cursor()
                tbls = src_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%';"
                ).fetchall()
                for (tbl_name,) in tbls:
                    df = pd.read_sql(f'SELECT * FROM "{tbl_name}"', src_conn)
                    df.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]
                    dest_tbl = tbl_name.lower().replace(" ", "_").replace("-", "_")
                    df.to_sql(dest_tbl, conn, if_exists="replace", index=False)
                    total_rows += len(df)
                    target_table = dest_tbl
                src_conn.close()

            else:
                raise ValueError(f"Unsupported file format: {ext}")

            # Restore synchronous mode
            conn.execute("PRAGMA synchronous = NORMAL;")

            # Automatically create indexes
            if pk_col:
                try:
                    conn.execute(f"CREATE INDEX IF NOT EXISTS \"idx_{target_table}_{pk_col}\" ON \"{target_table}\" (\"{pk_col}\");")
                except Exception as e:
                    logger.debug(f"Index creation note: {e}")

            # Auto create FTS5 index for text search if text columns exist
            if text_cols:
                fts_cols_def = ", ".join([f"\"{c}\"" for c in text_cols[:4]])
                fts_table = f"{target_table}_fts"
                try:
                    conn.execute(f"DROP TABLE IF EXISTS \"{fts_table}\";")
                    conn.execute(f"CREATE VIRTUAL TABLE \"{fts_table}\" USING fts5({fts_cols_def}, content='{target_table}');")
                    conn.execute(f"INSERT INTO \"{fts_table}\"(\"{fts_table}\") VALUES('rebuild');")
                except Exception as e:
                    logger.debug(f"FTS5 creation note: {e}")

            conn.commit()

        # Invalidate schema cache
        hot_cache.delete(f"schema:warehouse")
        logger.info(f"Ingested {total_rows:,} rows into table '{target_table}' with dynamic indexing.")

        return {
            "table": target_table,
            "rows_ingested": total_rows,
            "pk_column": pk_col,
            "indexed_text_columns": text_cols[:4],
            "fts_enabled": len(text_cols) > 0
        }

    def ingest_multiple_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Ingests a list of files sequentially into the warehouse."""
        results = []
        for fp in file_paths:
            try:
                res = self.ingest_file(fp)
                results.append(res)
            except Exception as e:
                logger.error(f"Failed to ingest {fp}: {e}")
                results.append({"file": fp, "error": str(e)})
        return results

    def search_text(
        self,
        query: str,
        table_name: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fast full-text search across warehouse tables.
        Uses FTS5 virtual tables when available, with hot cache check.
        """
        cache_key = f"query:text:{table_name or 'all'}:{query.strip().lower()}:{limit}"
        cached = hot_cache.get(cache_key)
        if cached:
            return cached

        import re

        MONTH_MAP = {
            'january': '01', 'jan': '01', 'february': '02', 'feb': '02', 'march': '03', 'mar': '03',
            'april': '04', 'apr': '04', 'may': '05', 'june': '06', 'jun': '06', 'july': '07', 'jul': '07',
            'august': '08', 'aug': '08', 'september': '09', 'sep': '09', 'october': '10', 'oct': '10',
            'november': '11', 'nov': '11', 'december': '12', 'dec': '12'
        }

        # Date pattern detection (e.g., '20th April', 'April 20', '2022-04-20')
        lower_q = query.lower()
        date_pattern = None
        m_d1 = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)', lower_q)
        if m_d1 and m_d1.group(2).lower() in MONTH_MAP:
            date_pattern = f"-{MONTH_MAP[m_d1.group(2).lower()]}-{int(m_d1.group(1)):02d}"
        else:
            m_d2 = re.search(r'([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?', lower_q)
            if m_d2 and m_d2.group(1).lower() in MONTH_MAP:
                date_pattern = f"-{MONTH_MAP[m_d2.group(1).lower()]}-{int(m_d2.group(2)):02d}"
            else:
                m_d3 = re.search(r'(\d{4}-\d{2}-\d{2})', lower_q)
                if m_d3:
                    date_pattern = m_d3.group(1)

        # Smart prioritization of target tables based on query keywords
        all_tables = [t["table_name"] for t in self.list_tables()]
        if table_name:
            target_tables = [table_name]
        else:
            priority_tables = []
            if any(k in lower_q for k in ["order", "dispatch", "ship", "delivery", "track"]):
                priority_tables.extend([t for t in ["orders", "shipments", "order_items"] if t in all_tables])
            if any(k in lower_q for k in ["salary", "employee", "worker", "staff"]):
                priority_tables.extend([t for t in ["employees"] if t in all_tables])
            if any(k in lower_q for k in ["product", "item", "stock", "price", "inventory"]):
                priority_tables.extend([t for t in ["products", "inventory_items"] if t in all_tables])
            if any(k in lower_q for k in ["customer", "client", "user"]):
                priority_tables.extend([t for t in ["customers"] if t in all_tables])
            if any(k in lower_q for k in ["store", "branch", "location"]):
                priority_tables.extend([t for t in ["stores"] if t in all_tables])

            ordered = []
            for pt in priority_tables:
                if pt not in ordered:
                    ordered.append(pt)
            for at in all_tables:
                if at not in ordered:
                    ordered.append(at)
            target_tables = ordered

        results = []

        with self._get_connection() as conn:
            cur = conn.cursor()

            # Fast-path for date queries on orders/shipments/tables with date columns
            if date_pattern:
                for tname in target_tables:
                    try:
                        cur.execute(f"PRAGMA table_info(\"{tname}\");")
                        cols = [r["name"] for r in cur.fetchall()]
                        date_cols = [c for c in cols if any(dk in c.lower() for dk in ["date", "time", "created", "at"])]

                        if tname == "orders" and "order_date" in cols:
                            # Join with shipments if shipments table exists
                            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shipments';")
                            has_shipments = cur.fetchone() is not None
                            if has_shipments:
                                if any(k in lower_q for k in ["dispatch", "ship"]):
                                    cur.execute("""
                                        SELECT o.order_id, o.customer_id, o.order_date, s.status, o.store_id
                                        FROM orders o
                                        LEFT JOIN shipments s ON o.order_id = s.order_id
                                        WHERE o.order_date LIKE ? AND s.status IN ('shipped', 'delivered')
                                        ORDER BY o.order_id
                                        LIMIT ?;
                                    """, (f"%{date_pattern}%", limit))
                                else:
                                    cur.execute("""
                                        SELECT o.order_id, o.customer_id, o.order_date, s.status, o.store_id
                                        FROM orders o
                                        LEFT JOIN shipments s ON o.order_id = s.order_id
                                        WHERE o.order_date LIKE ?
                                        ORDER BY o.order_id
                                        LIMIT ?;
                                    """, (f"%{date_pattern}%", limit))
                                hits = [dict(r) for r in cur.fetchall()]
                                for h in hits:
                                    h["_source_table"] = "orders"
                                if hits:
                                    results.extend(hits[:limit])
                                    break

                        # General date column LIKE query
                        for dc in date_cols:
                            cur.execute(f"SELECT * FROM \"{tname}\" WHERE \"{dc}\" LIKE ? LIMIT ?;", (f"%{date_pattern}%", limit))
                            hits = [dict(r) for r in cur.fetchall()]
                            if hits:
                                for h in hits:
                                    h["_source_table"] = tname
                                results.extend(hits)
                                break
                        if results:
                            break
                    except Exception as date_err:
                        logger.debug(f"Date search note on {tname}: {date_err}")

                if results:
                    hot_cache.set(cache_key, results[:limit], ttl_seconds=300)
                    return results[:limit]

            cleaned = re.sub(r'[^a-zA-Z0-9]+', ' ', query).strip()
            terms = [t for t in cleaned.split() if len(t) >= 1]
            if not terms:
                return []

            for tname in target_tables:
                fts_table = f"{tname}_fts"
                # Check if FTS table exists
                cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{fts_table}';")
                has_fts = cur.fetchone() is not None

                table_hits = []
                if has_fts:
                    # 1. Try strict AND first (alphanumeric terms with prefix wildcard)
                    fts_expr_and = " AND ".join([f"{t}*" for t in terms])
                    try:
                        cur.execute(f"""
                            SELECT t.* 
                            FROM "{tname}" t 
                            WHERE t.rowid IN (
                                SELECT rowid FROM "{fts_table}" 
                                WHERE "{fts_table}" MATCH ? 
                                ORDER BY rank 
                                LIMIT ?
                            );
                        """, (fts_expr_and, limit))
                        table_hits = [dict(r) for r in cur.fetchall()]
                    except Exception as e:
                        logger.debug(f"FTS AND search note on {fts_table}: {e}")

                    # 2. Fallback to ranking OR if AND had no results
                    if not table_hits:
                        fts_expr_or = " OR ".join([f"{t}*" for t in terms])
                        try:
                            cur.execute(f"""
                                SELECT t.* 
                                FROM "{tname}" t 
                                WHERE t.rowid IN (
                                    SELECT rowid FROM "{fts_table}" 
                                    WHERE "{fts_table}" MATCH ? 
                                    ORDER BY rank 
                                    LIMIT ?
                                );
                            """, (fts_expr_or, limit))
                            table_hits = [dict(r) for r in cur.fetchall()]
                        except Exception as e:
                            logger.debug(f"FTS OR search note on {fts_table}: {e}")

                # 3. Fallback to schema-introspected column search if FTS yielded no results
                if not table_hits:
                    try:
                        cur.execute(f"PRAGMA table_info(\"{tname}\");")
                        table_cols = cur.fetchall()

                        # First check if any term is a numeric ID matching integer/id columns
                        num_terms = [int(t) for t in terms if t.isdigit()]
                        if num_terms:
                            num_cols = [r["name"] for r in table_cols if "int" in str(r["type"]).lower() or "id" in r["name"].lower() or r["pk"]]
                            for nc in num_cols:
                                for nt in num_terms:
                                    cur.execute(f"SELECT * FROM \"{tname}\" WHERE \"{nc}\" = ? LIMIT ?;", (nt, limit))
                                    hits = [dict(r) for r in cur.fetchall()]
                                    if hits:
                                        table_hits.extend(hits)
                                        break
                                if table_hits:
                                    break

                        # Text LIKE match for non-numeric or general terms
                        if not table_hits:
                            text_terms = [t for t in terms if not t.isdigit()]
                            search_term = text_terms[0] if text_terms else terms[0]
                            cols = [r["name"] for r in table_cols if "int" not in str(r["type"]).lower()]
                            if cols:
                                where_clauses = " OR ".join([f"\"{c}\" LIKE ?" for c in cols[:4]])
                                like_params = [f"%{search_term}%"] * min(len(cols), 4)
                                cur.execute(f"SELECT * FROM \"{tname}\" WHERE {where_clauses} LIMIT ?;", (*like_params, limit))
                                table_hits = [dict(r) for r in cur.fetchall()]
                    except Exception as e:
                        logger.debug(f"Search fallback note on {tname}: {e}")

                for item in table_hits:
                    item["_source_table"] = tname
                    results.append(item)
                    if len(results) >= limit:
                        break

                if len(results) >= limit:
                    break

        hot_cache.set(cache_key, results, ttl_seconds=300)
        return results

    def get_record_by_id(
        self,
        table_name: str,
        id_value: Any,
        id_column: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Instant primary key lookup with hot cache."""
        cache_key = f"entity:{table_name}:{id_value}"
        cached = hot_cache.get(cache_key)
        if cached:
            return cached

        with self._get_connection() as conn:
            cur = conn.cursor()
            if not id_column:
                # Find PK column
                cur.execute(f"PRAGMA table_info(\"{table_name}\");")
                cols = cur.fetchall()
                for c in cols:
                    if c["pk"] or "id" in c["name"].lower():
                        id_column = c["name"]
                        break
                if not id_column and cols:
                    id_column = cols[0]["name"]

            query = f"SELECT * FROM \"{table_name}\" WHERE \"{id_column}\" = ? OR LOWER(\"{id_column}\") = LOWER(?) LIMIT 1;"
            cur.execute(query, (id_value, str(id_value)))
            row = cur.fetchone()
            if row:
                res = dict(row)
                hot_cache.set(cache_key, res, ttl_seconds=3600)
                return res
            return None

    def search_records_by_field(
        self,
        table_name: str,
        field_name: str,
        field_value: Any,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Returns all rows from `table_name` where `field_name` = `field_value`.
        Used for relational lookups such as fetching all order_items for a given order_id.
        Results are NOT cached (dynamic relational data must always be fresh).
        """
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                query = f'SELECT * FROM "{table_name}" WHERE "{field_name}" = ? LIMIT {int(limit)};'
                cur.execute(query, (field_value,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.debug(f"search_records_by_field error on {table_name}.{field_name}={field_value}: {e}")
            return []

    def execute_aggregation(
        self,
        table_name: str,
        agg_func: str = "COUNT",
        column: str = "*",
        group_by: Optional[str] = None,
        filter_condition: Optional[str] = None,
        filter_params: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes fast mathematical aggregations (SUM, AVG, COUNT, MIN, MAX) with hot caching.
        Supports grouping and optional filter conditions.
        """
        import time
        start_t = time.perf_counter()
        agg_clean = agg_func.upper().strip()
        if agg_clean not in ["COUNT", "SUM", "AVG", "MIN", "MAX"]:
            agg_clean = "COUNT"

        params = list(filter_params or [])
        cache_key = f"agg:{table_name}:{agg_clean}:{column}:{group_by}:{filter_condition}:{params}"
        cached = hot_cache.get(cache_key)
        if cached:
            return cached

        with self._get_connection() as conn:
            cur = conn.cursor()
            where_clause = f" WHERE {filter_condition}" if filter_condition else ""

            if group_by:
                col_expr = f"{agg_clean}(\"{column}\")" if column != "*" else f"{agg_clean}(*)"
                sql = f"SELECT \"{group_by}\", {col_expr} as val FROM \"{table_name}\"{where_clause} GROUP BY \"{group_by}\" ORDER BY val DESC LIMIT 15;"
                cur.execute(sql, params)
                rows = cur.fetchall()
                breakdown = {str(r[group_by]): r["val"] for r in rows}
                total_val = sum(r["val"] for r in rows if r["val"] is not None)
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                data = {
                    "operation": "AGGREGATION",
                    "function": agg_clean,
                    "table": table_name,
                    "column": column,
                    "group_by": group_by,
                    "value": total_val,
                    "formatted_value": f"{total_val:,.2f}" if isinstance(total_val, float) else f"{total_val:,}",
                    "breakdown": breakdown,
                    "filter_condition": filter_condition,
                    "sql": sql,
                    "elapsed_ms": round(elapsed_ms, 2)
                }
            else:
                col_expr = f"{agg_clean}({column if column == '*' else '\"' + column + '\"'})"
                sql = f"SELECT {col_expr} as val, COUNT(*) as total_rows FROM \"{table_name}\"{where_clause};"
                cur.execute(sql, params)
                row = cur.fetchone()
                val = row["val"] if row else 0
                cnt = row["total_rows"] if row else 0
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0

                # Also fetch sample records for transparency if count is reasonable
                sample_records = []
                if cnt > 0 and cnt <= 50:
                    sample_cur = conn.cursor()
                    sample_cur.execute(f"SELECT * FROM \"{table_name}\"{where_clause} LIMIT 25;", params)
                    sample_records = [dict(r) for r in sample_cur.fetchall()]
                
                # Format nicely
                if val is None:
                    formatted = "0"
                elif isinstance(val, float):
                    formatted = f"{val:,.2f}"
                elif isinstance(val, int):
                    formatted = f"{val:,}"
                else:
                    formatted = str(val)

                data = {
                    "operation": "AGGREGATION",
                    "function": agg_clean,
                    "table": table_name,
                    "column": column,
                    "group_by": None,
                    "value": val,
                    "formatted_value": formatted,
                    "total_rows_evaluated": cnt,
                    "filter_condition": filter_condition,
                    "sample_records": sample_records,
                    "sql": sql,
                    "elapsed_ms": round(elapsed_ms, 2)
                }

        hot_cache.set(cache_key, data, ttl_seconds=600)
        return data

    def insert_record(
        self,
        table_name: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Inserts a new record into any table, auto-detecting schema and updating FTS index.
        """
        import time
        start_t = time.perf_counter()

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info(\"{table_name}\");")
            table_cols = {r["name"]: r for r in cur.fetchall()}
            if not table_cols:
                raise ValueError(f"Table '{table_name}' does not exist.")

            # Determine primary key or candidate id column
            pk_col = next((c for c, r in table_cols.items() if r["pk"]), None)
            if not pk_col:
                singular = table_name[:-3] + "y" if table_name.endswith("ies") else table_name.rstrip("s")
                for candidate in [f"{singular}_id", f"{table_name}_id", "id"]:
                    if candidate in table_cols:
                        pk_col = candidate
                        break

            # Filter provided data to valid columns
            valid_data = {k: v for k, v in data.items() if k in table_cols}

            # If an ID column exists and was not provided, automatically generate next ID
            if pk_col and pk_col not in valid_data:
                col_type = str(table_cols[pk_col]["type"]).upper()
                if any(t in col_type for t in ["INT", "NUM", "SERIAL"]) or not col_type:
                    cur.execute(f"SELECT COALESCE(MAX(\"{pk_col}\"), 0) + 1 FROM \"{table_name}\";")
                    max_row = cur.fetchone()
                    auto_val = max_row[0] if max_row else 1
                    valid_data[pk_col] = auto_val

            if not valid_data:
                raise ValueError(f"No valid columns provided for table '{table_name}'. Available: {list(table_cols.keys())}")

            cols = list(valid_data.keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join([f"\"{c}\"" for c in cols])
            values = [valid_data[c] for c in cols]

            sql = f"INSERT INTO \"{table_name}\" ({col_names}) VALUES ({placeholders});"
            cur.execute(sql, values)
            new_rowid = cur.lastrowid
            new_id = valid_data.get(pk_col, new_rowid) if pk_col else new_rowid

            # Sync FTS if FTS virtual table exists
            fts_table = f"{table_name}_fts"
            try:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (fts_table,))
                if cur.fetchone():
                    fts_cols = [c for c in cols if table_cols[c]["type"].upper() in ("TEXT", "VARCHAR")]
                    if fts_cols:
                        fts_col_names = ", ".join([f"\"{c}\"" for c in fts_cols])
                        fts_placeholders = ", ".join(["?"] * (len(fts_cols) + 1))
                        fts_sql = f"INSERT INTO \"{fts_table}\" (rowid, {fts_col_names}) VALUES ({fts_placeholders});"
                        cur.execute(fts_sql, [new_rowid] + [str(valid_data[c]) for c in fts_cols])
            except Exception as fts_err:
                logger.debug(f"FTS insert sync note on {table_name}: {fts_err}")

            conn.commit()

        # Invalidate caches
        hot_cache.clear()
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return {
            "operation": "INSERT",
            "table": table_name,
            "status": "SUCCESS",
            "inserted_id": new_id,
            "record": valid_data,
            "sql": sql,
            "affected_rows": 1,
            "elapsed_ms": round(elapsed_ms, 2)
        }

    def update_record(
        self,
        table_name: str,
        filter_data: Dict[str, Any],
        update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Updates an existing record, captures Before/After diff, and synchronizes FTS index.
        """
        import time
        start_t = time.perf_counter()

        if not filter_data:
            raise ValueError("Filter criteria required for safe update operation to avoid full-table overwrite.")
        if not update_data:
            raise ValueError("No update fields provided.")

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info(\"{table_name}\");")
            table_cols = {r["name"]: r for r in cur.fetchall()}
            if not table_cols:
                raise ValueError(f"Table '{table_name}' does not exist.")

            # Build WHERE clause
            where_parts = [f"\"{k}\" = ?" for k in filter_data.keys() if k in table_cols]
            where_vals = [filter_data[k] for k in filter_data.keys() if k in table_cols]
            if not where_parts:
                raise ValueError(f"Filter fields {list(filter_data.keys())} do not match table columns.")
            where_sql = " AND ".join(where_parts)

            # 1. Fetch BEFORE state
            cur.execute(f"SELECT * FROM \"{table_name}\" WHERE {where_sql} LIMIT 1;", where_vals)
            before_row = cur.fetchone()
            if not before_row:
                return {
                    "operation": "UPDATE",
                    "table": table_name,
                    "status": "NOT_FOUND",
                    "affected_rows": 0,
                    "message": f"No record in '{table_name}' matched criteria: {filter_data}"
                }

            before_state = dict(before_row)

            # 2. Build SET clause
            valid_updates = {k: v for k, v in update_data.items() if k in table_cols}
            if not valid_updates:
                raise ValueError(f"No valid update columns provided. Table columns: {list(table_cols.keys())}")

            set_parts = [f"\"{k}\" = ?" for k in valid_updates.keys()]
            set_vals = [valid_updates[k] for k in valid_updates.keys()]
            update_sql = f"UPDATE \"{table_name}\" SET {', '.join(set_parts)} WHERE {where_sql};"
            cur.execute(update_sql, set_vals + where_vals)
            affected = cur.rowcount

            # 3. Fetch AFTER state
            cur.execute(f"SELECT * FROM \"{table_name}\" WHERE {where_sql} LIMIT 1;", where_vals)
            after_row = cur.fetchone()
            after_state = dict(after_row) if after_row else {}

            # Calculate field diff
            diff = {}
            for k in valid_updates.keys():
                diff[k] = {
                    "before": before_state.get(k),
                    "after": after_state.get(k)
                }

            # Update FTS table if exists
            fts_table = f"{table_name}_fts"
            try:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (fts_table,))
                if cur.fetchone() and "rowid" in before_state:
                    cur.execute(f"DELETE FROM \"{fts_table}\" WHERE rowid = ?;", (before_state["rowid"],))
                    fts_cols = [c for c in table_cols if table_cols[c]["type"].upper() in ("TEXT", "VARCHAR")]
                    if fts_cols:
                        fts_col_names = ", ".join([f"\"{c}\"" for c in fts_cols])
                        fts_placeholders = ", ".join(["?"] * (len(fts_cols) + 1))
                        fts_sql = f"INSERT INTO \"{fts_table}\" (rowid, {fts_col_names}) VALUES ({fts_placeholders});"
                        cur.execute(fts_sql, [before_state["rowid"]] + [str(after_state.get(c, "")) for c in fts_cols])
            except Exception as fts_err:
                logger.debug(f"FTS update sync note on {table_name}: {fts_err}")

            conn.commit()

        # Invalidate caches
        hot_cache.clear()
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return {
            "operation": "UPDATE",
            "table": table_name,
            "status": "SUCCESS",
            "affected_rows": affected,
            "filter": filter_data,
            "diff": diff,
            "before": before_state,
            "after": after_state,
            "sql": update_sql,
            "elapsed_ms": round(elapsed_ms, 2)
        }

    def delete_record(
        self,
        table_name: str,
        filter_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Safely deletes a record by filter criteria and purges FTS index.
        """
        import time
        start_t = time.perf_counter()

        if not filter_data:
            raise ValueError("Filter criteria required for safe deletion to prevent deleting entire table.")

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info(\"{table_name}\");")
            table_cols = {r["name"]: r for r in cur.fetchall()}
            if not table_cols:
                raise ValueError(f"Table '{table_name}' does not exist.")

            where_parts = [f"\"{k}\" = ?" for k in filter_data.keys() if k in table_cols]
            where_vals = [filter_data[k] for k in filter_data.keys() if k in table_cols]
            if not where_parts:
                raise ValueError(f"Filter keys {list(filter_data.keys())} do not match table columns.")
            where_sql = " AND ".join(where_parts)

            # Snapshot deleted record
            cur.execute(f"SELECT * FROM \"{table_name}\" WHERE {where_sql} LIMIT 1;", where_vals)
            target = cur.fetchone()
            if not target:
                return {
                    "operation": "DELETE",
                    "table": table_name,
                    "status": "NOT_FOUND",
                    "affected_rows": 0,
                    "message": f"No record in '{table_name}' matched criteria: {filter_data}"
                }

            deleted_record = dict(target)
            rowid = deleted_record.get("rowid")

            delete_sql = f"DELETE FROM \"{table_name}\" WHERE {where_sql};"
            cur.execute(delete_sql, where_vals)
            affected = cur.rowcount

            # Remove from FTS
            fts_table = f"{table_name}_fts"
            try:
                if rowid is not None:
                    cur.execute(f"DELETE FROM \"{fts_table}\" WHERE rowid = ?;", (rowid,))
            except Exception as fts_err:
                logger.debug(f"FTS delete sync note on {table_name}: {fts_err}")

            conn.commit()

        hot_cache.clear()
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return {
            "operation": "DELETE",
            "table": table_name,
            "status": "SUCCESS",
            "affected_rows": affected,
            "deleted_record": deleted_record,
            "sql": delete_sql,
            "elapsed_ms": round(elapsed_ms, 2)
        }

    def query_tabular(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        filter_condition: Optional[str] = None,
        filter_params: Optional[List[Any]] = None,
        order_by: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Retrieves formatted tabular data for responsive table rendering.
        """
        import time
        start_t = time.perf_counter()

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info(\"{table_name}\");")
            all_cols = [r["name"] for r in cur.fetchall()]
            if not all_cols:
                raise ValueError(f"Table '{table_name}' does not exist.")

            selected_cols = [c for c in (columns or all_cols) if c in all_cols] or all_cols
            cols_sql = ", ".join([f"\"{c}\"" for c in selected_cols])

            where_sql = f" WHERE {filter_condition}" if filter_condition else ""
            order_sql = f" ORDER BY {order_by}" if order_by else ""
            limit_sql = f" LIMIT {min(limit, 50)}"

            sql = f"SELECT {cols_sql} FROM \"{table_name}\"{where_sql}{order_sql}{limit_sql};"
            cur.execute(sql, filter_params or [])
            rows = [dict(r) for r in cur.fetchall()]

            # Total count
            count_sql = f"SELECT COUNT(*) as cnt FROM \"{table_name}\"{where_sql};"
            cur.execute(count_sql, filter_params or [])
            total_count = cur.fetchone()["cnt"]

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return {
            "operation": "TABULAR",
            "table": table_name,
            "columns": selected_cols,
            "records": rows,
            "rows": [[r[c] for c in selected_cols] for r in rows],
            "total_count": total_count,
            "displayed_count": len(rows),
            "sql": sql,
            "elapsed_ms": round(elapsed_ms, 2)
        }

    async def search_text_async(self, query: str, table_name: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Non-blocking async wrapper for full-text search."""
        return await asyncio.to_thread(self.search_text, query, table_name, limit)

    async def get_record_by_id_async(self, table_name: str, id_value: Any) -> Optional[Dict[str, Any]]:
        """Non-blocking async wrapper for PK lookup."""
        return await asyncio.to_thread(self.get_record_by_id, table_name, id_value)

    async def execute_aggregation_async(
        self,
        table_name: str,
        agg_func: str = "COUNT",
        column: str = "*",
        group_by: Optional[str] = None,
        filter_condition: Optional[str] = None,
        filter_params: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """Non-blocking async wrapper for aggregation."""
        return await asyncio.to_thread(
            self.execute_aggregation,
            table_name,
            agg_func,
            column,
            group_by,
            filter_condition,
            filter_params
        )

    async def insert_record_async(self, table_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Non-blocking async wrapper for insert."""
        return await asyncio.to_thread(self.insert_record, table_name, data)

    async def update_record_async(self, table_name: str, filter_data: Dict[str, Any], update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Non-blocking async wrapper for update."""
        return await asyncio.to_thread(self.update_record, table_name, filter_data, update_data)

    async def delete_record_async(self, table_name: str, filter_data: Dict[str, Any]) -> Dict[str, Any]:
        """Non-blocking async wrapper for delete."""
        return await asyncio.to_thread(self.delete_record, table_name, filter_data)

    async def query_tabular_async(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        filter_condition: Optional[str] = None,
        filter_params: Optional[List[Any]] = None,
        order_by: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Non-blocking async wrapper for tabular queries."""
        return await asyncio.to_thread(
            self.query_tabular,
            table_name,
            columns,
            filter_condition,
            filter_params,
            order_by,
            limit
        )
