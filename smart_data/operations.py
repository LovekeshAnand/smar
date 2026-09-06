"""
smart_data/operations.py
========================
Universal Operations Layer & Intent Analyzer for SMAR v2.
Enables mathematical aggregations (SUM, AVG, COUNT, MIN, MAX) and full CRUD mutations
(INSERT, UPDATE, DELETE, TABULAR_QUERY) across any connected database or dataset.
Zero hardcoding: dynamically adapts to introspected tables, primary keys, and column types.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("smar.smart_data.operations")


class OperationsAnalyzer:
    """
    Parses natural language requests into structured executable Operation Plans,
    and executes them against the warehouse manager.
    """

    AGG_KEYWORDS = {
        "SUM": [
            "sum of", "total of", "sum", "total", "kul jod", "total amount",
            "add up", "combined", "all salaries", "total salary", "overall sum"
        ],
        "AVG": [
            "average of", "average", "mean of", "mean", "ausat", "typical"
        ],
        "MIN": [
            "minimum of", "minimum", "min", "lowest", "least", "cheapest",
            "smallest", "sabse kam", "kam se kam"
        ],
        "MAX": [
            "maximum of", "maximum", "max", "highest", "greatest", "most expensive",
            "top", "biggest", "sabse jyada", "sabse bada"
        ],
        "COUNT": [
            "count of", "number of", "how many", "total count", "kitne", "kitni",
            "kitna", "how many entries", "how many records"
        ]
    }

    MUTATION_KEYWORDS = {
        "INSERT": ["add new", "add entry", "insert into", "insert", "create record", "add row", "naya jodo", "naya daalo"],
        "UPDATE": ["update", "change", "modify", "set", "badlo", "theek karo", "revise"],
        "DELETE": ["delete", "remove", "drop entry", "hatao", "mitao", "cancel record"]
    }

    TABULAR_KEYWORDS = [
        "table format", "show in table", "show table", "list all", "tabular",
        "display table", "in table", "show records", "view table", "list table"
    ]

    VISUAL_KEYWORDS = [
        "chart", "graph", "picture", "plot", "visualize", "visualization",
        "diagram", "chitra", "tasveer", "picture format", "show visually"
    ]

    def __init__(self, warehouse_manager=None, domain_dict=None):
        self.warehouse_manager = warehouse_manager
        self.domain_dict = domain_dict

    def is_operation_query(self, text: str) -> bool:
        """Determines whether a user query requires an Operation (aggregation, CRUD, table, or chart)."""
        lower = text.lower()

        # Check for mutation signals
        for m_type, keywords in self.MUTATION_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                return True

        # Check for aggregation signals
        for agg_func, keywords in self.AGG_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                # Ensure it's not a generic point question like "what is the salary of employee 98"
                if agg_func in ["SUM", "AVG", "MIN", "MAX"]:
                    return True
                if agg_func == "COUNT" and any(k in lower for k in ["count of", "total count", "number of", "how many total", "how many records"]):
                    return True

        # Check for tabular view
        if any(kw in lower for kw in self.TABULAR_KEYWORDS):
            return True

        # Check for visual request
        if any(kw in lower for kw in self.VISUAL_KEYWORDS):
            return True

        return False

    def _detect_target_table(
        self,
        clean: str,
        schema_tables: List[Dict[str, Any]],
        has_aggregation: bool = False
    ) -> Optional[str]:
        """
        Dynamically detects the best target table from schema_tables based on
        table names, column mentions, and aggregation requirements.
        """
        if not schema_tables:
            return None
        if len(schema_tables) == 1:
            return schema_tables[0]["table_name"]

        words = clean.split()
        table_scores: Dict[str, float] = {t["table_name"]: 0.0 for t in schema_tables}

        for tbl in schema_tables:
            tname = tbl["table_name"].lower()
            t_orig = tbl["table_name"]
            singular = tname[:-3] + "y" if tname.endswith("ies") else (tname[:-1] if tname.endswith("s") else tname)

            # Table name matching
            if tname in words or singular in words or tname in clean:
                # Check if preceded by "per" or "by" (likely a group-by dimension, not the subject)
                is_group_by_dimension = any(f"per {w}" in clean or f"by {w}" in clean for w in [tname, singular])
                if is_group_by_dimension:
                    table_scores[t_orig] += 1.5
                else:
                    table_scores[t_orig] += 4.0

            # Column matching
            cols = tbl.get("columns", [])
            for c in cols:
                cname = c["name"].lower()
                c_phrase = cname.replace("_", " ")
                ctype = str(c.get("type", "")).upper()
                is_numeric = any(nt in ctype for nt in ["INT", "REAL", "FLOAT", "DOUBLE", "NUM"])

                # Exact column or phrase match
                if cname in words or c_phrase in clean or (cname.endswith("s") and cname[:-1] in words) or (cname == "salary" and "salaries" in words):
                    score_boost = 5.0
                    if has_aggregation and is_numeric and not cname.endswith("_id"):
                        score_boost += 6.0  # Dominant priority for the table owning the numeric aggregation column!
                    table_scores[t_orig] += score_boost

        # If domain dictionary is available
        if self.domain_dict:
            for word in words:
                if word in self.domain_dict.column_to_table:
                    tbl_match = self.domain_dict.column_to_table[word]
                    if tbl_match in table_scores:
                        table_scores[tbl_match] += 4.0
                if word in self.domain_dict.term_to_canonical:
                    canon = self.domain_dict.term_to_canonical[word]
                    for t_orig in table_scores:
                        if t_orig.lower() == canon.lower():
                            table_scores[t_orig] += 3.0

        best_table, best_score = max(table_scores.items(), key=lambda x: x[1])
        if best_score > 0:
            return best_table
        return schema_tables[0]["table_name"]

    def parse_plan(self, text: str, schema_tables: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Translates user utterance into an executable Operation Plan.
        Adapts dynamically to the provided database schema tables.
        """
        lower = text.lower()
        clean = re.sub(r"[^\w\s\-\.\,\:]", " ", lower).strip()

        # Check if visual representation was explicitly requested
        wants_visual = any(kw in lower for kw in self.VISUAL_KEYWORDS)

        # Check for aggregation signals upfront
        detected_agg = None
        for agg_name, keywords in self.AGG_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    detected_agg = agg_name
                    break
            if detected_agg:
                break

        # 1. Detect target table dynamically
        target_table = self._detect_target_table(clean, schema_tables, has_aggregation=bool(detected_agg))

        # -------------------------------------------------------------
        # 2. Check for UPDATE Mutation
        # -------------------------------------------------------------
        if any(kw in lower for kw in self.MUTATION_KEYWORDS["UPDATE"]):
            return self._parse_update_plan(clean, text, target_table, schema_tables)

        # -------------------------------------------------------------
        # 3. Check for INSERT Mutation
        # -------------------------------------------------------------
        if any(kw in lower for kw in self.MUTATION_KEYWORDS["INSERT"]):
            return self._parse_insert_plan(clean, text, target_table, schema_tables)

        # -------------------------------------------------------------
        # 4. Check for DELETE Mutation
        # -------------------------------------------------------------
        if any(kw in lower for kw in self.MUTATION_KEYWORDS["DELETE"]):
            return self._parse_delete_plan(clean, text, target_table, schema_tables)

        # -------------------------------------------------------------
        # 5. Check for AGGREGATIONS (SUM, AVG, COUNT, MIN, MAX)
        # -------------------------------------------------------------
        detected_agg = None
        for agg_name, keywords in self.AGG_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    detected_agg = agg_name
                    break
            if detected_agg:
                break

        if detected_agg:
            return self._parse_aggregation_plan(clean, detected_agg, target_table, schema_tables, wants_visual)

        # -------------------------------------------------------------
        # 6. Check for TABULAR Query / List All
        # -------------------------------------------------------------
        if any(kw in lower for kw in self.TABULAR_KEYWORDS) or "list" in clean.split():
            return {
                "operation": "TABULAR",
                "table": target_table or (schema_tables[0]["table_name"] if schema_tables else "data"),
                "limit": 10,
                "wants_visual": wants_visual
            }

        if wants_visual and target_table:
            # User wants a chart of this table's data
            return {
                "operation": "TABULAR",
                "table": target_table,
                "limit": 10,
                "wants_visual": True
            }

        return None

    def _parse_aggregation_plan(
        self,
        clean: str,
        agg_name: str,
        target_table: Optional[str],
        schema_tables: List[Dict[str, Any]],
        wants_visual: bool
    ) -> Dict[str, Any]:
        """Parses aggregation column and optional group_by."""
        table_obj = next((t for t in schema_tables if t["table_name"] == target_table), None) if target_table else (schema_tables[0] if schema_tables else None)
        active_table = table_obj["table_name"] if table_obj else "data"
        columns = table_obj.get("columns", []) if table_obj else []

        # Find numeric column candidate
        target_col = "*"
        numeric_cols = [c["name"] for c in columns if any(t in str(c.get("type", "")).upper() for t in ["INT", "REAL", "FLOAT", "DOUBLE", "NUM"])]

        # Try to find specific column mentioned in text
        for c in columns:
            cname = c["name"].lower()
            if cname in clean or cname.replace("_", " ") in clean:
                target_col = c["name"]
                break

        if target_col == "*" and numeric_cols:
            # Check domain keywords for common numeric metrics
            if any(w in clean for w in ["salary", "pay", "compensation", "wage"]) and "salary" in numeric_cols:
                target_col = "salary"
            elif any(w in clean for w in ["price", "cost", "mrp", "rate", "amount"]) and any(c in numeric_cols for c in ["amount", "price", "unit_price", "cost"]):
                target_col = next(c for c in numeric_cols if c in ["amount", "price", "unit_price", "cost"])
            elif any(w in clean for w in ["quantity", "stock", "qty"]) and any(c in numeric_cols for c in ["quantity", "qty", "stock"]):
                target_col = next(c for c in numeric_cols if c in ["quantity", "qty", "stock"])
            elif any(w in clean for w in ["refund"]) and "refund" in numeric_cols:
                target_col = "refund"
            elif any(w in clean for w in ["discount"]) and "discount" in numeric_cols:
                target_col = "discount"
            else:
                # Default to first non-ID numeric column if doing SUM/AVG
                non_id_numerics = [c for c in numeric_cols if not c.lower().endswith("id")]
                target_col = non_id_numerics[0] if non_id_numerics else numeric_cols[0]

        # Check for GROUP BY (e.g. "per store", "by city", "each category", "store wise")
        group_by_col = None
        for c in columns:
            cname = c["name"].lower()
            c_phrase = cname.replace("_", " ")
            if any(f"per {cname}" in clean or f"by {cname}" in clean or f"each {cname}" in clean or f"per {c_phrase}" in clean or f"by {c_phrase}" in clean for p in [cname, c_phrase]):
                group_by_col = c["name"]
                break
        
        # Shorthand phrases (e.g. "per store" -> "store_id")
        if not group_by_col:
            if "store" in clean and any(c["name"] == "store_id" for c in columns):
                group_by_col = "store_id"
            elif "category" in clean and any(c["name"] == "category_id" for c in columns):
                group_by_col = "category_id"
            elif "customer" in clean and any(c["name"] == "customer_id" for c in columns):
                group_by_col = "customer_id"
            elif "city" in clean and any(c["name"] == "city" for c in columns):
                group_by_col = "city"
            elif "status" in clean and any(c["name"] == "status" for c in columns):
                group_by_col = "status"

        return {
            "operation": "AGGREGATION",
            "function": agg_name,
            "table": active_table,
            "column": target_col,
            "group_by": group_by_col,
            "wants_visual": wants_visual or (group_by_col is not None)
        }

    def _parse_update_plan(
        self,
        clean: str,
        raw_text: str,
        target_table: Optional[str],
        schema_tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parses update filter criteria and mutation fields."""
        table_obj = next((t for t in schema_tables if t["table_name"] == target_table), None) if target_table else (schema_tables[0] if schema_tables else None)
        active_table = table_obj["table_name"] if table_obj else "data"
        columns = table_obj.get("columns", []) if table_obj else []

        filter_data: Dict[str, Any] = {}
        update_data: Dict[str, Any] = {}

        # 1. Extract Filter Target (usually primary key or code like "employee 98" or "id 210")
        pk_col = next((c["name"] for c in columns if c.get("pk")), None)
        if not pk_col:
            pk_col = next((c["name"] for c in columns if c["name"].lower().endswith("id")), columns[0]["name"] if columns else "id")

        # Search for ID in text (e.g. "employee 98", "order id 210", "id 42")
        id_match = re.search(r"(?:id|number|#|employee|order|customer|item|product)\s*(?:is|=|:)?\s*(\d+)", clean)
        if id_match:
            filter_data[pk_col] = int(id_match.group(1))
        else:
            # Any lone digits
            lone_digits = [int(w) for w in clean.split() if w.isdigit()]
            if lone_digits:
                filter_data[pk_col] = lone_digits[0]

        # 2. Extract Update Field & Value (e.g. "salary to 35000", "salary = 35000", "status to delivered", "salary of employee 98 to 35000")
        for c in columns:
            cname = c["name"].lower()
            c_display = cname.replace("_", " ")

            patterns = [
                rf"(?:{cname}|{c_display})\s*(?:of\s+[^=,]+?)?\s*(?:to|=|as|becomes|set to)\s*([a-zA-Z0-9_\-\.]+)",
                rf"(?:set|change)\s*(?:{cname}|{c_display})\s*(?:to|=)?\s*([a-zA-Z0-9_\-\.]+)",
                rf"(?:to|=|becomes)\s*([a-zA-Z0-9_\-\.]+)\s*(?:for|of|in)?\s*(?:{cname}|{c_display})"
            ]
            for pattern in patterns:
                m = re.search(pattern, clean)
                if m:
                    raw_val = m.group(1).strip()
                    # Skip common stopwords
                    if raw_val in ("of", "the", "a", "an", "for", "in", "to", "at", "by"):
                        continue
                    # Skip if matched val was the filter ID itself
                    if filter_data.get(pk_col) and raw_val == str(filter_data[pk_col]):
                        continue

                    col_type = str(c.get("type", "")).upper()
                    if "INT" in col_type and raw_val.isdigit():
                        update_data[c["name"]] = int(raw_val)
                    elif ("REAL" in col_type or "FLOAT" in col_type) and re.match(r"^-?\d+(\.\d+)?$", raw_val):
                        update_data[c["name"]] = float(raw_val)
                    else:
                        update_data[c["name"]] = raw_val
                    break

        # Fallback numeric update: if salary/amount is updated
        if not update_data and len(re.findall(r"\b\d+\b", clean)) >= 2:
            nums = [int(n) for n in re.findall(r"\b\d+\b", clean)]
            # First is likely ID, second is likely new numeric value
            if len(nums) >= 2:
                if pk_col not in filter_data:
                    filter_data[pk_col] = nums[0]
                # Find first numeric column that isn't the PK
                num_cols = [c["name"] for c in columns if any(t in str(c.get("type", "")).upper() for t in ["INT", "REAL", "FLOAT"]) and c["name"] != pk_col]
                if num_cols:
                    update_data[num_cols[0]] = nums[1]

        return {
            "operation": "UPDATE",
            "table": active_table,
            "filter": filter_data,
            "updates": update_data,
            "raw_text": raw_text
        }

    def _parse_insert_plan(
        self,
        clean: str,
        raw_text: str,
        target_table: Optional[str],
        schema_tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parses fields to insert for a new record."""
        table_obj = next((t for t in schema_tables if t["table_name"] == target_table), None) if target_table else (schema_tables[0] if schema_tables else None)
        active_table = table_obj["table_name"] if table_obj else "data"
        columns = table_obj.get("columns", []) if table_obj else []

        data: Dict[str, Any] = {}

        # Look for explicit column mentions: "salary 50000", "store_id 2"
        for c in columns:
            cname = c["name"].lower()
            c_display = cname.replace("_", " ")
            pattern = rf"(?:{cname}|{c_display})\s*(?:is|=|:|to)?\s*([a-zA-Z0-9_\-\.]+)"
            m = re.search(pattern, clean)
            if m:
                val = m.group(1).strip()
                col_type = str(c.get("type", "")).upper()
                if "INT" in col_type and val.isdigit():
                    data[c["name"]] = int(val)
                elif ("REAL" in col_type or "FLOAT" in col_type) and re.match(r"^-?\d+(\.\d+)?$", val):
                    data[c["name"]] = float(val)
                else:
                    data[c["name"]] = val

        return {
            "operation": "INSERT",
            "table": active_table,
            "data": data,
            "raw_text": raw_text
        }

    def _parse_delete_plan(
        self,
        clean: str,
        raw_text: str,
        target_table: Optional[str],
        schema_tables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Parses target entity to delete."""
        table_obj = next((t for t in schema_tables if t["table_name"] == target_table), None) if target_table else (schema_tables[0] if schema_tables else None)
        active_table = table_obj["table_name"] if table_obj else "data"
        columns = table_obj.get("columns", []) if table_obj else []

        pk_col = next((c["name"] for c in columns if c.get("pk")), None)
        if not pk_col:
            pk_col = next((c["name"] for c in columns if c["name"].lower().endswith("id")), columns[0]["name"] if columns else "id")

        filter_data: Dict[str, Any] = {}
        digits = [int(w) for w in clean.split() if w.isdigit()]
        if digits:
            filter_data[pk_col] = digits[0]

        return {
            "operation": "DELETE",
            "table": active_table,
            "filter": filter_data,
            "raw_text": raw_text
        }
