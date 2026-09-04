"""
memory/extractor.py
===================
Fact and entity extractor for SMAR conversation turns.
Converts conversational text into clean, atomic relational triples.
Supports clause splitting (English & Hindi) to prevent compound fact pollution.
"""

import re
from typing import List, Dict, Any, Tuple


class FactExtractor:
    def __init__(self, default_user: str = "User"):
        self.default_user = default_user
        
        # English patterns
        self.patterns = [
            # Likes / Dislikes
            (r"(?:i|user)\s+(?:really\s+)?(?:like|love|prefer|enjoy)\s+([^,\.;]+)", "Likes"),
            (r"(?:i|user)\s+do\s+not\s+(?:like|enjoy)\s+([^,\.;]+)", "Dislikes"),
            # Identity / Occupation / Name
            (r"(?:my name is|i am called)\s+([A-Za-z0-9_\-]+)", "Named"),
            (r"(?:i am|i'm)\s+(?:a|an)\s+([A-Za-z0-9_\-\s]+)", "IsA"),
            # Contact / Location
            (r"(?:my email is)\s+([^\s]+@[^\s]+)", "HasEmail"),
            (r"(?:my phone is|my number is)\s+([0-9\+\-\s]{8,15})", "HasPhone"),
            (r"(?:i live in|i am based in|my location is)\s+([A-Za-z\s]+)", "LivesIn"),
            # Third-person facts (e.g. Sweta likes Python, Alex works at...)
            (r"([A-Z][a-z]+)\s+(?:likes|loves|prefers)\s+([^,\.;]+)", "Likes"),
            (r"([A-Z][a-z]+)\s+(?:works at|works for)\s+([^,\.;]+)", "WorksAt"),
            (r"([A-Z][a-z]+)\s+(?:lives in|is located in)\s+([^,\.;]+)", "LivesIn"),
            
            # Hindi patterns
            (r"मेरा नाम\s+([A-Za-z\u0900-\u097F]+)\s+है", "Named"),
            (r"मुझे\s+([A-Za-z0-9_\-\s\u0900-\u097F]+)\s+(?:पसंद|अच्छा लगता|अच्छी लगती)\s+है", "Likes"),
            (r"मेरी ईमेल\s+([^\s]+@[^\s]+)\s+है", "HasEmail"),
            (r"मैं\s+([A-Za-z\u0900-\u097F\s]+)\s+में रहता हूँ", "LivesIn"),
        ]

    def _split_into_clauses(self, text: str) -> List[str]:
        """
        Splits compound sentences by conjunctions and punctuation to extract atomic facts.
        """
        # Split on: and, also, as well as, aur, तथा, comma, semicolon, or sentence-ending periods (followed by space and capital)
        split_regex = r"(?:\s+(?:and|also|as well as|plus|aur|तथा|और)\s+|[;\n]+|(?<=[a-zA-Z0-9])\.\s+(?=[A-Z\u0900-\u097F])|,\s*(?=[a-z\u0900-\u097F]))"
        raw_clauses = re.split(split_regex, text, flags=re.IGNORECASE)
        
        clauses = []
        for c in raw_clauses:
            cleaned = c.strip()
            if len(cleaned) > 2:
                clauses.append(cleaned)
        return clauses

    def _clean_object(self, obj: str) -> str:
        """Strips filler words, trailing punctuation, and conjunctions from extracted object."""
        cleaned = obj.strip()
        # Remove trailing punctuation
        cleaned = re.sub(r'[\.!?,;:\'"]+$', '', cleaned).strip()
        # Strip common trailing conjunctions if any leaked
        cleaned = re.sub(r'\s+(?:and|also|too|as well)\s*$', '', cleaned, flags=re.IGNORECASE).strip()
        return cleaned

    def extract_facts(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Extracts list of clean (subject, predicate, object) atomic triples.
        """
        triples = []
        clauses = self._split_into_clauses(text)

        for clause in clauses:
            for pattern, predicate in self.patterns:
                m = re.search(pattern, clause, re.IGNORECASE)
                if m:
                    groups = m.groups()
                    if len(groups) == 1:
                        sub = self.default_user
                        raw_obj = groups[0]
                    elif len(groups) >= 2:
                        sub = groups[0].strip()
                        raw_obj = groups[1]
                    else:
                        continue

                    obj = self._clean_object(raw_obj)
                    if sub and obj and len(obj) > 1:
                        # Avoid duplicates
                        triple = (sub, predicate, obj)
                        if triple not in triples:
                            triples.append(triple)
                    break  # One predicate per atomic clause

        return triples

    def extract_potential_entities(self, text: str) -> List[str]:
        """
        Extracts key nouns or capitalized names that could match Knowledge Graph entities.
        """
        entities = [self.default_user]
        words = text.split()
        for w in words:
            clean_w = re.sub(r'[^A-Za-z0-9\u0900-\u097F]', '', w)
            if clean_w and (clean_w[0].isupper() or len(clean_w) > 4):
                if clean_w.lower() not in ["hello", "please", "thanks", "could", "would", "where", "what", "which"]:
                    entities.append(clean_w)
        return list(set(entities))
