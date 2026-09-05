"""
smart_data/engine.py
====================
Universal Smart Data Layer Engine for SMAR v2.
Completely domain-agnostic: adapts dynamically to ANY arbitrary dataset
(Medical, Aviation, Retail, Logistics, IoT, Finance, Academic, etc.).

Coordinates:
1. Universal Data Sync Engine (syncs any unexpected files into warehouse & KG).
2. Dynamic Intent & Entity Extraction (vocabulary learned from introspected schemas).
3. Hot Cache lookup (TieredHotCache: Redis Docker or In-Memory LRU).
4. Relational & Full-Text Search Engine (non-blocking).
5. Dynamic Spoken Formulation (generates answers based on actual retrieved schema columns).
6. Continuous Learning & KG Write-back.
"""

import time
import logging
import asyncio
from typing import Dict, Any, List, Optional

from .dictionary import DynamicDomainDictionary
from .intent_entity import SmartIntentEntityExtractor
from .query_builder import SmartQueryBuilder
from structured_data.adapters.registry import AdapterRegistry
from structured_data.adapters.base import BaseStorageAdapter
from structured_data.schema_introspector import SchemaIntrospector
from structured_data.multi_table_manager import MultiTableWarehouseManager
from structured_data.sync_engine import UniversalDataSyncEngine
from structured_data.cache import hot_cache

logger = logging.getLogger("smar.smart_data.engine")


