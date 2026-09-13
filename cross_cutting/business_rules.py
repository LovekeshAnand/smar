"""
cross_cutting/business_rules.py
===============================
Business Rules Engine for SMAR.
Provides a decoupled, persistent policy and operational rule store.
Allows uploading, querying, and dynamically injecting enterprise guidelines
(e.g., warehouse protocols, SLA limits, discount tiers, return policies)
directly into the LLM reasoning context without polluting core memory graphs.
"""

import os
import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("smar.cross_cutting.business_rules")

RULES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "business_rules.json")

DEFAULT_BUSINESS_RULES = [
    {
        "id": "RULE-WMS-001",
        "title": "Hazardous & Chemical Goods Climate Storage",
        "category": "safety",
        "priority": 10,
        "keywords": ["hazmat", "chemical", "hazardous", "storage", "zone", "temperature", "climate"],
        "description": "All hazardous materials, chemical solvents, and flammable stock must be stored exclusively in climate-controlled Zone C with 24/7 temperature monitoring (15°C - 20°C) and Level-3 fire suppression.",
        "is_active": True,
        "created_at": "2026-09-01T00:00:00Z"
    },
    {
        "id": "RULE-PRC-002",
        "title": "Enterprise Bulk Order Volume Discount",
        "category": "pricing",
        "priority": 8,
        "keywords": ["bulk", "discount", "order", "quantity", "500", "wholesale", "pricing", "volume"],
        "description": "Orders exceeding 500 units of any product line automatically qualify for a 15% wholesale volume discount. Bulk orders over 2,000 units require custom quote sign-off from sales management.",
        "is_active": True,
        "created_at": "2026-09-01T00:00:00Z"
    },
    {
        "id": "RULE-OPS-003",
        "title": "High-Value Inventory Transfer Authorization",
        "category": "operations",
        "priority": 9,
        "keywords": ["transfer", "high-value", "manager", "authorization", "sign-off", "1000", "expensive"],
        "description": "Any single inventory relocation, write-off, or warehouse transfer exceeding $1,000 in total value requires dual authorization: one Warehouse Supervisor and one Operations Manager sign-off.",
        "is_active": True,
        "created_at": "2026-09-01T00:00:00Z"
    },
    {
        "id": "RULE-SLA-004",
        "title": "Same-Day Order Dispatch Cutoff",
        "category": "sla",
        "priority": 7,
        "keywords": ["cutoff", "same-day", "dispatch", "shipping", "deadline", "delivery", "time", "4 pm", "16:00"],
        "description": "Standard orders received before 16:00 IST (4:00 PM) must be picked, packed, and handed to logistics carriers on the same business day. Orders after 16:00 IST are scheduled for next-day dispatch.",
        "is_active": True,
        "created_at": "2026-09-01T00:00:00Z"
    },
    {
        "id": "RULE-RET-005",
        "title": "Customer Return & Restocking Window",
        "category": "returns",
        "priority": 6,
        "keywords": ["return", "refund", "restocking", "window", "30 days", "policy", "damaged", "reverse"],
        "description": "Merchandise returns are accepted within 30 days of documented customer delivery. Returned items must undergo a barcode QA inspection before being restocked into active inventory.",
        "is_active": True,
        "created_at": "2026-09-01T00:00:00Z"
    },
    {
        "id": "RULE-SLA-006",
        "title": "Logistics SLA Idle Escalation",
        "category": "sla",
        "priority": 8,
        "keywords": ["escalation", "idle", "delay", "stuck", "pending", "sla", "48 hours", "carrier"],
        "description": "Any order remaining in 'Pending Shipment' or 'Awaiting Pickup' status for longer than 48 hours automatically triggers an automated high-priority SLA escalation to logistics dispatch.",
        "is_active": True,
        "created_at": "2026-09-01T00:00:00Z"
    }
]


