"""
structured_data/schema_introspector.py
======================================
Domain-Agnostic Schema Introspector for SMAR v2.
Introspects any connected database or tabular file adapter (SQL, CSV, Excel)
and synchronizes the complete structural schema into the Knowledge Graph.
Zero hardcoding: works for warehouses, medical supplies, automotive parts, or retail.
"""

import logging
from typing import List, Dict, Any, Optional
from .adapters.base import BaseStorageAdapter

logger = logging.getLogger("smar.structured_data.schema_introspector")

# Generalized keywords that indicate frequently changing (volatile) state
VOLATILE_INDICATORS = {
    "qty", "quantity", "stock", "count", "balance", "level", "avail",
    "price", "cost", "mrp", "rate", "fee", "amount", "value",
    "status", "state", "updated", "modified", "timestamp"
}


class SchemaIntrospector:
    """
    Introspects any storage adapter and creates structural schema triples in the Knowledge Graph.
    """

    def __init__(self, context_store=None):
        self.context_store = context_store

    def is_column_volatile(self, col_name: str, col_type: str = "TEXT") -> bool:
        """
        Dynamically infers if a column is volatile based on name tokens.
        """
        clean_name = col_name.lower().replace("-", "_").replace(" ", "_")
        tokens = set(clean_name.split("_"))
        if tokens.intersection(VOLATILE_INDICATORS):
            return True
        return False

    def introspect_and_sync(
        self,
        adapter: BaseStorageAdapter,
        schema_user_id: str = "system_schema"
    ) -> List[Dict[str, str]]:
        """
        Introspects adapter schema and writes dynamic schema triples into Knowledge Graph.
        """
        schema_data = adapter.introspect_schema()
        source_name = schema_data.get("source_name", "DataSource")
        source_type = schema_data.get("source_type", "database")
        tables = schema_data.get("tables", [])

        triples: List[Dict[str, str]] = []

        # 1. Source level triples
        triples.append({
            "subject": source_name,
            "predicate": "is_data_source_type",
            "object": source_type
        })

        for tbl in tables:
            t_name = tbl["table_name"]
            triples.append({
                "subject": source_name,
                "predicate": "has_table",
                "object": t_name
            })
            triples.append({
                "subject": t_name,
                "predicate": "has_row_count",
                "object": str(tbl.get("row_count", 0))
            })

            for col in tbl.get("columns", []):
                col_name = col["name"]
                col_type = col.get("type", "TEXT")
                is_pk = str(col.get("is_primary_key", False)).lower()
                is_volatile = str(col.get("is_volatile", self.is_column_volatile(col_name, col_type))).lower()

                triples.append({
                    "subject": t_name,
                    "predicate": "has_column",
                    "object": col_name
                })
                triples.append({
                    "subject": f"{t_name}.{col_name}",
                    "predicate": "has_data_type",
                    "object": col_type
                })
                triples.append({
                    "subject": f"{t_name}.{col_name}",
                    "predicate": "is_volatile_field",
                    "object": is_volatile
                })
                if is_pk == "true":
                    triples.append({
                        "subject": f"{t_name}.{col_name}",
                        "predicate": "is_primary_key",
                        "object": "true"
                    })

                # Sample values for semantic grounding
                for sample in col.get("sample_values", []):
                    if sample is not None:
                        s_str = str(sample).strip()
                        if s_str and len(s_str) < 60:
                            triples.append({
                                "subject": f"{t_name}.{col_name}",
                                "predicate": "has_sample_value",
                                "object": s_str
                            })

        # Persist into Knowledge Graph if store is attached
        if self.context_store:
            for t in triples:
                try:
                    self.context_store.upsert_triple(
                        user_id=schema_user_id,
                        subject=t["subject"],
                        predicate=t["predicate"],
                        object_val=t["object"],
                        confidence=1.0
                    )
                except Exception as e:
                    logger.debug(f"Error persisting schema triple: {e}")

        logger.info(f"Dynamically introspected and synced {len(triples)} schema triples for '{source_name}'.")
        return triples

    def introspect_multi_table(
        self,
        warehouse_manager,
        schema_user_id: str = "system_schema"
    ) -> List[Dict[str, str]]:
        """
        Introspects all tables, columns, and foreign keys in a MultiTableWarehouseManager
        and syncs structural relational triples into the Knowledge Graph.
        """
        tables = warehouse_manager.list_tables()
        triples: List[Dict[str, str]] = []

        triples.append({
            "subject": "WarehouseDatabase",
            "predicate": "is_data_source_type",
            "object": "multi_table_warehouse"
        })

        for t_info in tables:
            t_name = t_info["table_name"]
            row_count = t_info["row_count"]

            triples.append({
                "subject": "WarehouseDatabase",
                "predicate": "has_table",
                "object": t_name
            })
            triples.append({
                "subject": t_name,
                "predicate": "has_row_count",
                "object": str(row_count)
            })

            detailed = warehouse_manager.get_table_schema(t_name)

            for col_name, col_type in detailed.get("columns", {}).items():
                is_volatile = str(self.is_column_volatile(col_name, col_type)).lower()
                triples.append({
                    "subject": t_name,
                    "predicate": "has_column",
                    "object": col_name
                })
                triples.append({
                    "subject": f"{t_name}.{col_name}",
                    "predicate": "has_data_type",
                    "object": col_type
                })
                triples.append({
                    "subject": f"{t_name}.{col_name}",
                    "predicate": "is_volatile_field",
                    "object": is_volatile
                })

            # Foreign key relations
            for fk in detailed.get("foreign_keys", []):
                triples.append({
                    "subject": t_name,
                    "predicate": "references_table",
                    "object": fk["to_table"]
                })
                triples.append({
                    "subject": f"{t_name}.{fk['from_col']}",
                    "predicate": "foreign_key_to",
                    "object": f"{fk['to_table']}.{fk['to_col']}"
                })

        if self.context_store:
            for t in triples:
                try:
                    self.context_store.upsert_triple(
                        user_id=schema_user_id,
                        subject=t["subject"],
                        predicate=t["predicate"],
                        object_val=t["object"],
                        confidence=1.0
                    )
                except Exception as e:
                    logger.debug(f"Error persisting multi-table schema triple: {e}")

        logger.info(f"Introspected multi-table warehouse: {len(tables)} tables, {len(triples)} triples.")
        return triples

    def get_compact_schema_prompt(self, adapter: BaseStorageAdapter) -> str:
        """
        Generates a concise schema map for the LLM reasoning prompt.
        """
        schema = adapter.introspect_schema()
        lines = [f"[Connected Database: {schema.get('source_name')} ({schema.get('source_type')})]"]
        for tbl in schema.get("tables", []):
            t_name = tbl["table_name"]
            cols = []
            for c in tbl.get("columns", []):
                v_tag = "(volatile)" if c.get("is_volatile") else "(static)"
                cols.append(f"{c['name']} {c['type']} {v_tag}")
            lines.append(f"Table `{t_name}` ({tbl.get('row_count', 0):,} rows):")
            lines.append(f"  Columns: {', '.join(cols)}")
        return "\n".join(lines)

