"""
context_layer/knowledge_formation.py
====================================
Knowledge formation and fact extraction pipeline for SMAR.
Extracts structured relational triples and semantic concepts from user turns.
Combines comprehensive clause-splitting heuristic extraction (English & Hindi/Hinglish)
with local LLM-assisted cognitive extraction for continuous, organic knowledge formation.
"""

import re
import json
import logging
from typing import List, Dict, Any, Tuple, Optional, Set
import httpx

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

# Rich heuristic patterns for instant zero-dependency relational extraction
EXTRACTION_PATTERNS = [
    # User's name: handles "my name is X", "i am called X", "call me X", "i am X", "i'm X"
    (re.compile(
        r"(?:(?:my name is|i am called|call me|myself)\s+|(?:^|\b)(?:i am|i'm)\s+(?!(?:a|an|the|just|looking|asking|trying|here|not|so|very|currently|always|busy|working|going|from)\b))([A-Za-z][A-Za-z0-9_\-]*(?:\s+[A-Za-z][A-Za-z0-9_\-]*)?)(?=\s+(?:can|could|please|and|who|from|,|\.|$)|$)",
        re.IGNORECASE
    ), "Name"),
    (re.compile(r"(?:मेरा नाम|main hoon)\s+([A-Za-z\u0900-\u097F\s]{1,30})", re.IGNORECASE), "Name"),
    
    # Location / Residence / Origin
    (re.compile(r"(?:(?<!don't\s)(?<!do not\s)i live in|i moved to|i am currently living in|my city is|i stay in|i am based in|i am from|i'm from)\s+([A-Za-z\u0900-\u097F\s]{2,30})", re.IGNORECASE), "LivesIn"),
    (re.compile(r"(?:main|mein)\s+([A-Za-z\u0900-\u097F\s]{2,30})\s+(?:me rehta|se hu|rehti)", re.IGNORECASE), "LivesIn"),
    
    # Work / Company / Role / Profession
    (re.compile(r"(?:i work at|i am working at|i joined|my company is)\s+([A-Za-z0-9\s]{2,40})", re.IGNORECASE), "WorksAt"),
    (re.compile(r"(?:i work as a|i work as an|my role is|my job is|i am a|i'm a|i am an|i'm an)\s+([A-Za-z0-9\s]{2,40})", re.IGNORECASE), "Role"),
    
    # Projects / Building / Creating
    (re.compile(r"(?:i am building|i'm building|i am working on|i'm working on|my project is|we are building|i develop)\s+([A-Za-z0-9\s\-_]{2,50})", re.IGNORECASE), "Building"),
    
    # Tech Stack & Skills
    (re.compile(r"(?:my tech stack is|i code in|i program in|i use|i am proficient in)\s+([A-Za-z0-9\s,\-_]{2,50})", re.IGNORECASE), "UsesTechnology"),
    
    # Education
    (re.compile(r"(?:i studied at|i graduated from|i study at|i am a student at|my college is)\s+([A-Za-z0-9\s]{2,40})", re.IGNORECASE), "StudiedAt"),
    
    # Contact
    (re.compile(r"(?:my email is|email me at|my email id is)\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", re.IGNORECASE), "Email"),
    (re.compile(r"(?:my phone is|my mobile is|my number is)\s+([+0-9\s\-]{7,20})", re.IGNORECASE), "Phone"),
    
    # Likes / Loves / Preferences
    (re.compile(r"(?:i prefer|i love|i really like|i enjoy|i like)\s+([A-Za-z0-9\s]{2,40})", re.IGNORECASE), "Prefers"),
    (re.compile(r"(?:mujhe|humko)\s+([A-Za-z0-9\s\u0900-\u097F]{2,30})\s+(?:pasand|accha lagta)", re.IGNORECASE), "Prefers"),
    
    # Dislikes
    (re.compile(r"(?:i dislike|i hate|i don't like|i do not like)\s+([A-Za-z0-9\s]{2,40})", re.IGNORECASE), "Dislikes"),
    
    # Favorites
    (re.compile(r"(?:my favorite\s+([A-Za-z0-9]+)\s+is)\s+([A-Za-z0-9\s]{2,40})", re.IGNORECASE), "Favorite"),
]