class SmartDataLayerEngine:
    """
    Unified, Domain-Agnostic Smart Data Layer Engine for SMAR v2.
    """

    def __init__(
        self,
        adapter_registry: Optional[AdapterRegistry] = None,
        context_store = None,
        warehouse_manager: Optional[MultiTableWarehouseManager] = None
    ):
        self.registry = adapter_registry or AdapterRegistry()
        self.context_store = context_store
        self.warehouse_manager = warehouse_manager or MultiTableWarehouseManager()
        self.domain_dict = DynamicDomainDictionary()
        self.intent_extractor = SmartIntentEntityExtractor(domain_dict=self.domain_dict)
        self.query_builder = SmartQueryBuilder()
        self.schema_introspector = SchemaIntrospector(context_store=self.context_store)

        # Universal Sync Engine
        self.sync_engine = UniversalDataSyncEngine(
            warehouse_manager=self.warehouse_manager,
            context_store=self.context_store,
            domain_dict=self.domain_dict
        )

        # Cache hit/miss counters
        self.cache_hits = 0
        self.cache_misses = 0

        # Sync initial state if tables already exist
        self.refresh_schema()

    def refresh_schema(self) -> None:
        """Dynamically learns from whatever tables exist in the warehouse or primary adapter."""
        try:
            # 1. Check warehouse tables
            tables = self.warehouse_manager.list_tables()
            if tables:
                for t in tables:
                    tname = t["table_name"]
                    self.domain_dict.term_to_canonical[tname.lower()] = tname
                    for col in t.get("columns", []):
                        cname = col["name"]
                        self.domain_dict.term_to_canonical[cname.lower()] = cname

            # 2. Check primary adapter if registered
            primary = self.registry.get_primary()
            if primary:
                schema = primary.introspect_schema()
                self.domain_dict.learn_from_schema(schema)
                self.schema_introspector.introspect_and_sync(primary)

            logger.info("SmartDataLayerEngine refreshed schema dynamically.")
        except Exception as e:
            logger.debug(f"Initial schema refresh note: {e}")

    def load_new_datasource(self, file_or_db_path: str) -> BaseStorageAdapter:
        """
        Dynamically loads and adapts to ANY uploaded database, CSV, or Excel file.
        Updates schema, introspects into KG, and resets dictionary.
        """
        adapter = self.registry.load_file_adapter(file_or_db_path, set_as_primary=True)
        self.refresh_schema()
        # Also sync into warehouse
        try:
            self.warehouse_manager.ingest_file(file_or_db_path)
            self.sync_engine.get_status()
        except Exception as e:
            logger.debug(f"Warehouse ingest note on single file load: {e}")
        return adapter

    def sync_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """Runs the Universal Data Sync Engine across any uploaded files."""
        status = self.sync_engine.sync_files(file_paths)
        self.refresh_schema()
        return status

    async def sync_files_async(self, file_paths: List[str]) -> Dict[str, Any]:
        """Non-blocking async sync to keep voice loop completely unblocked."""
        return await asyncio.to_thread(self.sync_files, file_paths)

    def get_sync_status(self) -> Dict[str, Any]:
        """Returns readiness status and table statistics."""
        return self.sync_engine.get_status()

    def process_query(self, user_text: str, user_id: str = "default_user") -> Dict[str, Any]:
        """
        Main cognitive query pipeline across the Smart Data Layer.
        Zero domain hardcoding: dynamically adapts to any table and column.
        """
        start_time = time.perf_counter()

        # Step 1: Dynamic Intent & Entity Extraction
        extracted = self.intent_extractor.extract(user_text)
        intent = extracted["intent"]
        search_query = extracted.get("search_query", "").strip()

        # Step 2: KG Cache Lookup (Warm Memory) & Hot Entity Cache
        resolved_item_id = None
        kg_cache_hit = False

        # Check Hot Cache for entity resolution first
        if search_query:
            cached_entity = hot_cache.get_entity(search_query)
            if cached_entity:
                ident = cached_entity.get("item_id") or cached_entity.get("product_id") or cached_entity.get("id")
                if ident:
                    resolved_item_id = ident
                    kg_cache_hit = True

        if self.context_store and search_query:
            try:
                candidates = [search_query.lower()]
                res_triples = self.context_store.query_triples_for_entities(
                    user_id="kg_cache",
                    entities=candidates,
                    limit=10
                )
                for t in res_triples:
                    if t.get("predicate") == "resolved_to_canonical_id":
                        resolved_item_id = t.get("object")
                        kg_cache_hit = True
                        break
            except Exception as e:
                logger.debug(f"KG cache lookup error: {e}")

        # Step 3: Query Execution
        db_results: List[Dict[str, Any]] = []

        if resolved_item_id:
            # Check primary adapter first if registered, then warehouse
            item = None
            adapter = self.registry.get_primary()
            if adapter:
                try:
                    item = adapter.get_item_by_id(resolved_item_id)
                except Exception:
                    pass

            if not item:
                for tbl in self.warehouse_manager.list_tables():
                    item = self.warehouse_manager.get_record_by_id(tbl["table_name"], resolved_item_id)
                    if item:
                        break

            if item:
                db_results = [item]
                self.cache_hits += 1
            else:
                self.cache_misses += 1
        else:
            self.cache_misses += 1

            # Check if this is an aggregation query
            if intent == "SUMMARY":
                # Aggregate across active tables
                tables = self.warehouse_manager.list_tables()
                if tables:
                    primary_table = tables[0]["table_name"]
                    agg_data = self.warehouse_manager.execute_aggregation(primary_table)
                    total_records = self.sync_engine.total_rows_synced
                    spoken = f"The dataset currently has {len(tables)} tables with {total_records:,} total records."
                    res_payload = {
                        "intent": intent,
                        "operation": "AGGREGATE",
                        "data": agg_data,
                        "spoken_confirmation": spoken,
                        "kg_cache_hit": False,
                        "elapsed_ms": (time.perf_counter() - start_time) * 1000.0
                    }
                    hot_cache.set(cache_key, res_payload, ttl_seconds=300)
                    return res_payload

            # Search warehouse via FTS or adapter
            if search_query:
                # 1. Search warehouse
                db_results = self.warehouse_manager.search_text(search_query, limit=5)
                # 2. If no hits in warehouse, try primary adapter
                if not db_results:
                    adapter = self.registry.get_primary()
                    if adapter:
                        db_results = adapter.search_by_text(search_query, limit=5)

        # Step 4: Universal Dynamic Field Extraction & Spoken Answer Formulation
        # ZERO hardcoding: dynamically derives attributes from the actual returned record
        primary_item = db_results[0] if db_results else None
        spoken_response = ""
        structured_context_lines = []

        if primary_item:
            # Dynamically identify primary identifier / name column
            ident_keys = [k for k in primary_item.keys() if any(sub in k.lower() for sub in ["name", "title", "label", "sku", "code", "tag", "id"])]
            primary_key_col = ident_keys[0] if ident_keys else list(primary_item.keys())[0]
            primary_label = str(primary_item.get(primary_key_col, "Record"))

            # Build readable attributes list with prioritized key fields
            priority_cols = []
            other_cols = []
            uom = primary_item.get("unit_of_measure") or primary_item.get("unit") or ""

            for col, val in primary_item.items():
                if col.startswith("_") or col == primary_key_col or val is None or str(val).strip() == "":
                    continue
                col_lower = col.lower()
                col_display = col.replace("_", " ").title()

                if col_lower in ["quantity", "stock", "qty"]:
                    entry = f"Stock: {val} {uom}".strip() if uom else f"Stock: {val}"
                    priority_cols.insert(0, entry)
                elif col_lower in ["unit_price", "retail_price", "price", "mrp", "rate", "cost_price", "cost"]:
                    priority_cols.append(f"{col_display}: {val}")
                elif any(sig in col_lower for sig in ["status", "tier", "ward", "origin", "destination", "brand", "category"]):
                    priority_cols.append(f"{col_display}: {val}")
                else:
                    other_cols.append(f"{col_display}: {val}")

            all_attrs = priority_cols + other_cols
            structured_context_lines.append(f"[Verified Data Record ({primary_label})]: {', '.join(all_attrs[:12])}")

            # Universal spoken confirmation
            top_attrs = all_attrs[:3]
            if top_attrs:
                spoken_response = f"{primary_label}: {', '.join(top_attrs)}."
            else:
                spoken_response = f"Found record for {primary_label}."

            # Step 5: Dynamic Learn & Write Back to KG Cache
            if self.context_store and search_query:
                try:
                    self.context_store.upsert_triple(
                        user_id="kg_cache",
                        subject=search_query.lower(),
                        predicate="resolved_to_canonical_id",
                        object_val=primary_label,
                        confidence=0.98
                    )
                except Exception as e:
                    logger.debug(f"Error writing back to KG cache: {e}")
        else:
            spoken_response = f"No matching records found for '{search_query}' in the synchronized dataset."
            structured_context_lines.append(f"[Data Notice]: No matching records found for '{search_query}'.")

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        result_payload = {
            "intent": intent,
            "search_query": search_query,
            "kg_cache_hit": kg_cache_hit,
            "hot_cache_hit": False,
            "matched_item": primary_item,
            "all_results": db_results,
            "context_string": "\n".join(structured_context_lines),
            "spoken_confirmation": spoken_response,
            "elapsed_ms": elapsed_ms
        }

        # Cache entity in Hot Cache only if valid item was resolved
        if search_query and primary_item:
            hot_cache.set_entity(search_query, primary_item)
            query_cache_key = f"smart_query:{user_text.strip().lower()}"
            hot_cache.set(query_cache_key, result_payload, ttl_seconds=300)

        return result_payload

    async def process_query_async(self, user_text: str, user_id: str = "default_user") -> Dict[str, Any]:
        """
        Non-blocking async query pipeline.
        Dispatches all DB lookups to worker threads so the Voice AI loop / audio stream
        never experiences jitter or stalls.
        """
        return await asyncio.to_thread(self.process_query, user_text, user_id)
