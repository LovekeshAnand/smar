"""
memory/extractor.py
===================
Fact and entity extractor for SMAR conversation turns.
Converts conversational text into relational triples and semantic concepts.
"""

import re
from typing import List, Dict, Any, Tuple


class FactExtractor:
    def __init__(self, default_user: str = "User"):
        self.default_user = default_user
        
        # Heuristic extraction patterns for conversational facts
        self.patterns = [
            # Likes / Prefers
            (r"(?:i|user)\s+(?:really\s+)?(?:like|love|prefer|enjoy)\s+(.+)", "Likes"),
            (r"(?:i|user)\s+do\s+not\s+(?:like|enjoy)\s+(.+)", "Dislikes"),
            # Identity / Occupation
            (r"(?:i am|i'm)\s+(?:a|an)\s+(.+)", "IsA"),
            (r"(?:my name is)\s+([A-Za-z]+)", "Named"),
            # Contact / Location
            (r"(?:my email is)\s+([^\s]+@[^\s]+)", "HasEmail"),
            (r"(?:my phone is)\s+([0-9\+\-\s]{8,15})", "HasPhone"),
            (r"(?:i live in|i am based in)\s+([A-Za-z\s]+)", "LivesIn"),
            # Third-person facts (e.g. Sweta likes Python, Alex works at...)
            (r"([A-Z][a-z]+)\s+(?:likes|loves|prefers)\s+(.+)", "Likes"),
            (r"([A-Z][a-z]+)\s+(?:works at|works for)\s+(.+)", "WorksAt"),
            (r"([A-Z][a-z]+)\s+(?:lives in|is located in)\s+(.+)", "LivesIn"),
        ]

    def extract_facts(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Extracts list of (subject, predicate, object) triples from text.
        """
        triples = []
        cleaned = text.strip()

        for pattern, predicate in self.patterns:
            matches = re.finditer(pattern, cleaned, re.IGNORECASE)
            for m in matches:
                groups = m.groups()
                if len(groups) == 1:
                    # Subject is default_user
                    sub = self.default_user
                    obj = groups[0].strip().rstrip(".!?,")
                elif len(groups) >= 2:
                    sub = groups[0].strip()
                    obj = groups[1].strip().rstrip(".!?,")
                else:
                    continue

                if sub and obj:
                    triples.append((sub, predicate, obj))

        return triples

    def extract_potential_entities(self, text: str) -> List[str]:
        """
        Extracts key nouns or capitalized names that could match Knowledge Graph entities.
        """
        entities = [self.default_user]
        words = text.split()
        for w in words:
            clean_w = re.sub(r'[^A-Za-z0-9]', '', w)
            if clean_w and (clean_w[0].isupper() or len(clean_w) > 4):
                if clean_w.lower() not in ["hello", "please", "thanks", "could", "would"]:
                    entities.append(clean_w)
        return list(set(entities))
