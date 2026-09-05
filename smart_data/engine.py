"""
smart_data/engine.py
====================
Core Coordinator for SMAR v2 Smart Data Layer.
Connects the Cognitive Context Layer (Knowledge Graph) with the Structured Data Layer.
Coordinates:
1. Intent Classification & Entity Extraction
2. Query Understanding & Builder
3. KG Cache Lookup (Warm Memory)
4. Smart DB Query Engine (Indexed Access via Adapter)
5. Results Aggregator & Normalizer
6. Learn & Write Back (Updates KG Cache with resolved facts)
"""

import time
import logging
from typing import Dict, Any, List, Optional

from .dictionary import DynamicDomainDictionary
from .intent_entity import SmartIntentEntityExtractor
from .query_builder import SmartQueryBuilder
from structured_data.adapters.registry import AdapterRegistry
from structured_data.adapters.base import BaseStorageAdapter
from structured_data.schema_introspector import SchemaIntrospector

logger = logging.getLogger("smar.smart_data.engine")


class SmartDataLayerEngine:
    """
    Unified Smart Data Layer Engine for SMAR v2.
    """

    def __init__(
        self,
        adapter_registry: Optional[AdapterRegistry] = None,
        context_store = None
    ):
        self.registry = adapter_registry or AdapterRegistry()
        self.context_store = context_store
        self.domain_dict = DynamicDomainDictionary()
        self.intent_extractor = SmartIntentEntityExtractor(domain_dict=self.domain_dict)
        self.query_builder = SmartQueryBuilder()
        self.schema_introspector = SchemaIntrospector(context_store=self.context_store)

        # Cache hit/miss counters for metrics
        self.cache_hits = 0
        self.cache_misses = 0

        # Sync active primary adapter schema if available
        self.sync_active_schema()

    def sync_active_schema(self) -> None:
        """Introspects primary adapter and populates KG and domain dictionary."""
        try:
            adapter = self.registry.get_primary()
            schema = adapter.introspect_schema()
            self.domain_dict.learn_from_schema(schema)
            self.schema_introspector.introspect_and_sync(adapter)
            logger.info(f"SmartDataLayer synced with adapter: {adapter.get_source_name()}")
        except Exception as e:
            logger.warning(f"Could not sync schema on init: {e}")

    def load_new_datasource(self, file_or_db_path: str) -> BaseStorageAdapter:
        """
        Dynamically loads and adapts to ANY uploaded database, CSV, or Excel file.
        Updates schema, introspects into KG, and resets dictionary.
        """
        adapter = self.registry.load_file_adapter(file_or_db_path, set_as_primary=True)
        self.sync_active_schema()
        return adapter

    def process_query(self, user_text: str, user_id: str = "default_user") -> Dict[str, Any]:
        """
        Main cognitive query pipeline across the Smart Data Layer.
        """
        start_time = time.perf_counter()
        adapter = self.registry.get_primary()
        schema_data = adapter.introspect_schema()

        # Step 1: Dynamic Intent & Entity Extraction
        extracted = self.intent_extractor.extract(user_text)
        intent = extracted["intent"]
        search_query = extracted.get("search_query", "").strip()

        # Step 2: KG Cache Lookup (Check if entity was previously resolved in KG)
        resolved_item_id = None
        kg_cache_hit = False
        cached_facts = []

        if self.context_store and search_query:
            try:
                # Look for resolution triple in KG
                res_triples = self.context_store.get_triples(
                    user_id=user_id,
                    subject=search_query.lower()
                )
                for t in res_triples:
                    if t.get("predicate") == "resolved_to_canonical_id":
                        resolved_item_id = t.get("object")
                        kg_cache_hit = True
                        break

                # Also check system cache
                if not resolved_item_id:
                    sys_triples = self.context_store.get_triples(
                        user_id="kg_cache",
                        subject=search_query.lower()
                    )
                    for t in sys_triples:
                        if t.get("predicate") == "resolved_to_canonical_id":
                            resolved_item_id = t.get("object")
                            kg_cache_hit = True
                            break
            except Exception as e:
                logger.debug(f"KG cache lookup error: {e}")

        # Step 3: Execute Smart DB Query Engine
        query_spec = self.query_builder.build_query(extracted, schema_data)
        op = query_spec.get("operation")
        db_results: List[Dict[str, Any]] = []

        if resolved_item_id:
            # Direct indexed primary key lookup
            item = adapter.get_item_by_id(resolved_item_id)
            if item:
                db_results = [item]
                self.cache_hits += 1
            else:
                self.cache_misses += 1
        else:
            self.cache_misses += 1
            # Execute based on operation
            if op == "EXACT_ID":
                item = adapter.get_item_by_id(query_spec["item_id"])
                if item:
                    db_results = [item]
            elif op == "AGGREGATE":
                agg_res = adapter.get_aggregations(group_by=query_spec.get("group_by"))
                return {
                    "intent": intent,
                    "operation": "AGGREGATE",
                    "data": agg_res,
                    "spoken_text": f"Warehouse has {agg_res.get('total_records', 0):,} total inventory items.",
                    "kg_cache_hit": False,
                    "elapsed_ms": (time.perf_counter() - start_time) * 1000.0
                }
            elif op == "FILTER":
                db_results = adapter.filter_items(query_spec.get("filters", {}), limit=query_spec.get("limit", 5))
            else:
                # Text search
                db_results = adapter.search_by_text(query_spec.get("query", search_query), limit=query_spec.get("limit", 5))

        # Step 4: Results Normalization & Spoken Confirmation for Zero-Literacy Workers
        primary_item = db_results[0] if db_results else None
        spoken_response = ""
        structured_context_lines = []

        if primary_item:
            # Extract common display fields dynamically
            name_val = primary_item.get("canonical_name") or primary_item.get("name") or primary_item.get("product_name") or primary_item.get("item_id")
            qty_val = primary_item.get("quantity") or primary_item.get("stock") or primary_item.get("qty")
            unit_val = primary_item.get("unit_of_measure") or primary_item.get("uom") or primary_item.get("unit") or "units"
            price_val = primary_item.get("unit_price") or primary_item.get("price") or primary_item.get("mrp") or primary_item.get("rate")
            brand_val = primary_item.get("brand") or primary_item.get("company")
            cat_val = primary_item.get("category") or primary_item.get("section")
            loc_val = primary_item.get("bin_location") or primary_item.get("location") or primary_item.get("shelf")

            parts = []
            if name_val:
                parts.append(f"{name_val}")
            if qty_val is not None:
                parts.append(f"Stock: {qty_val} {unit_val}")
            if price_val is not None:
                parts.append(f"Price: ₹{price_val}")
            if loc_val:
                parts.append(f"Location: {loc_val}")

            structured_context_lines.append(f"[Verified Inventory Fact]: {', '.join(parts)}")

            # Formulate spoken confirm-back
            if intent == "PRICE" and price_val is not None:
                spoken_response = f"{name_val} ka bhav ₹{price_val} rupaye hai."
            elif intent == "QUANTITY" and qty_val is not None:
                spoken_response = f"{name_val}: {qty_val} {unit_val} bacha hai."
            else:
                spoken_response = f"{name_val}: Stock {qty_val if qty_val is not None else 'N/A'} {unit_val}, bhav ₹{price_val if price_val is not None else 'N/A'}."

            # Step 5: Learn & Write Back (Update KG Cache with resolved entity)
            item_id_val = primary_item.get("item_id") or primary_item.get("id") or str(name_val)
            if self.context_store and item_id_val and search_query:
                try:
                    # Write entity resolution link
                    self.context_store.upsert_triple(
                        user_id="kg_cache",
                        subject=search_query.lower(),
                        predicate="resolved_to_canonical_id",
                        object_val=str(item_id_val),
                        confidence=0.98
                    )
                    # Cache static name and category
                    if name_val and cat_val:
                        self.context_store.upsert_triple(
                            user_id="kg_cache",
                            subject=str(name_val),
                            predicate="belongs_to_category",
                            object_val=str(cat_val),
                            confidence=1.0
                        )
                    if brand_val and name_val:
                        self.context_store.upsert_triple(
                            user_id="kg_cache",
                            subject=str(name_val),
                            predicate="has_brand",
                            object_val=str(brand_val),
                            confidence=1.0
                        )
                except Exception as e:
                    logger.debug(f"Error writing back to KG cache: {e}")
        else:
            spoken_response = f"Yeh item inventory record me nahi mila."
            structured_context_lines.append(f"[Inventory Notice]: No matching records found for '{search_query}'.")

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return {
            "intent": intent,
            "search_query": search_query,
            "kg_cache_hit": kg_cache_hit,
            "matched_item": primary_item,
            "all_results": db_results,
            "context_string": "\n".join(structured_context_lines),
            "spoken_confirmation": spoken_response,
            "elapsed_ms": elapsed_ms
        }
