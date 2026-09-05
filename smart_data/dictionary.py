"""
smart_data/dictionary.py
========================
Dynamic, Domain-Agnostic Synonym and Vocabulary Store.
Zero hardcoding: Automatically extracts vocabulary, entity terms, and categorical
values directly from connected databases, files, and schemas.
Can adapt to ANY warehouse, inventory, automotive, pharma, or enterprise domain.
"""

import re
from typing import Dict, List, Optional, Set, Any


class DynamicDomainDictionary:
    """
    Dynamic vocabulary store that populates itself by introspecting
    the active database/file adapter schema and distinct categorical values.
    """

    def __init__(self):
        # Dynamically learned entity tokens -> canonical values
        self.term_to_canonical: Dict[str, str] = {}
        # Known categorical values per column (e.g. category names, brands, suppliers)
        self.column_domains: Dict[str, Set[str]] = {}
        # Column aliases learned from schema introspection
        self.column_aliases: Dict[str, List[str]] = {}
        # Generic intent patterns (domain-agnostic)
        self.intent_signals = {
            "QUANTITY": [
                "how many", "how much", "quantity", "stock", "count", "available", "units",
                "left", "balance", "kitna", "kitne", "kitni", "bacha", "bache", "bachi", "pada", "rakha"
            ],
            "PRICE": [
                "price", "cost", "rate", "mrp", "fee", "value", "worth",
                "bhav", "daam", "keemat", "kitne ka", "rupaye"
            ],
            "STATUS": [
                "status", "condition", "active", "expired", "state", "kaisa", "kya sthiti"
            ],
            "LOCATION": [
                "where", "location", "bin", "shelf", "aisle", "rack", "warehouse", "kahan", "jagah"
            ],
            "SUMMARY": [
                "summary", "total", "overall", "all", "report", "kul", "sab", "poora"
            ]
        }

    def learn_from_schema(self, schema_data: Dict[str, Any]) -> None:
        """
        Dynamically extracts vocabulary, table names, column names,
        and sample values from the introspected schema.
        Zero hardcoded tables or columns!
        """
        tables = schema_data.get("tables", [])
        for tbl in tables:
            t_name = tbl.get("table_name", "")
            self.term_to_canonical[t_name.lower()] = t_name

            for col in tbl.get("columns", []):
                c_name = col.get("name", "")
                c_lower = c_name.lower()
                self.term_to_canonical[c_lower] = c_name

                # Add sample values to vocabulary
                for s_val in col.get("sample_values", []):
                    if s_val is not None:
                        s_str = str(s_val).strip()
                        if s_str and len(s_str) > 1:
                            self.term_to_canonical[s_str.lower()] = s_str

    def learn_domain_values(self, column_name: str, values: List[str]) -> None:
        """Ingest distinct categorical values from the database."""
        col_key = column_name.lower()
        if col_key not in self.column_domains:
            self.column_domains[col_key] = set()

        for val in values:
            v_str = str(val).strip()
            if v_str:
                self.column_domains[col_key].add(v_str)
                self.term_to_canonical[v_str.lower()] = v_str

    def match_intent(self, text: str) -> str:
        """Detect generic query intent from user speech."""
        lower = text.lower()
        for intent, signals in self.intent_signals.items():
            for sig in signals:
                if re.search(r"\b" + re.escape(sig) + r"\b", lower):
                    return intent
        return "GENERAL_SEARCH"

    def find_matching_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Scans input text against the dynamically learned vocabulary.
        Returns matching canonical values and their source columns.
        """
        lower = text.lower()
        matches = []

        # Check multi-word and single-word tokens in learned vocabulary
        for term_lower, canonical in self.term_to_canonical.items():
            if len(term_lower) >= 3 and term_lower in lower:
                # Find which column domain this belongs to if known
                parent_col = None
                for col_name, domain_set in self.column_domains.items():
                    if canonical in domain_set:
                        parent_col = col_name
                        break

                matches.append({
                    "matched_text": term_lower,
                    "canonical": canonical,
                    "column": parent_col
                })

        # Deduplicate and sort by length descending (longest match first)
        matches.sort(key=lambda m: len(m["matched_text"]), reverse=True)
        unique_matches = []
        seen = set()
        for m in matches:
            if m["canonical"] not in seen:
                seen.add(m["canonical"])
                unique_matches.append(m)

        return unique_matches
