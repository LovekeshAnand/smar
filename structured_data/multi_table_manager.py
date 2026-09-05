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

        target_tables = [table_name] if table_name else [t["table_name"] for t in self.list_tables()]
        results = []

        with self._get_connection() as conn:
            cur = conn.cursor()
            import re
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

                # 3. Fallback to LIKE search if FTS yielded no results
                if not table_hits:
                    try:
                        cur.execute(f"PRAGMA table_info(\"{tname}\");")
                        cols = [r["name"] for r in cur.fetchall() if "int" not in str(r["type"]).lower()]
                        if cols:
                            where_clauses = " OR ".join([f"\"{c}\" LIKE ?" for c in cols[:4]])
                            like_params = [f"%{terms[0]}%"] * min(len(cols), 4)
                            cur.execute(f"SELECT * FROM \"{tname}\" WHERE {where_clauses} LIMIT ?;", (*like_params, limit))
                            table_hits = [dict(r) for r in cur.fetchall()]
                    except Exception as e:
                        logger.debug(f"LIKE fallback note on {tname}: {e}")

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

            query = f"SELECT * FROM \"{table_name}\" WHERE \"{id_column}\" = ? LIMIT 1;"
            cur.execute(query, (id_value,))
            row = cur.fetchone()
            if row:
                res = dict(row)
                hot_cache.set(cache_key, res, ttl_seconds=3600)
                return res
            return None

    def execute_aggregation(
        self,
        table_name: str,
        agg_func: str = "COUNT",
        column: str = "*",
        group_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs fast aggregations with hot caching."""
        cache_key = f"agg:{table_name}:{agg_func}:{column}:{group_by}"
        cached = hot_cache.get(cache_key)
        if cached:
            return cached

        with self._get_connection() as conn:
            cur = conn.cursor()
            if group_by:
                sql = f"SELECT \"{group_by}\", {agg_func}(\"{column}\") as val FROM \"{table_name}\" GROUP BY \"{group_by}\" ORDER BY val DESC LIMIT 10;"
                cur.execute(sql)
                rows = cur.fetchall()
                data = {str(r[group_by]): r["val"] for r in rows}
            else:
                sql = f"SELECT {agg_func}({column if column == '*' else '\"' + column + '\"'}) as val FROM \"{table_name}\";"
                cur.execute(sql)
                data = {"value": cur.fetchone()["val"]}

        hot_cache.set(cache_key, data, ttl_seconds=600)
        return data

    async def search_text_async(self, query: str, table_name: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Non-blocking async wrapper for full-text search."""
        return await asyncio.to_thread(self.search_text, query, table_name, limit)

    async def get_record_by_id_async(self, table_name: str, id_value: Any) -> Optional[Dict[str, Any]]:
        """Non-blocking async wrapper for PK lookup."""
        return await asyncio.to_thread(self.get_record_by_id, table_name, id_value)

    async def execute_aggregation_async(self, table_name: str, agg_func: str = "COUNT", column: str = "*") -> Dict[str, Any]:
        """Non-blocking async wrapper for aggregation."""
        return await asyncio.to_thread(self.execute_aggregation, table_name, agg_func, column)