class KnowledgeFormationPipeline:
    """
    Pipeline that turns unstructured conversational turns into structured knowledge.
    Disambiguates pronouns and tags memories strictly with user_id.
    """

    def __init__(self, assistant_name: str = "SMAR"):
        self.assistant_name = assistant_name

    def _split_into_clauses(self, text: str) -> List[str]:
        """Splits compound sentences by conjunctions to prevent compound fact bleeding."""
        split_regex = r"(?:\s+(?:and|also|as well as|plus|aur|तथा|और|can you|could you|please|so you can|so please|so)\s+|[;\n]+|(?<=[a-zA-Z0-9])\.\s+(?=[A-Z\u0900-\u097F])|,\s*(?=[a-z\u0900-\u097F]))"
        raw_clauses = re.split(split_regex, text, flags=re.IGNORECASE)
        clauses = []
        for c in raw_clauses:
            cleaned = c.strip()
            if len(cleaned) > 2:
                clauses.append(cleaned)
        return clauses if clauses else [text.strip()]

    def _clean_val(self, val: str) -> str:
        """Strips filler words, punctuation, and leading/trailing whitespace."""
        cleaned = re.sub(r'[\.!?,;:\'"]+$', '', val.strip()).strip()
        cleaned = re.sub(r'\s+(?:and|also|too|as well)\s*$', '', cleaned, flags=re.IGNORECASE).strip()
        return cleaned

    def extract_entities(self, text: str) -> List[str]:
        """
        Extracts salient query entities from input text for graph & vector search.
        Filters stop words, punctuation, and system keywords.
        """
        if not text:
            return []

        proper_nouns = re.findall(r"\b[A-Z][a-zA-Z0-9_-]+\b", text)
        quotes = re.findall(r'"([^"]+)"', text)
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
        Extracts structured relational triples from text using clause-splitting heuristics.
        Substitutes first-person pronouns ('I', 'my', 'me') with the concrete user_id.
        """
        facts: List[Dict[str, Any]] = []
        user_clean = user_id.strip() or "default_user"
        clauses = self._split_into_clauses(text)

        seen_keys = set()

        for clause in clauses:
            # Check if clause is purely a question / inquiry asking for information
            clause_clean = clause.strip()
            is_pure_question = bool(re.search(
                r"^(?:what|who|where|when|why|how|which|whose|whom|is|are|can|could|would|do|does|did|tell|show|give)\b",
                clause_clean,
                re.IGNORECASE
            )) or clause_clean.endswith("?")

            for pattern, predicate in EXTRACTION_PATTERNS:
                # If clause is a question asking about name/location, do not extract it as a statement
                if is_pure_question and predicate in ("Name", "LivesIn", "Role", "WorksAt"):
                    continue

                matches = pattern.finditer(clause)
                for m in matches:
                    if predicate == "Favorite":
                        cat = self._clean_val(m.group(1))
                        val = self._clean_val(m.group(2))
                        pred = f"Favorite_{cat.capitalize()}"
                    else:
                        val = self._clean_val(m.group(1))
                        pred = predicate

                    if val and len(val) >= 2:
                        key = (user_clean.lower(), pred.lower(), val.lower())
                        if key not in seen_keys:
                            seen_keys.add(key)
                            facts.append({
                                "user_id": user_clean,
                                "subject": user_clean,
                                "predicate": pred,
                                "object": val,
                                "confidence": 0.95
                            })

            # Third-party relational statements: e.g., "Sweta works at Google"
            rel_pattern = re.compile(
                r"([A-Z][a-zA-Z0-9_]+)\s+(works with|reports to|works at|is married to|lives in)\s+([A-Z][a-zA-Z0-9_\s]+)",
                re.IGNORECASE
            )
            for m in rel_pattern.finditer(clause):
                sub = self._clean_val(m.group(1))
                pred = m.group(2).strip().title().replace(" ", "")
                obj = self._clean_val(m.group(3))
                if sub.lower() != self.assistant_name.lower() and obj:
                    key = (sub.lower(), pred.lower(), obj.lower())
                    if key not in seen_keys:
                        seen_keys.add(key)
                        facts.append({
                            "user_id": user_clean,
                            "subject": sub,
                            "predicate": pred,
                            "object": obj,
                            "confidence": 0.90
                        })

        return facts

    async def extract_facts_llm(
        self,
        user_text: str,
        reply_text: str = "",
        user_id: str = "default_user",
        api_base: str = "http://127.0.0.1:8088"
    ) -> List[Dict[str, Any]]:
        """
        Uses the local Epsilon LLM (Qwen 7B) to extract nuanced, natural conversational facts.
        Strictly extracts facts stated by the user about themselves, never attributing
        database records or assistant replies to the user.
        """
        if not user_text or len(user_text.strip()) < 5:
            return []

        user_clean = user_id.strip() or "default_user"

        prompt = (
            "<|im_start|>system\n"
            f"You are a knowledge graph extractor for an AI assistant named {self.assistant_name}.\n"
            f"Extract personal facts, identity, location, role, or preferences explicitly stated by the human user ({user_clean}) about themselves.\n\n"
            "CRITICAL RULES:\n"
            f"1. Extract facts ONLY when the user explicitly reveals personal facts about themselves (e.g. name, location, job, preferences).\n"
            f"2. Subject must be '{user_clean}'.\n"
            "3. NEVER extract questions, inquiries, or database search queries.\n"
            "   - Questions like 'what is my name?', 'what was the 1st question?', 'who are you?', 'what is employee salary?' are QUESTIONS, NOT FACTS. Output [] for them.\n"
            "4. NEVER attribute database items, inventory details, employee records, order dates, or assistant lookup answers to the user.\n"
            "5. If a message contains an introduction followed by a question (e.g. 'hi i am lokesh can you tell me...'), ONLY extract the user's name ('Name' -> 'lokesh'). Do NOT extract the question or warehouse details.\n"
            "6. Output format: Return ONLY a valid JSON array of objects with keys 'subject', 'predicate', 'object', or [] if no personal facts are found.\n"
            "<|im_end|>\n"
            "<|im_start|>user\n"
            f"User message: \"{user_text}\"\n"
            "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

        endpoint = api_base.rstrip("/")
        if endpoint.endswith("/v1"):
            endpoint = endpoint[:-3]
        endpoint = f"{endpoint}/completion"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    endpoint,
                    json={
                        "prompt": prompt,
                        "n_predict": 128,
                        "temperature": 0.0,
                        "stop": ["<|im_end|>", "\n\n", "```\n"],
                        "stream": False
                    }
                )
                if res.status_code != 200:
                    return []

                raw = res.json().get("content", "").strip()
                # Clean code markdown blocks if present
                clean = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
                clean = re.sub(r"```$", "", clean).strip()

                # Find outermost JSON array brackets
                start_bracket = clean.find("[")
                end_bracket = clean.rfind("]")
                if start_bracket == -1 or end_bracket == -1 or end_bracket < start_bracket:
                    return []

                json_str = clean[start_bracket:end_bracket + 1]
                parsed = json.loads(json_str)

                invalid_placeholders = {
                    "not specified", "unknown", "none", "n/a", "unspecified",
                    "null", "not mentioned", "not provided", "tbd", "n.a.",
                    "nothing", "not available", "none specified", "no info", "not given"
                }

                invalid_predicates = {
                    "question", "first_question", "looking up data", "query", "asking"
                }

                valid_facts = []
                for item in parsed:
                    if isinstance(item, dict) and "predicate" in item and "object" in item:
                        sub = item.get("subject", user_clean).strip()
                        pred = item.get("predicate", "").strip()
                        obj = item.get("object", "").strip()

                        # Discard invalid predicates or placeholders
                        if pred.lower() in invalid_predicates:
                            continue
                        low_obj = obj.lower()
                        if low_obj in invalid_placeholders or any(low_obj.startswith(p) for p in ("not specified", "not mentioned", "unknown", "unspecified")):
                            continue

                        if pred and obj and len(obj) >= 2:
                            if sub.lower() in ("user", "i", "me", user_clean.lower()):
                                sub = user_clean
                            valid_facts.append({
                                "user_id": user_clean,
                                "subject": sub,
                                "predicate": pred,
                                "object": obj,
                                "confidence": 0.95
                            })
                return valid_facts
        except Exception as e:
            logger.debug(f"LLM fact extraction skipped or failed: {e}")
            return []

    def should_store_semantic(self, text: str) -> bool:
        """
        Determines whether a message contains substantive PERSONAL information worthy
        of entering the semantic vector memory.

        STRICT POLICY:
        - Only store genuine personal user statements (name, location, job, preferences).
        - NEVER store transactional queries, database lookups, or question-answer pairs.
        - Any text mentioning database entity keywords (order, salary, price, employee, etc.)
          is assumed transactional and blocked regardless of phrasing.
        """
        clean = text.strip()
        if len(clean) < 6:
            return False

        low = clean.lower()

        # Block pure greetings / chitchat
        greetings = {"hello", "hi", "hey", "bye", "goodbye", "ok", "okay", "thanks", "thank you",
                     "naa", "hmm", "uh", "um", "yes", "no", "sure", "alright", "fine"}
        if low in greetings:
            return False

        # Block ANY query starting with question words — these are always lookups
        if re.match(
            r"^(?:what|who|where|when|why|how|which|whose|whom|is|are|can|could|"
            r"tell\s+me|show\s+me|give\s+me|find|search|check|list|display|get|fetch|"
            r"hi\s+what|hi\s+can|hi\s+how|hi\s+could|hi\s+please|hi\s+i)\b",
            low
        ):
            return False

        # Block texts mentioning transactional/warehouse entity keywords
        transactional_keywords = {
            "order", "employee", "salary", "price", "stock", "product", "shipment",
            "payment", "promotion", "customer", "supplier", "return", "category",
            "qty", "quantity", "amount", "sum", "count", "avg", "average", "total",
            "item", "invoice", "bill", "receipt", "transaction", "store", "revenue",
            "profit", "loss", "discount", "refund", "tax", "fee"
        }
        words_in_text = set(re.findall(r'\b[a-z]+\b', low))
        if words_in_text & transactional_keywords:
            return False

        # Block texts that are "User: ...\nAssistant: ..." QA pairs
        if "user:" in low and "assistant:" in low:
            return False

        # Block unrecognized speech placeholders
        if "unrecognized speech" in low:
            return False

        return True
