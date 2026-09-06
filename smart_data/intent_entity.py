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

    def _normalize_stt_numbers(self, text: str) -> str:
        """
        Normalise common Speech-to-Text transcription artifacts where a single
        large number is split across colon-separated groups or space-separated
        digit chunks that contextually belong together.

        Examples handled:
          "05:02 580"   -> "0502580"  (colon = continuation, then space)
          "52 05 80"    -> kept as tokens (could be 3 separate values)
          "order id 05:02 580" -> "order id 0502580"

        Strategy:
          1. Collapse all NN:MM patterns into NNMM (remove colon).
          2. Merge adjacent whitespace-separated token sequences that are ALL
             digits (and together would form 5-8 digit IDs) into one token.
             We gate this on context: only merge when adjacent to a keyword
             like "order", "id", "item", "product", "employee", "shipment",
             "payment", "customer", "return", "number", "#".
        """
        # Step 1: collapse colon-joined digit groups (STT reads "05:02" for 0502)
        normalized = re.sub(r'\b(\d+):(\d+)\b', r'\1\2', text)

        # Step 2: after a known ID-context keyword, merge space-separated digit
        # tokens if their concatenation is 5-10 digits long
        id_context_pattern = re.compile(
            r'(?<!\w)(order|item|order item|product|employee|shipment|payment|customer|return|number|#|id|no\.?)\s+'
            r'(\d+(?:\s+\d+)*)',
            re.IGNORECASE
        )

        def merge_digits(m):
            keyword = m.group(1)
            digit_seq = m.group(2)
            tokens = digit_seq.split()
            merged = ''.join(tokens)
            # Only merge if result is between 4 and 10 digits (ID range)
            if 4 <= len(merged) <= 10 and len(tokens) > 1:
                return f"{keyword} {merged}"
            return m.group(0)

        normalized = id_context_pattern.sub(merge_digits, normalized)
        return normalized

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Dynamically extracts intent and candidate entity tokens from user input.
        Handles STT transcription normalisation, numeric ID extraction across
        arbitrary schemas, and domain-vocabulary entity matching.
        """
        # Apply STT normalization before any further processing
        normalized_text = self._normalize_stt_numbers(text)
        clean_text = normalized_text.strip()
        lower = clean_text.lower()

        # 1. Detect dynamic intent
        intent = self.domain_dict.match_intent(clean_text)

        # 2. Extract matched entities from dynamically learned vocabulary
        matched_entities = self.domain_dict.find_matching_entities(clean_text)

        # 3. Clean search keywords (remove conversational stop words in Hindi and English)
        stop_words = {
            "can", "could", "would", "you", "i", "we", "they", "it", "that", "this", "these", "those",
            "was", "were", "is", "are", "am", "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "tell", "me", "show", "how", "much", "many", "what", "s", "the", "a", "an",
            "of", "in", "on", "at", "by", "for", "with", "about", "against", "between", "into", "through",
            "during", "before", "after", "above", "below", "to", "from", "up", "down", "give", "find", "get", "check",
            "bhaiya", "bhai", "ji", "kya", "hai", "ka", "ki", "ke", "ko", "se", "me", "mein",
            "kitna", "kitne", "kitni", "bacha", "bache", "bachi", "pada", "rakha", "bhav", "rate",
            "daam", "keemat", "warehouse", "store", "dukan", "hoga", "chahiye", "please", "kahan", "rakha"
        }
        raw_words = re.findall(r"[a-zA-Z0-9_\-]+", lower)
        meaningful_tokens = [w for w in raw_words if w not in stop_words and len(w) > 1]

        # 4. Extract numeric ID candidates from the NORMALIZED text
        #    Include: plain integers, alphanumeric codes with dashes, and
        #    digit-only tokens that are plausible IDs (>= 2 digits)
        code_candidates: List[str] = []
        seen_codes = set()

        # First: grab anything that looks like a bare numeric or alphanumeric code
        for w in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-]*[0-9][a-zA-Z0-9\-]*", lower):
            # Only keep if it has at least one digit and is purely numeric OR alphanumeric-with-dash
            if any(c.isdigit() for c in w) and w not in seen_codes:
                code_candidates.append(w)
                seen_codes.add(w)

        # Also grab any standalone digit sequences that are >= 2 digits long
        for w in re.findall(r"\b\d{2,}\b", lower):
            if w not in seen_codes:
                code_candidates.append(w)
                seen_codes.add(w)

        # Build candidate search string: prioritize domain entities, then substantive tokens
        candidate_terms = []
        for me in matched_entities:
            candidate_terms.append(me["canonical"])
        for tok in meaningful_tokens:
            if not any(tok.lower() in ct.lower() for ct in candidate_terms):
                candidate_terms.append(tok)

        # Build search query preserving domain terms and specific qualifiers (e.g. date, action)
        search_query_terms = candidate_terms if candidate_terms else meaningful_tokens
        search_query = " ".join(search_query_terms[:6])

        return {
            "raw_text": text,
            "normalized_text": normalized_text,
            "intent": intent,
            "matched_entities": matched_entities,
            "code_candidates": code_candidates,
            "search_query": search_query
        }
