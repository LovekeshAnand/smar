"""
smart_data/intent_entity.py
===========================
Dynamic Intent Classifier & Entity Extractor.
Domain-agnostic: Adapts to any warehouse, catalog, or database schema.
Extracts query intents (QUANTITY, PRICE, STATUS, LOCATION, SUMMARY, SEARCH)
and resolves target entities against the dynamic domain vocabulary.
"""

import re
from typing import Dict, Any, List, Optional
from .dictionary import DynamicDomainDictionary


class SmartIntentEntityExtractor:
    """
    Schema-driven intent and entity extractor.
    """

    def __init__(self, domain_dict: Optional[DynamicDomainDictionary] = None):
        self.domain_dict = domain_dict or DynamicDomainDictionary()

    def set_domain_dict(self, domain_dict: DynamicDomainDictionary) -> None:
        self.domain_dict = domain_dict

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Dynamically extracts intent and candidate entity tokens from user input.
        """
        clean_text = text.strip()
        lower = clean_text.lower()

        # 1. Detect dynamic intent
        intent = self.domain_dict.match_intent(clean_text)

        # 2. Extract matched entities from dynamically learned vocabulary
        matched_entities = self.domain_dict.find_matching_entities(clean_text)

        # 3. Clean search keywords (remove conversational stop words in Hindi and English)
        stop_words = {
            "bhaiya", "bhai", "ji", "kya", "hai", "ka", "ki", "ke", "ko", "se", "me", "mein",
            "kitna", "kitne", "kitni", "bacha", "bache", "bachi", "pada", "rakha", "bhav", "rate",
            "daam", "keemat", "tell", "me", "show", "how", "much", "many", "what", "is", "the",
            "of", "in", "warehouse", "store", "dukan", "hoga", "chahiye", "please", "kahan", "rakha"
        }
        raw_words = re.findall(r"[a-zA-Z0-9_\-]+", lower)
        meaningful_tokens = [w for w in raw_words if w not in stop_words and len(w) > 1]

        # 4. Check for barcode or alphanumeric SKU/item code patterns (e.g. INV-100234, PART-892, 8901030001)
        code_candidates = [w for w in raw_words if (w.isdigit() and len(w) >= 6) or ("-" in w and any(c.isdigit() for c in w))]

        # Build candidate search string
        candidate_terms = []
        for me in matched_entities:
            candidate_terms.append(me["canonical"])
        for tok in meaningful_tokens:
            if not any(tok.lower() in ct.lower() for ct in candidate_terms):
                candidate_terms.append(tok)

        return {
            "raw_text": text,
            "intent": intent,
            "matched_entities": matched_entities,
            "code_candidates": code_candidates,
            "search_tokens": meaningful_tokens,
            "search_query": " ".join(candidate_terms[:4]) if candidate_terms else " ".join(meaningful_tokens[:4])
        }
