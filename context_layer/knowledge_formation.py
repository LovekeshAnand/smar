"""
context_layer/knowledge_formation.py
====================================
Knowledge formation and fact extraction pipeline for SMAR.
Extracts structured relational triples and semantic concepts from user turns.
Handles pronoun disambiguation ('I', 'my' -> user_id), entity resolution,
and contradiction detection.
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional, Set

logger = logging.getLogger("smar.context_layer.knowledge_formation")

# Common stop words to exclude when extracting query entities
STOP_WORDS: Set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below", "from",
    "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "s", "t", "can", "will", "just", "don", "should", "now",
    "what", "who", "which", "whose", "whom", "tell", "show", "please",
    "hey", "hi", "hello", "okay", "ok", "assistant", "smar", "do", "does", "did"
}

# Heuristic patterns for rapid zero-dependency relational extraction
EXTRACTION_PATTERNS = [
    # User's name: "my name is Lovkesh" / "I am Lovkesh" / "call me Lovkesh"
    (re.compile(r"(?:my name is|i am|call me)\s+([A-Z][a-zA-Z0-9_\-\s]{1,30})", re.IGNORECASE), "Name"),
    
    # Location / Residence: "I live in Delhi" / "I moved to Bangalore" / "I am in Mumbai" / "my city is Pune"
    (re.compile(r"(?:i live in|i moved to|i am currently living in|my city is|i stay in)\s+([A-Za-z\s]{2,30})", re.IGNORECASE), "LivesIn"),
    
    # Work / Role: "I work at Google" / "I work as a software engineer" / "my role is founder" / "I joined Microsoft"
    (re.compile(r"(?:i work at|i am working at|i joined)\s+([A-Za-z0-9\s]{2,40})", re.IGNORECASE), "WorksAt"),
    (re.compile(r"(?:i work as a|i work as an|my role is|my job is|i am a)\s+([A-Za-z0-9\s]{2,40})", re.IGNORECASE), "Role"),
    
    # Contact: "my email is test@example.com"
    (re.compile(r"(?:my email is|email me at|my email id is)\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", re.IGNORECASE), "Email"),
    
    # Phone: "my phone is 9876543210"
    (re.compile(r"(?:my phone is|my mobile is|my number is)\s+([+0-9\s\-]{7,20})", re.IGNORECASE), "Phone"),
    
    # Preferences: "I prefer dark mode" / "I like Python" / "my favorite language is Rust"
    (re.compile(r"(?:i prefer|i love|i really like)\s+([A-Za-z0-9\s]{2,40})", re.IGNORECASE), "Prefers"),
    (re.compile(r"(?:my favorite\s+([A-Za-z0-9]+)\s+is)\s+([A-Za-z0-9\s]{2,40})", re.IGNORECASE), "Favorite"),
]


class KnowledgeFormationPipeline:
    """
    Pipeline that turns unstructured conversational input into structured knowledge.
    Disambiguates pronouns and tags memories strictly with user_id.
    """

    def __init__(self, assistant_name: str = "SMAR"):
        self.assistant_name = assistant_name

    def extract_entities(self, text: str) -> List[str]:
        """
        Extracts salient query entities from input text for graph & vector search.
        Filters stop words, punctuation, and system keywords.
        """
        if not text:
            return []

        # Find capitalized words (proper nouns) and quoted phrases
        proper_nouns = re.findall(r"\b[A-Z][a-zA-Z0-9_-]+\b", text)
        quotes = re.findall(r'"([^"]+)"', text)

        # Tokenize general words
        words = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", text)
        keywords = [w for w in words if w.lower() not in STOP_WORDS]

        combined: List[str] = []
        seen = set()

        for term in quotes + proper_nouns + keywords:
            clean = term.strip()
            low = clean.lower()
            if low not in seen and low not in STOP_WORDS and low != self.assistant_name.lower():
                seen.add(low)
                combined.append(clean)

        return combined[:8]

    def extract_facts(self, text: str, user_id: str) -> List[Dict[str, Any]]:
        """
        Extracts structured relational triples from text.
        Substitutes first-person pronouns ('I', 'my', 'me') with the concrete user_id.
        """
        facts: List[Dict[str, Any]] = []
        user_clean = user_id.strip() or "default_user"

        for pattern, predicate in EXTRACTION_PATTERNS:
            matches = pattern.finditer(text)
            for m in matches:
                if predicate == "Favorite":
                    # Captures (category, value) e.g. "favorite language is Rust"
                    cat = m.group(1).strip()
                    val = m.group(2).strip()
                    facts.append({
                        "user_id": user_clean,
                        "subject": user_clean,
                        "predicate": f"Favorite_{cat.capitalize()}",
                        "object": val,
                        "confidence": 0.95
                    })
                else:
                    val = m.group(1).strip().rstrip(".,!?")
                    facts.append({
                        "user_id": user_clean,
                        "subject": user_clean,
                        "predicate": predicate,
                        "object": val,
                        "confidence": 0.95
                    })

        # Relational statements between third-party entities:
        # e.g., "Arjun works with Sweta" / "Delhi is the capital of India"
        rel_pattern = re.compile(
            r"([A-Z][a-zA-Z0-9_]+)\s+(works with|reports to|is married to|lives with|collaborates with)\s+([A-Z][a-zA-Z0-9_]+)",
            re.IGNORECASE
        )
        for m in rel_pattern.finditer(text):
            sub = m.group(1).strip()
            pred = m.group(2).strip().title().replace(" ", "")
            obj = m.group(3).strip()
            facts.append({
                "user_id": user_clean,
                "subject": sub,
                "predicate": pred,
                "object": obj,
                "confidence": 0.90
            })

        return facts

    def should_store_semantic(self, text: str) -> bool:
        """
        Determines whether a message contains substantive information worthy
        of entering the semantic vector memory (avoids chitchat / greetings).
        """
        clean = text.strip()
        if len(clean) < 10:
            return False

        low = clean.lower()
        chitchat = {
            "hello", "hi", "hey", "good morning", "good evening",
            "thank you", "thanks", "ok", "okay", "bye", "goodbye",
            "who are you", "what can you do", "yes", "no", "sure"
        }
        if low in chitchat:
            return False

        # If it's just a simple short question like "what time is it?"
        if low.startswith(("what time", "who is", "how are you")) and len(low.split()) <= 5:
            return False

        return True
