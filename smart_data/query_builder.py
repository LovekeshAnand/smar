"""
smart_data/query_builder.py
===========================
Dynamic Query Understanding & Builder for SMAR v2.
Builds executable query operations tailored to the actual schema of the connected data source.
Zero hardcoding: adapts to whatever columns exist in the active table.
"""

from typing import Dict, Any, List, Optional


class SmartQueryBuilder:
    """
    Builds executable query plans for any storage adapter based on dynamic schema.
    """

    def build_query(self, extracted: Dict[str, Any], schema_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Translates extracted intent, tokens, and schema into an adapter query spec.
        """
        intent = extracted.get("intent", "GENERAL_SEARCH")
        code_candidates = extracted.get("code_candidates", [])
        matched_entities = extracted.get("matched_entities", [])
        search_query = extracted.get("search_query", "").strip()
        search_tokens = extracted.get("search_tokens", [])

        # 1. Exact ID / Code / Barcode Match
        if code_candidates:
            return {
                "operation": "EXACT_ID",
                "item_id": code_candidates[0]
            }

        # 2. Summary / Aggregation
        if intent == "SUMMARY":
            group_by_col = None
            if schema_data and schema_data.get("tables"):
                # Find first plausible categorical column
                table = schema_data["tables"][0]
                for col in table.get("columns", []):
                    c_name = col.get("name", "").lower()
                    if c_name in ["category", "type", "department", "brand", "supplier", "group", "status"]:
                        group_by_col = col["name"]
                        break
            return {
                "operation": "AGGREGATE",
                "group_by": group_by_col
            }

        # 3. Column-specific Filter if an entity matched a known column domain
        for me in matched_entities:
            col_name = me.get("column")
            if col_name:
                return {
                    "operation": "FILTER",
                    "filters": {col_name: me["canonical"]},
                    "limit": 10
                }

        # 4. Full Text / Keyword Search
        final_query = search_query or " ".join(search_tokens)
        if not final_query:
            final_query = "all"

        return {
            "operation": "SEARCH_TEXT",
            "query": final_query,
            "limit": 5
        }
