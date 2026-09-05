"""
structured_data/sync_engine.py
===============================
Universal Data Sync Engine for SMAR v2.
Accepts COMPLETELY RANDOM, UNEXPECTED files (CSV, Excel, SQLite) of any domain:
Medical, Logistics, Finance, Aviation, Retail, Academic, IoT, etc.

Synchronizes:
1. Universal chunked streaming ingestion into high-performance warehouse database.
2. Relational and schema introspection.
3. Knowledge Graph structural and semantic sync (into `system_schema` partition).
4. Dynamic domain vocabulary and entity extraction learning.
5. Hot Cache layer warming (Redis Docker or In-Memory LRU).
6. Transitions state to "ready_to_answer" with comprehensive readiness metrics.
"""

import os
import time
import logging
import asyncio
from typing import Dict, Any, List, Optional
import pandas as pd

from structured_data.multi_table_manager import MultiTableWarehouseManager
from structured_data.schema_introspector import SchemaIntrospector
from structured_data.cache import hot_cache

logger = logging.getLogger("smar.sync_engine")


class UniversalDataSyncEngine:
    """
    Universal Data Sync Engine that adapts to ANY arbitrary uploaded dataset.
    """

    def __init__(
        self,
        warehouse_manager: Optional[MultiTableWarehouseManager] = None,
        context_store = None,
        domain_dict = None
    ):
        self.warehouse_manager = warehouse_manager or MultiTableWarehouseManager()
        self.context_store = context_store
        self.domain_dict = domain_dict
        self.schema_introspector = SchemaIntrospector(context_store=self.context_store)

        # State tracking
        self.status = "uninitialized"  # "uninitialized" | "syncing" | "ready_to_answer" | "error"
        self.last_sync_time: Optional[float] = None
        self.sync_duration_sec: float = 0.0
        self.synced_tables: List[Dict[str, Any]] = []
        self.total_rows_synced: int = 0
        self.schema_triples_synced: int = 0
        self.error_message: Optional[str] = None

        # Check existing tables on startup
        self._check_initial_state()

    def _check_initial_state(self):
        try:
            tables = self.warehouse_manager.list_tables()
            if tables:
                self.synced_tables = tables
                self.total_rows_synced = sum(t.get("row_count", 0) for t in tables)
                self.status = "ready_to_answer"
                logger.info(f"SyncEngine initialized with existing warehouse: {len(tables)} tables, {self.total_rows_synced:,} rows.")
        except Exception as e:
            logger.debug(f"SyncEngine initial check note: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive readiness status for frontend and API."""
        cache_stats = hot_cache.stats()
        return {
            "status": self.status,
            "ready_to_answer": (self.status == "ready_to_answer"),
            "message": (
                f"Ready to answer queries across {len(self.synced_tables)} tables ({self.total_rows_synced:,} records)."
                if self.status == "ready_to_answer"
                else ("Syncing in progress..." if self.status == "syncing" else "No data synchronized yet.")
            ),
            "tables_count": len(self.synced_tables),
            "total_rows": self.total_rows_synced,
            "schema_triples_in_kg": self.schema_triples_synced,
            "tables": self.synced_tables,
            "last_sync_time": self.last_sync_time,
            "sync_duration_sec": self.sync_duration_sec,
            "cache_engine": cache_stats.get("active_engine", "in_memory_lru"),
            "is_redis": cache_stats.get("is_redis", False),
            "error": self.error_message
        }

    def sync_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Main synchronization pipeline:
        Ingests files -> Introspects Schema -> Syncs to KG -> Learns Vocabulary -> Warms Cache.
        """
        start_time = time.perf_counter()
        self.status = "syncing"
        self.error_message = None

        logger.info(f"UniversalDataSyncEngine: Starting sync for {len(file_paths)} files...")

        try:
            # Stage 1: Chunked Ingestion of all files
            ingest_results = []
            for fp in file_paths:
                if not os.path.exists(fp):
                    continue
                res = self.warehouse_manager.ingest_file(fp)
                ingest_results.append(res)

            # Stage 2: Discover all tables and row counts
            tables = self.warehouse_manager.list_tables()
            self.synced_tables = tables
            self.total_rows_synced = sum(t.get("row_count", 0) for t in tables)

            # Stage 3: Introspect multi-table schema into Knowledge Graph
            schema_triples = self.schema_introspector.introspect_multi_table(
                self.warehouse_manager,
                schema_user_id="system_schema"
            )
            self.schema_triples_synced = len(schema_triples)

            # Stage 4: Dynamically learn vocabulary in domain dictionary
            if self.domain_dict:
                for t in tables:
                    tname = t["table_name"]
                    self.domain_dict.term_to_canonical[tname.lower()] = tname
                    for col in t.get("columns", []):
                        cname = col["name"]
                        self.domain_dict.term_to_canonical[cname.lower()] = cname

            # Stage 5: Cache warming & query cache invalidation
            hot_cache.clear()
            hot_cache.set("schema:warehouse:tables", tables, ttl_seconds=3600)
            hot_cache.set("schema:warehouse:triples_count", len(schema_triples), ttl_seconds=3600)

            self.status = "ready_to_answer"
            self.sync_duration_sec = round(time.perf_counter() - start_time, 3)
            self.last_sync_time = time.time()

            logger.info(
                f"SUCCESS: Synchronized {len(tables)} tables ({self.total_rows_synced:,} records) "
                f"and {len(schema_triples)} KG schema triples in {self.sync_duration_sec}s. Ready to answer!"
            )

            return self.get_status()

        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            logger.error(f"Error during UniversalDataSyncEngine sync: {e}", exc_info=True)
            return self.get_status()

    async def sync_files_async(self, file_paths: List[str]) -> Dict[str, Any]:
        """Non-blocking async sync to prevent blocking FastAPI event loop or voice stream."""
        return await asyncio.to_thread(self.sync_files, file_paths)
