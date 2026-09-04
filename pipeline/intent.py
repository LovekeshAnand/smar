"""
pipeline/intent.py
==================
Work intent detector for SMAR.
Extracts background action intents (e.g. email, message, task) without blocking
the immediate spoken response loop.
"""

import re
from typing import Optional, Dict, Any


class WorkIntentExtractor:
    def __init__(self):
        self.intent_patterns = [
            (r"(?:send\s+(?:an?\s+)?email|email)\s+(?:to\s+)?([A-Za-z0-9_\.\-]+(?:\s*@[^\s]+)?)", "EMAIL"),
            (r"(?:send\s+(?:a\s+)?(?:whatsapp|message)|text)\s+(?:to\s+)?([A-Za-z0-9_\.\-]+)", "WHATSAPP"),
            (r"(?:remind\s+me\s+to|set\s+a\s+reminder\s+for)\s+(.+)", "REMINDER"),
            (r"(?:search\s+for|look\s+up)\s+(.+)", "SEARCH"),
        ]

    def extract_intent(self, user_text: str) -> Optional[Dict[str, Any]]:
        """
        Determines if the speech implies an autonomous task.
        """
        cleaned = user_text.strip()
        for pattern, action_type in self.intent_patterns:
            m = re.search(pattern, cleaned, re.IGNORECASE)
            if m:
                target_or_payload = m.group(1).strip()
                return {
                    "action": action_type,
                    "target": target_or_payload,
                    "raw_input": cleaned,
                    "status": "pending_dispatch"
                }
        return None
