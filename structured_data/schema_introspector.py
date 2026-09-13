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

    def reload_vocab_from_kg(self, domain_dict, schema_user_id: str = "system_schema") -> bool:
        """
        Fast-path vocabulary reload from stored KG schema triples.
        Avoids rescanning the DB when the schema fingerprint has not changed.
        Reconstructs domain_dict.term_to_canonical, column_to_table, and table_names
        entirely from the KG's persisted system_schema triples.

        Returns True if vocab was successfully reconstructed, False if KG has no schema triples
        (caller must then fall back to full DB introspection).
        """
        if not self.context_store:
            return False

        try:
            # Pull all system_schema triples in a single query
            all_triples = self.context_store.get_all_triples(
                user_id=schema_user_id, limit=10000
            )

            if not all_triples:
                return False

            tables_found = set()
            columns_by_table = {}      # table -> [col, ...]
            numeric_cols_by_table = {} # table -> [col, ...]
            fk_map = {}                # table -> [referenced_table, ...]
            sample_values = {}         # (table, col) -> [val, ...]

            for t in all_triples:
                pred = t.get("predicate", "")
                subj = t.get("subject", "")
                obj  = t.get("object", "")

                if pred == "has_table":
                    tables_found.add(obj)

                elif pred == "has_column":
                    table = subj
                    if table not in columns_by_table:
                        columns_by_table[table] = []
                    columns_by_table[table].append(obj)

                elif pred == "has_data_type":
                    # subject is "table.column"
                    if "." in subj:
                        tbl, col = subj.split(".", 1)
                        if obj.upper() in ("REAL", "INTEGER", "NUMERIC", "FLOAT", "INT", "DOUBLE", "DECIMAL"):
                            if tbl not in numeric_cols_by_table:
                                numeric_cols_by_table[tbl] = []
                            numeric_cols_by_table[tbl].append(col)

                elif pred == "references_table":
                    if subj not in fk_map:
                        fk_map[subj] = []
                    fk_map[subj].append(obj)

                elif pred == "foreign_key_to":
                    # subject = "table.from_col", object = "ref_table.ref_col"
                    if "." in subj and "." in obj:
                        from_table = subj.split(".")[0]
                        to_table = obj.split(".")[0]
                        if from_table not in fk_map:
                            fk_map[from_table] = []
                        if to_table not in fk_map[from_table]:
                            fk_map[from_table].append(to_table)

                elif pred == "has_sample_value":
                    if "." in subj:
                        tbl, col = subj.split(".", 1)
                        key = (tbl, col)
                        if key not in sample_values:
                            sample_values[key] = []
                        sample_values[key].append(obj)

            if not tables_found:
                return False

            # Rebuild domain_dict from discovered schema
            # 1. table names → canonical mapping
            for tbl in tables_found:
                clean = tbl.lower().strip()
                domain_dict.term_to_canonical[clean] = tbl
                # singular form
                singular = clean.rstrip("s")
                if singular != clean:
                    domain_dict.term_to_canonical[singular] = tbl

            # 2. column name → table mapping
            for tbl, cols in columns_by_table.items():
                for col in cols:
                    clean_col = col.lower().strip()
                    domain_dict.term_to_canonical[clean_col] = col
                    domain_dict.column_to_table[clean_col] = tbl

            # 3. numeric columns registry
            if hasattr(domain_dict, "numeric_columns_by_table"):
                domain_dict.numeric_columns_by_table = numeric_cols_by_table

            # 4. FK map registry
            if hasattr(domain_dict, "fk_map"):
                domain_dict.fk_map = fk_map

            # 5. Sample values → vocabulary enrichment
            for (tbl, col), vals in sample_values.items():
                for v in vals:
                    v_clean = str(v).lower().strip()
                    if v_clean and len(v_clean) < 50:
                        domain_dict.term_to_canonical[v_clean] = v

            # 6. Table names list
            if hasattr(domain_dict, "table_names"):
                domain_dict.table_names = list(tables_found)

            logger.info(
                f"Vocab reloaded from KG: {len(tables_found)} tables, "
                f"{sum(len(c) for c in columns_by_table.values())} columns, "
                f"{sum(len(v) for v in sample_values.values())} sample values."
            )
            return True

        except Exception as e:
            logger.warning(f"reload_vocab_from_kg failed, will fall back to DB scan: {e}")
            return False