class BusinessRulesEngine:
    """
    Manages enterprise operational rules, policies, and procedural constraints.
    Enables runtime upload and intelligent retrieval for LLM grounding.
    """

    def __init__(self, rules_file: str = RULES_FILE):
        self.rules_file = rules_file
        os.makedirs(os.path.dirname(self.rules_file), exist_ok=True)
        self.rules: List[Dict[str, Any]] = []
        self._load_rules()

    def _load_rules(self) -> None:
        if os.path.exists(self.rules_file):
            try:
                with open(self.rules_file, "r", encoding="utf-8") as f:
                    self.rules = json.load(f)
                logger.info(f"Loaded {len(self.rules)} business rules from {self.rules_file}")
                return
            except Exception as e:
                logger.warning(f"Error loading business rules file, reseeding: {e}")
        self.rules = list(DEFAULT_BUSINESS_RULES)
        self._save_rules()

    def _save_rules(self) -> None:
        try:
            with open(self.rules_file, "w", encoding="utf-8") as f:
                json.dump(self.rules, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist business rules: {e}")

    def list_rules(self, category: Optional[str] = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """Return all business rules, optionally filtered by category and active status."""
        results = []
        for r in self.rules:
            if active_only and not r.get("is_active", True):
                continue
            if category and r.get("category", "").lower() != category.lower():
                continue
            results.append(r)
        return results

    def add_rule(
        self,
        title: str,
        description: str,
        category: str = "operations",
        priority: int = 5,
        keywords: Optional[List[str]] = None,
        is_active: bool = True
    ) -> Dict[str, Any]:
        """Add or update an individual business rule."""
        rule_id = f"RULE-{category[:3].upper()}-{uuid.uuid4().hex[:4].upper()}"
        clean_keywords = [k.strip().lower() for k in (keywords or []) if k.strip()]
        if not clean_keywords:
            # Auto-extract words from title
            clean_keywords = [w.lower() for w in title.split() if len(w) > 3]

        new_rule = {
            "id": rule_id,
            "title": title.strip(),
            "category": category.strip().lower(),
            "priority": priority,
            "keywords": clean_keywords,
            "description": description.strip(),
            "is_active": is_active,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.rules.append(new_rule)
        self._save_rules()
        logger.info(f"Added business rule: {rule_id} - '{title}'")
        return new_rule

    def ingest_rules_document(self, text_content: str, source_name: str = "upload") -> List[Dict[str, Any]]:
        """
        Parse and ingest a raw text or markdown document containing business rules.
        Recognizes numbered lists, bullet points, or JSON arrays.
        """
        added_rules: List[Dict[str, Any]] = []
        # Attempt JSON parse first
        try:
            parsed = json.loads(text_content)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "title" in item and "description" in item:
                        added = self.add_rule(
                            title=item["title"],
                            description=item["description"],
                            category=item.get("category", "operations"),
                            priority=item.get("priority", 5),
                            keywords=item.get("keywords")
                        )
                        added_rules.append(added)
                return added_rules
        except Exception:
            pass

        # Fallback to line-by-line / section-based markdown parser
        lines = [ln.strip() for ln in text_content.splitlines() if ln.strip()]
        current_title = ""
        current_desc = []

        for line in lines:
            if line.startswith(("#", "Rule:", "RULE:", "**", "- **")):
                if current_title and current_desc:
                    added = self.add_rule(
                        title=current_title,
                        description=" ".join(current_desc),
                        category="operations"
                    )
                    added_rules.append(added)
                    current_desc = []
                clean_title = line.lstrip("#-* ").replace("**", "").replace("Rule:", "").strip()
                current_title = clean_title
            else:
                if current_title:
                    current_desc.append(line)

        if current_title and current_desc:
            added = self.add_rule(
                title=current_title,
                description=" ".join(current_desc),
                category="operations"
            )
            added_rules.append(added)

        return added_rules

    def delete_rule(self, rule_id: str) -> bool:
        """Deactivate or remove a rule by ID."""
        initial_len = len(self.rules)
        self.rules = [r for r in self.rules if r["id"] != rule_id]
        if len(self.rules) < initial_len:
            self._save_rules()
            return True
        return False

    def get_applicable_rules(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieves active rules relevant to the user query based on keyword overlap
        and category alignment, sorted by priority and relevance score.
        """
        query_words = set(w.lower() for w in query.replace("?", "").replace("!", "").replace(",", "").split())
        scored_rules = []

        for rule in self.rules:
            if not rule.get("is_active", True):
                continue
            keywords = set(k.lower() for k in rule.get("keywords", []))
            overlap = len(query_words.intersection(keywords))
            # Also check substring occurrence in query
            for kw in keywords:
                if len(kw) > 3 and kw in query.lower():
                    overlap += 1

            if overlap > 0:
                score = (overlap * 10) + rule.get("priority", 5)
                scored_rules.append((score, rule))

        scored_rules.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored_rules[:top_k]]

    def format_rules_for_prompt(self, rules: List[Dict[str, Any]]) -> str:
        """Renders rules into a structured system prompt directive block."""
        if not rules:
            return ""
        lines = [
            "=== ACTIVE ENTERPRISE BUSINESS RULES ===",
            "[You must strictly adhere to the following enterprise policies and operational rules]:"
        ]
        for r in rules:
            lines.append(f"- [{r['id']}] ({r.get('category', 'general').upper()}): {r['description']}")
        lines.append("If user query asks about policies, limits, discounts, or workflows, cite the exact rule details above.")
        return "\n".join(lines)


# Global singleton
business_rules_engine = BusinessRulesEngine()
