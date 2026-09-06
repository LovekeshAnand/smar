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

import re
import time
import logging
import asyncio
from typing import Dict, Any, List, Optional

from .dictionary import DynamicDomainDictionary
from .intent_entity import SmartIntentEntityExtractor
from .query_builder import SmartQueryBuilder
from .operations import OperationsAnalyzer
from .visualizer import AdaptiveDataVisualizer
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
        self.operations_analyzer = OperationsAnalyzer(
            warehouse_manager=self.warehouse_manager,
            domain_dict=self.domain_dict
        )
        self.visualizer = AdaptiveDataVisualizer()

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
                self.domain_dict.learn_from_schema({"tables": tables})

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

    def reset(self) -> Dict[str, Any]:
        """Resets the sync engine and cache state."""
        self.sync_engine.reset()
        hot_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        return self.get_sync_status()

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

        # Step 2: KG Cache Lookup (Warm Memory), Dynamic Entity Resolution & Hot Entity Cache
        resolved_item_id = None
        target_table = None
        kg_cache_hit = False

        # Identify target table if any table entity or column matched in domain vocabulary
        tables_list = self.warehouse_manager.list_tables()
        table_lookup = {t["table_name"].lower(): t["table_name"] for t in tables_list}

        for me in extracted.get("matched_entities", []):
            canon = me.get("canonical", "").lower()
            if canon in table_lookup:
                target_table = table_lookup[canon]
                break
            if canon in self.domain_dict.column_to_table:
                target_table = self.domain_dict.column_to_table[canon]
                break

        # Check for direct numeric or alphanumeric ID candidates from user speech
        # Use the normalized text's candidates (post STT-normalization)
        code_candidates = extracted.get("code_candidates", [])
        if code_candidates:
            resolved_item_id = code_candidates[0]

        # Check if the query is purely conversational, greeting, self-identity, or session recall
        lower_raw = user_text.strip().lower()
        conversational_patterns = [
            r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|namaste)\b",
            r"(?:what(?:'s|\s+is)\s+your\s+name|who\s+are\s+you)\b",
            r"(?:what(?:'s|\s+is)\s+my\s+name|who\s+am\s+i)\b",
            r"(?:pronounce\s+my\s+name|say\s+my\s+name|repeat\s+my\s+name|spell\s+my\s+name)\b",
            r"(?:no\s+my\s+name\s+not\s+yours|i\s+meant\s+my\s+name|not\s+your\s+name\s+my\s+name)\b",
            r"(?:what\s+did\s+i\s+ask|what\s+was\s+(?:the\s+)?(?:1st|first|previous|last)\s+question|i\s+forgot\s+what\s+was)\b",
            r"^(?:how\s+are\s+you|what\s+can\s+you\s+do|help\s+me)\b",
            r"(?:do\s+you\s+have\s+any\s+information\s+about\s+me|what\s+do\s+you\s+know\s+about\s+me)\b",
            r"\b(?:i\s+live\s+in|i\s+work\s+as|my\s+name\s+is|i\s+am\s+a|i\s+don't\s+live\s+in|update\s+(?:it\s+in\s+)?(?:your\s+)?memory|remember\s+(?:that)?|keep\s+in\s+mind|note\s+that|let\s+you\s+know)\b"
        ]
        is_pure_conversation = any(re.search(p, lower_raw) for p in conversational_patterns)

        # If it's a conversational or meta query with NO warehouse table/column/code entity, bypass database search
        if is_pure_conversation and not target_table and not code_candidates:
            return {
                "intent": "CONVERSATION",
                "search_query": "",
                "kg_cache_hit": False,
                "hot_cache_hit": False,
                "matched_item": None,
                "all_results": [],
                "context_string": "",
                "spoken_confirmation": "",
                "elapsed_ms": (time.perf_counter() - start_time) * 1000.0
            }

        # Step 2A: Check for Operations (Aggregations, CRUD Mutations, Tabular Views)
        # GUARD: If the user is querying about a specific single entity (order, employee, product)
        # by ID with aggregation keywords — prefer entity lookup + relational enrichment.
        # This prevents "total price for order 292487" from running SUM(order_id) instead of
        # properly aggregating order_items for that specific order.
        # NOTE: This guard only suppresses AGGREGATION — TABULAR, VISUAL, INSERT, UPDATE,
        # DELETE always go through the operations path regardless.
        _single_entity_agg_query = (
            len(code_candidates) == 1 and
            len(str(code_candidates[0])) >= 3 and
            any(kw in user_text.lower() for kw in [
                "order", "employee", "product", "item", "customer", "shipment", "payment", "return"
            ])
        )
        _is_op = self.operations_analyzer.is_operation_query(user_text)
        if _is_op:
            plan = self.operations_analyzer.parse_plan(user_text, tables_list)
            # Skip aggregation plans for single-entity queries — handled by entity lookup below
            if plan and plan.get("operation") == "AGGREGATION" and _single_entity_agg_query:
                plan = None  # Fall through to entity lookup

            if plan:
                op_type = plan.get("operation")
                op_res: Dict[str, Any] = {}
                spoken_response = ""
                context_str = ""
                chart = None

                try:
                    if op_type == "AGGREGATION":
                        op_res = self.warehouse_manager.execute_aggregation(
                            table_name=plan["table"],
                            agg_func=plan["function"],
                            column=plan["column"],
                            group_by=plan.get("group_by"),
                            filter_condition=plan.get("filter_condition"),
                            filter_params=plan.get("filter_params")
                        )
                        if plan.get("wants_visual") or plan.get("group_by"):
                            chart = self.visualizer.generate_chart_for_operation(op_res)

                        if plan['function'] == 'COUNT' and (plan['column'] in ('*', 'total') or plan['column'].endswith('_id') or plan['column'] == 'id'):
                            col_disp = plan['table']
                        else:
                            col_disp = plan['column'].replace('_', ' ')
                        filter_desc = plan.get("filter_description")
                        if plan.get("group_by"):
                            grp_disp = plan['group_by'].replace('_', ' ')
                            spoken_response = f"Here is the {plan['function'].lower()} of {col_disp} grouped by {grp_disp} across {plan['table']}."
                            context_str = f"[Verified Aggregation Result]: {plan['function']} of {col_disp} grouped by {grp_disp} on table '{plan['table']}'. Breakdown: {op_res.get('breakdown')} (SQL: {op_res.get('sql')})"
                        elif filter_desc:
                            val_disp = op_res.get("formatted_value", op_res.get("value"))
                            cnt_rows = op_res.get("total_rows_evaluated", 0)
                            spoken_response = f"The {plan['function'].lower()} of {col_disp} in {plan['table']} for {filter_desc} is {val_disp} (evaluated across {cnt_rows} records)."
                            context_str = f"[Verified Aggregation Result]: {plan['function']}({col_disp}) on table '{plan['table']}' where {filter_desc} = {val_disp} across {cnt_rows} records (SQL: {op_res.get('sql')})"
                        else:
                            val_disp = op_res.get("formatted_value", op_res.get("value"))
                            cnt_rows = op_res.get("total_rows_evaluated", 0)
                            spoken_response = f"The {plan['function'].lower()} of {col_disp} in {plan['table']} is {val_disp} across {cnt_rows} records."
                            context_str = f"[Verified Aggregation Result]: {plan['function']}({col_disp}) on table '{plan['table']}' = {val_disp} across {cnt_rows} rows (SQL: {op_res.get('sql')})"

                    elif op_type == "INSERT":
                        op_res = self.warehouse_manager.insert_record(
                            table_name=plan["table"],
                            data=plan["data"]
                        )
                        new_id = op_res.get("inserted_id")
                        spoken_response = f"Successfully added a new record into {plan['table']} with ID {new_id}."
                        context_str = f"[Database Insert Executed]: Added new record into '{plan['table']}' with ID {new_id} (SQL: {op_res.get('sql')})"

                    elif op_type == "UPDATE":
                        op_res = self.warehouse_manager.update_record(
                            table_name=plan["table"],
                            filter_data=plan["filter"],
                            update_data=plan["updates"]
                        )
                        if op_res.get("status") == "SUCCESS":
                            diff_strs = [f"{k} changed to {v.get('after')}" for k, v in op_res.get("diff", {}).items()]
                            filter_str = ", ".join([f"{k} {v}" for k, v in plan["filter"].items()])
                            spoken_response = f"Successfully updated {plan['table']} ({filter_str}): {', '.join(diff_strs)}."
                            context_str = f"[Database Update Executed]: Updated '{plan['table']}' ({filter_str}): {', '.join(diff_strs)} (SQL: {op_res.get('sql')})"
                        else:
                            spoken_response = f"Could not find any record in {plan['table']} matching {plan['filter']} to update."
                            context_str = f"[Database Update Notice]: Record not found in '{plan['table']}'."

                    elif op_type == "DELETE":
                        op_res = self.warehouse_manager.delete_record(
                            table_name=plan["table"],
                            filter_data=plan["filter"]
                        )
                        if op_res.get("status") == "SUCCESS":
                            filter_str = ", ".join([f"{k} {v}" for k, v in plan["filter"].items()])
                            spoken_response = f"Successfully deleted record from {plan['table']} ({filter_str})."
                            context_str = f"[Database Delete Executed]: Deleted from '{plan['table']}' ({filter_str}) (SQL: {op_res.get('sql')})"
                        else:
                            spoken_response = f"Could not find record in {plan['table']} matching {plan['filter']} to delete."
                            context_str = f"[Database Delete Notice]: Record not found in '{plan['table']}'."

                    elif op_type == "TABULAR":
                        op_res = self.warehouse_manager.query_tabular(
                            table_name=plan["table"],
                            limit=plan.get("limit", 10)
                        )
                        if plan.get("wants_visual"):
                            chart = self.visualizer.generate_chart_for_operation(op_res)
                        spoken_response = f"Displaying {op_res.get('displayed_count')} records from {plan['table']} in table format."
                        context_str = f"[Verified Tabular Query]: Retrieved {op_res.get('displayed_count')} rows from '{plan['table']}' (Total: {op_res.get('total_count')}, SQL: {op_res.get('sql')})"

                    # Construct table_data if tabular query or if aggregation has sample records
                    table_data_payload = op_res if op_type == "TABULAR" else None
                    if not table_data_payload and op_res.get("sample_records"):
                        s_recs = op_res["sample_records"]
                        s_cols = list(s_recs[0].keys()) if s_recs else []
                        table_data_payload = {
                            "operation": "TABULAR",
                            "table": plan["table"],
                            "columns": s_cols,
                            "rows": [[r.get(c) for c in s_cols] for r in s_recs],
                            "records": s_recs,
                            "total_count": op_res.get("total_rows_evaluated", len(s_recs)),
                            "displayed_count": len(s_recs),
                            "sql": op_res.get("sql"),
                            "elapsed_ms": op_res.get("elapsed_ms")
                        }

                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    return {
                        "intent": "OPERATION",
                        "operation": op_type,
                        "operation_details": op_res,
                        "table_data": table_data_payload,
                        "visual_chart": chart,
                        "search_query": user_text,
                        "kg_cache_hit": False,
                        "hot_cache_hit": False,
                        "matched_item": None,
                        "all_results": op_res.get("records", []) if op_type == "TABULAR" else [],
                        "context_string": context_str,
                        "spoken_confirmation": spoken_response,
                        "elapsed_ms": elapsed_ms
                    }
                except Exception as op_err:
                    logger.error(f"Error executing operation plan: {op_err}")

        # Check Hot Cache for entity resolution
        if not resolved_item_id and search_query:
            cached_entity = hot_cache.get_entity(search_query)
            if cached_entity:
                ident = cached_entity.get("item_id") or cached_entity.get("product_id") or cached_entity.get("id")
                if ident:
                    resolved_item_id = ident
                    kg_cache_hit = True

        if not resolved_item_id and self.context_store and search_query and not _is_op and intent != "SUMMARY":
            try:
                candidates = [search_query.lower()]
                res_triples = self.context_store.query_triples_for_entities(
                    user_id="kg_cache",
                    entities=candidates,
                    limit=10
                )
                for t in res_triples:
                    if t.get("predicate") == "resolved_to_canonical_id":
                        cand_val = t.get("object")
                        if cand_val and isinstance(cand_val, (int, str)):
                            s_val = str(cand_val).strip()
                            # Extract numeric ID if stored as "Table#123"
                            if "#" in s_val:
                                s_val = s_val.split("#")[-1].strip()
                            # Only accept if it looks like a real ID/code (no long sentences)
                            if s_val and len(s_val) <= 30 and (" " not in s_val or s_val.isdigit()):
                                resolved_item_id = s_val
                                kg_cache_hit = True
                                break
            except Exception as e:
                logger.debug(f"KG cache lookup error: {e}")

        # Step 3: Query Execution
        db_results: List[Dict[str, Any]] = []

        if resolved_item_id:
            item = None

            # Try each candidate ID until we find a match (handles multi-chunk STT IDs)
            candidates_to_try = list(dict.fromkeys(code_candidates)) if code_candidates else [resolved_item_id]

            for candidate_id in candidates_to_try:
                item = None
                candidate_int = int(candidate_id) if str(candidate_id).isdigit() else None

                # If a specific table was identified from user speech, look there first
                if target_table:
                    item = self.warehouse_manager.get_record_by_id(target_table, candidate_id)
                    if not item and candidate_int is not None:
                        item = self.warehouse_manager.get_record_by_id(target_table, candidate_int)
                    if item:
                        item["_source_table"] = target_table

                # Check primary adapter
                if not item:
                    adapter = self.registry.get_primary()
                    if adapter:
                        try:
                            item = adapter.get_item_by_id(candidate_id)
                        except Exception:
                            pass

                # Scan all warehouse tables with context-aware ordering
                if not item:
                    lower_user_raw = user_text.lower()

                    # Determine preferred table scan order based on user's entity keywords
                    preferred_first = []
                    if any(kw in lower_user_raw for kw in ["order item", "item id", "order_item"]):
                        preferred_first = ["order_items"]
                    elif any(kw in lower_user_raw for kw in ["order id", "order number", "order no", "order #"]):
                        # User explicitly said "order id" → check orders table first
                        preferred_first = ["orders", "shipments", "payments"]
                    elif any(kw in lower_user_raw for kw in ["employee id", "employee number", "employee no"]):
                        preferred_first = ["employees"]
                    elif any(kw in lower_user_raw for kw in ["product id", "product number"]):
                        preferred_first = ["products"]
                    elif any(kw in lower_user_raw for kw in ["customer id", "customer number"]):
                        preferred_first = ["customers"]
                    elif any(kw in lower_user_raw for kw in ["shipment id", "shipment"]):
                        preferred_first = ["shipments"]

                    # Reorder tables: preferred first, then the rest
                    ordered_tables = (
                        [t for t in tables_list if t["table_name"] in preferred_first] +
                        [t for t in tables_list if t["table_name"] not in preferred_first]
                    )

                    for tbl in ordered_tables:
                        tname = tbl["table_name"]
                        item = self.warehouse_manager.get_record_by_id(tname, candidate_id)
                        if not item and candidate_int is not None:
                            item = self.warehouse_manager.get_record_by_id(tname, candidate_int)
                        if item:
                            item["_source_table"] = tname
                            break

                if item:
                    resolved_item_id = candidate_id  # Lock in the winning candidate
                    break

            if item:
                db_results = [item]
                self.cache_hits += 1
            else:
                self.cache_misses += 1

        # If direct ID lookup yielded no results, search via FTS / text search
        if not db_results:
            self.cache_misses += 1

            # Check if this is a SUMMARY or TABULAR query
            # SUMMARY intent fires for generic "show me all" — but if the user
            # mentioned a specific table or tabular keyword, prefer TABULAR.
            _tabular_keywords_present = any(
                kw in user_text.lower()
                for kw in ["in a table", "in table", "show all", "list all", "show me all",
                           "display all", "tabular", "in table format", "as a table",
                           "all stores", "all employees", "all products", "all orders",
                           "all customers", "all suppliers", "all categories"]
            )
            if intent == "SUMMARY" and not _tabular_keywords_present:
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
                    _summary_cache_key = f"summary:{len(tables)}:{total_records}"
                    hot_cache.set(_summary_cache_key, res_payload, ttl_seconds=300)
                    return res_payload

            # If tabular keywords detected and no ID found → force TABULAR operation
            if _tabular_keywords_present and not resolved_item_id:
                tab_plan = self.operations_analyzer.parse_plan(user_text, tables_list)
                # If parse_plan returned None, infer target table from domain vocabulary
                if not tab_plan:
                    _lower = user_text.lower()
                    inferred_table = None
                    for tname_lower, tname_orig in table_lookup.items():
                        singular = tname_lower[:-1] if tname_lower.endswith("s") else tname_lower
                        if tname_lower in _lower or singular in _lower:
                            inferred_table = tname_orig
                            break
                    if inferred_table:
                        tab_plan = {"operation": "TABULAR", "table": inferred_table, "limit": 10, "wants_visual": False}
                if tab_plan and tab_plan.get("operation") == "TABULAR":
                    try:
                        op_res = self.warehouse_manager.query_tabular(
                            table_name=tab_plan["table"],
                            limit=tab_plan.get("limit", 10)
                        )
                        wants_visual = tab_plan.get("wants_visual", False)
                        chart = self.visualizer.generate_chart_for_operation(op_res) if wants_visual else None
                        spoken_response = f"Displaying {op_res.get('displayed_count')} records from {tab_plan['table']}."
                        context_str = (
                            f"[Verified Tabular Query]: Retrieved {op_res.get('displayed_count')} rows "
                            f"from '{tab_plan['table']}' (Total: {op_res.get('total_count')}, SQL: {op_res.get('sql')})"
                        )
                        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                        return {
                            "intent": "OPERATION",
                            "operation": "TABULAR",
                            "operation_details": op_res,
                            "table_data": op_res,
                            "visual_chart": chart,
                            "search_query": user_text,
                            "kg_cache_hit": False,
                            "hot_cache_hit": False,
                            "matched_item": None,
                            "all_results": op_res.get("records", []),
                            "context_string": context_str,
                            "spoken_confirmation": spoken_response,
                            "elapsed_ms": elapsed_ms
                        }
                    except Exception as tab_err:
                        logger.error(f"Forced TABULAR query error: {tab_err}")

            # Search warehouse via FTS or adapter

            query_str = search_query if search_query else user_text.strip()
            if query_str:
                # 1. Search warehouse using search_query
                db_results = self.warehouse_manager.search_text(query_str, limit=5)
                # 2. Also try raw user text if search_query had no hits
                if not db_results and user_text.strip() != query_str:
                    db_results = self.warehouse_manager.search_text(user_text.strip(), limit=5)
                # 3. If no hits in warehouse, try primary adapter
                if not db_results:
                    adapter = self.registry.get_primary()
                    if adapter:
                        db_results = adapter.search_by_text(query_str, limit=5)

        # Step 4: Universal Dynamic Field Extraction & Spoken Answer Formulation
        # ZERO hardcoding: dynamically derives attributes from the actual returned record.
        # Handles order_item vs order hierarchy, computed totals, and cross-entity enrichment.
        primary_item = db_results[0] if db_results else None
        spoken_response = ""
        structured_context_lines = []

        if primary_item:
            source_table = primary_item.get("_source_table", "")
            lower_user = user_text.lower()

            # ---------------------------------------------------------------
            # HIERARCHY DISAMBIGUATION: order_items vs orders
            # When user says "order id X" but X is actually an order_item_id,
            # we enrich the context with the full relational picture and
            # compute the item-level total to prevent LLM hallucination.
            # ---------------------------------------------------------------
            is_order_item = source_table.lower() in ("order_items", "orderitems", "order_item")
            is_order = source_table.lower() in ("orders", "order")
            user_asked_about_order = any(p in lower_user for p in ["order id", "order no", "order number", "order #"])

            if is_order_item:
                oi_id = primary_item.get("order_item_id")
                parent_order_id = primary_item.get("order_id")
                unit_price = primary_item.get("price") or primary_item.get("unit_price") or 0
                qty = primary_item.get("qty") or primary_item.get("quantity") or 1
                product_id = primary_item.get("product_id")
                try:
                    total_item_price = int(unit_price) * int(qty)
                except (TypeError, ValueError):
                    total_item_price = 0

                # Retrieve shipment status for parent order if available
                shipment_info = ""
                try:
                    if parent_order_id:
                        shipment = self.warehouse_manager.get_record_by_id("shipments", parent_order_id, id_column="order_id")
                        if shipment:
                            shipment_info = f", Shipment Status: {shipment.get('status', 'Unknown')}"
                except Exception:
                    pass

                # Build a clear, unambiguous context line
                clarification = " (NOTE: This is an Order ITEM ID, NOT an Order ID.)" if user_asked_about_order else ""
                context_line = (
                    f"[Verified Data Record (Order Item #{oi_id})]{clarification}: "
                    f"This is an ORDER ITEM belonging to parent Order #{parent_order_id}. "
                    f"Product ID: {product_id}, Unit Price: {unit_price}, "
                    f"Quantity: {qty}, Total Item Price: {total_item_price}{shipment_info}. "
                    f"IMPORTANT: The price of this order item is {unit_price} per unit, "
                    f"not {total_item_price}. Total for {qty} units = {total_item_price}."
                )
                structured_context_lines.append(context_line)

                spoken_response = (
                    f"Order Item {oi_id} belongs to Order number {parent_order_id}. "
                    f"Unit price is {unit_price}, quantity is {qty}, "
                    f"so the total for this item is {total_item_price}."
                )

            elif is_order:
                # For orders: aggregate line items to get true total
                order_id_val = primary_item.get("order_id")
                order_date = primary_item.get("order_date", "")
                customer_id = primary_item.get("customer_id")
                store_id = primary_item.get("store_id")

                line_items = []
                order_total = 0
                try:
                    if order_id_val:
                        all_line_items = self.warehouse_manager.search_records_by_field(
                            "order_items", "order_id", order_id_val
                        )
                        for li in all_line_items:
                            up = li.get("price") or 0
                            q = li.get("qty") or 1
                            try:
                                item_total = int(up) * int(q)
                            except (TypeError, ValueError):
                                item_total = 0
                            order_total += item_total
                            line_items.append(
                                f"Item #{li.get('order_item_id')} (Product {li.get('product_id')}): "
                                f"unit price {up} x qty {q} = {item_total}"
                            )
                except Exception as e:
                    logger.debug(f"Order line-item aggregation error: {e}")

                # Get payment info
                payment_amount = ""
                try:
                    if order_id_val:
                        payment = self.warehouse_manager.get_record_by_id("payments", order_id_val, id_column="order_id")
                        if payment:
                            payment_amount = f", Payment Amount: {payment.get('amount')}"
                except Exception:
                    pass

                # Get shipment status
                shipment_status = ""
                try:
                    if order_id_val:
                        shipment = self.warehouse_manager.get_record_by_id("shipments", order_id_val, id_column="order_id")
                        if shipment:
                            shipment_status = f", Shipment Status: {shipment.get('status', 'Unknown')}"
                except Exception:
                    pass

                items_summary = " | ".join(line_items[:10]) if line_items else "No line items found"
                context_line = (
                    f"[Verified Data Record (Order #{order_id_val})]: "
                    f"Order Date: {order_date}, Customer ID: {customer_id}, Store ID: {store_id}, "
                    f"Total Items: {len(line_items)}, Order Total: {order_total}{payment_amount}{shipment_status}. "
                    f"Line Items: {items_summary}"
                )
                structured_context_lines.append(context_line)

                spoken_response = (
                    f"Order {order_id_val} was placed on {order_date} "
                    f"and contains {len(line_items)} item(s) "
                    f"with a total order value of {order_total}."
                )

            else:
                # Generic record: dynamically extract and format
                ident_keys = [k for k in primary_item.keys() if any(sub in k.lower() for sub in ["name", "title", "label", "sku", "code", "tag", "id"])]
                primary_key_col = ident_keys[0] if ident_keys else list(primary_item.keys())[0]
                table_display = (source_table.title()[:-1] if source_table.endswith("s") else source_table.title()) if source_table else ""
                primary_label = f"{table_display} #{primary_item.get(primary_key_col)}" if table_display else str(primary_item.get(primary_key_col, "Record"))

                asked_cols = []
                priority_cols = []
                other_cols = []
                if primary_key_col and primary_key_col in primary_item:
                    priority_cols.append(f"{primary_key_col.replace('_', ' ').title()}: {primary_item[primary_key_col]}")

                uom = primary_item.get("unit_of_measure") or primary_item.get("unit") or ""

                for col, val in primary_item.items():
                    if col.startswith("_") or col == primary_key_col or val is None or str(val).strip() == "":
                        continue
                    col_lower = col.lower()
                    col_display = col.replace("_", " ").title()

                    if col_lower in lower_user or col_display.lower() in lower_user:
                        asked_cols.append(f"{col_display}: {val}")
                    elif col_lower in ["qty", "quantity"]:
                        # In non-order-item context, qty IS inventory stock
                        entry = f"Quantity: {val} {uom}".strip() if uom else f"Quantity: {val}"
                        priority_cols.insert(0, entry)
                    elif col_lower in ["unit_price", "retail_price", "price", "mrp", "rate", "cost_price", "cost", "salary", "amount"]:
                        priority_cols.append(f"{col_display}: {val}")
                    elif any(sig in col_lower for sig in ["status", "tier", "ward", "origin", "destination", "brand", "category", "city", "country", "date"]):
                        priority_cols.append(f"{col_display}: {val}")
                    else:
                        other_cols.append(f"{col_display}: {val}")

                all_attrs = asked_cols + priority_cols + other_cols
                structured_context_lines.append(f"[Verified Data Record ({primary_label})]: {', '.join(all_attrs[:12])}")

                other_ids = [str(r.get(primary_key_col)) for r in db_results[1:5] if r.get(primary_key_col)]
                if other_ids:
                    pk_name = primary_key_col.replace('_', ' ').title()
                    structured_context_lines.append(f"[Other Matching Records Found]: Other {pk_name}s: {', '.join(other_ids)}")

                top_attrs = all_attrs[:3]
                if top_attrs:
                    spoken_response = f"{primary_label}: {', '.join(top_attrs)}."
                else:
                    spoken_response = f"Found record for {primary_label}."

            # Step 5: Dynamic Learn & Write Back to KG Cache (Only for concrete scalar entity IDs)
            if (self.context_store and search_query and not is_pure_conversation 
                and resolved_item_id and db_results and intent != "SUMMARY" and not _is_op):
                generic_words = {"forgot", "question", "1st", "first", "previous", "name", "hello", "what", "all", "table"}
                if not any(w in search_query.lower().split() for w in generic_words):
                    s_id = str(resolved_item_id).strip()
                    if len(s_id) <= 30 and (" " not in s_id or s_id.isdigit()):
                        try:
                            self.context_store.upsert_triple(
                                user_id="kg_cache",
                                subject=search_query.lower(),
                                predicate="resolved_to_canonical_id",
                                object_val=s_id,
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
            "operation": None,
            "operation_details": None,
            "table_data": None,
            "visual_chart": None,
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
