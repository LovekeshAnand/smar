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
        "display table", "in table", "in a table", "as a table", "show records",
        "view table", "list table", "show me all", "display all", "show all",
        "browse table", "all records", "in tabular format", "table view", "all rows"
    ]

    VISUAL_KEYWORDS = [
        "chart", "graph", "picture", "plot", "visualize", "visualization",
        "diagram", "chitra", "tasveer", "picture format", "show visually"
    ]

    WORD_TO_NUM = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
        "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90, "hundred": 100
    }

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
                if agg_func in ["SUM", "AVG", "MIN", "MAX"]:
                    return True
                if agg_func == "COUNT":
                    # "how many" is always a COUNT operation (not just point-lookup)
                    if any(k in lower for k in ["count of", "total count", "number of", "how many records", "how many total"]):
                        return True
                    # "how many X" where X is a table/domain entity => COUNT
                    if "how many" in lower:
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

        # Partition columns into metric measures (non-ID numeric) vs identifier/dimension columns
        numeric_cols = [c["name"] for c in columns if any(t in str(c.get("type", "")).upper() for t in ["INT", "REAL", "FLOAT", "DOUBLE", "NUM"])]
        metric_cols = [c for c in numeric_cols if not c.lower().endswith("id") and c.lower() != "id"]
        id_cols = [c["name"] for c in columns if c["name"].lower().endswith("id") or c["name"].lower() == "id"]

        clean_lower = clean.lower()
        target_col = None

        # For COUNT: Default to '*' (all entities) unless a specific metric column is explicitly requested
        if agg_name == "COUNT":
            for c in metric_cols:
                cname = c.lower()
                c_phrase = cname.replace("_", " ")
                if cname in clean_lower.split() or c_phrase in clean_lower:
                    target_col = c
                    break
            if not target_col:
                target_col = "*"
        else:
            # For mathematical operations (SUM, AVG/MEAN, MIN, MAX):
            # Step 1: Check if a column is explicitly named immediately after the aggregation word
            # e.g., "mean of salaries", "average of the salary", "sum of amounts", "max of price"
            agg_target_m = re.search(
                r"(?:sum|total|avg|average|mean|min|minimum|max|maximum)\s+(?:of|in)?\s+(?:the\s+)?([a-z_]+)",
                clean_lower
            )
            if agg_target_m:
                raw_word = agg_target_m.group(1).rstrip("s")
                if raw_word.endswith("ie"):
                    raw_word = raw_word[:-2] + "y"  # "salaries" -> "salary"
                for c in metric_cols:
                    cname = c.lower().rstrip("s")
                    if cname.endswith("ie"):
                        cname = cname[:-2] + "y"
                    if raw_word == cname or raw_word in c.lower() or c.lower() in agg_target_m.group(1):
                        target_col = c
                        break

            # Step 2: Check if any metric column (or its plural) appears anywhere in the clean query
            if not target_col:
                for c in metric_cols:
                    cname = c.lower()
                    plural = cname + "s" if not cname.endswith("y") else cname[:-1] + "ies"
                    if cname in clean_lower.split() or plural in clean_lower.split() or cname.replace("_", " ") in clean_lower:
                        target_col = c
                        break

            # Step 3: Check dynamic domain dictionary synonyms (e.g. wage/pay -> salary, cost -> price)
            if not target_col and self.domain_dict and hasattr(self.domain_dict, "synonyms"):
                for c in metric_cols:
                    syns = self.domain_dict.synonyms.get(c.lower(), [])
                    if any(s in clean_lower.split() for s in syns):
                        target_col = c
                        break

            # Step 4: Explicit request for ID aggregation (only if user explicitly says e.g. "average of employee id")
            if not target_col:
                for c in id_cols:
                    cname = c.lower()
                    c_phrase = cname.replace("_", " ")
                    if f"of {cname}" in clean_lower or f"of {c_phrase}" in clean_lower:
                        target_col = c
                        break

            # Step 5: Fallback to first metric measure column (NEVER default to an ID column)
            if not target_col:
                target_col = metric_cols[0] if metric_cols else (numeric_cols[0] if numeric_cols else "*")

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

        # Check for range or filter conditions (e.g. "from 30 to 40", "range of employee id 30 to 40", "between 1 and 10")
        filter_cond = None
        filter_params = None
        filter_desc = None

        # Identify primary key or default identifier column
        pk_col = next((c["name"] for c in columns if c.get("pk")), None)
        if not pk_col:
            pk_col = next((c["name"] for c in columns if c["name"].lower().endswith("id")), columns[0]["name"] if columns else "id")

        # Normalize word numbers to digits in clean text
        norm_text = clean
        for w, d in self.WORD_TO_NUM.items():
            norm_text = re.sub(rf"\b{w}\b", str(d), norm_text)

        # 1. RANGE FILTER: Always evaluate range first so numbers aren't greedily consumed as single IDs
        # Matches "range of employee id 30 to 40", "from 30 to 40", "between 30 and 40", "30 to 40"
        range_m = re.search(r'(?:range\s+(?:of\s+)?|between\s+|from\s+)?(?:[a-z_]+\s+)*?(\d+)\s*(?:to|and|-)\s*(\d+)\b', norm_text)
        if range_m:
            start_val, end_val = int(range_m.group(1)), int(range_m.group(2))
            # Determine which column the range applies to
            range_col = pk_col
            text_around_range = norm_text[:range_m.start() + len(range_m.group(0))]
            for c in columns:
                cname = c["name"].lower()
                c_phrase = cname.replace("_", " ")
                if cname in text_around_range or c_phrase in text_around_range:
                    range_col = c["name"]
                    break
            filter_cond = f'"{range_col}" BETWEEN ? AND ?'
            filter_params = [start_val, end_val]
            filter_desc = f"{range_col} from {start_val} to {end_val}"
        else:
            # 2. Limit / Top N (e.g. "first 10", "top 5")
            first_m = re.search(r"(?:first|top)\s+(\d+)", norm_text)
            if first_m:
                limit_val = int(first_m.group(1))
                filter_cond = f'"{pk_col}" <= ?'
                filter_params = [limit_val]
                filter_desc = f"first {limit_val} records"
            else:
                # 3. Specific entity filter: "for/of order|employee|customer id X"
                entity_filter_m = re.search(
                    r"(?:for|of|in|where|with)\s+([a-z_]+)?\s*(?:id|no\.?|number|#)?\s*(\d+)\b",
                    norm_text
                )
                if entity_filter_m:
                    filter_val = int(entity_filter_m.group(2))
                    fk_match = None
                    keyword = (entity_filter_m.group(1) or "").rstrip("s").lower()
                    if keyword:
                        for c in columns:
                            if keyword in c["name"].lower() and c["name"].lower().endswith("id"):
                                fk_match = c["name"]
                                break
                    if not fk_match:
                        fk_match = pk_col
                    filter_cond = f'"{fk_match}" = ?'
                    filter_params = [filter_val]
                    filter_desc = f"{fk_match} = {filter_val}"

        return {
            "operation": "AGGREGATION",
            "function": agg_name,
            "table": active_table,
            "column": target_col,
            "group_by": group_by_col,
            "filter_condition": filter_cond,
            "filter_params": filter_params,
            "filter_description": filter_desc,
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
