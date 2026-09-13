"""
cross_cutting/security_ruleset.py
=================================
Hierarchical Role-Based Access Control (RBAC) and Memory Clearance Ruleset for SMAR.
Governs which users can query specific database tables, financial metrics,
confidential memory nodes, and executive-level records.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from cross_cutting.admin_alerts import admin_alert_manager

logger = logging.getLogger("smar.cross_cutting.security")

# Role Clearance Hierarchy Levels
ROLE_HIERARCHY: Dict[str, int] = {
    "guest": 0,
    "user": 1,
    "operator": 1,
    "supervisor": 2,
    "manager": 3,
    "director": 4,
    "admin": 5,
}

# Access Denial Response specified by enterprise compliance
RESTRICTED_ACCESS_MESSAGE = (
    "You don't have access to this information. "
    "An alert has been sent to the admin inbox regarding the requested data. "
    "If you believe this is an error, please contact your system administrator."
)

# Sensitive Patterns requiring higher clearance
# Level 3 (Manager+) or Level 5 (Admin)
RESTRICTED_PATTERNS: List[Dict[str, Any]] = [
    {
        "category": "HR & Payroll",
        "patterns": [r"\bsalar(y|ies)\b", r"\bpayroll\b", r"\bcompensation\b", r"\bwages?\b", r"\bbonus(es)?\b"],
        "min_level": 3,  # Manager+
        "resource": "Employee Salaries & Payroll Records",
        "clearance_name": "MANAGER",
    },
    {
        "category": "Executive Financials",
        "patterns": [r"\bprofit margins?\b", r"\bcompany revenue\b", r"\bebitda\b", r"\bexecutive bonuses?\b", r"\bnet income\b"],
        "min_level": 4,  # Director+
        "resource": "Executive Financial & Margin Audits",
        "clearance_name": "DIRECTOR",
    },
    {
        "category": "Root System & Security",
        "patterns": [r"\badmin password\b", r"\bdatabase credentials\b", r"\broot key\b", r"\bsecurity audit logs?\b", r"\bapi secret\b"],
        "min_level": 5,  # Admin
        "resource": "Root Credentials & Security Logs",
        "clearance_name": "ADMIN",
    },
    {
        "category": "Supplier Contracts & Terms",
        "patterns": [r"\bsupplier contract\b", r"\bconfidential pricing agreement\b", r"\bprocurement kickback\b"],
        "min_level": 3,  # Manager+
        "resource": "Confidential Supplier Contracts",
        "clearance_name": "MANAGER",
    },
]


@dataclass
class AccessDecision:
    is_allowed: bool
    reason: Optional[str] = None
    denial_message: Optional[str] = None
    resource: Optional[str] = None
    clearance_required: Optional[str] = None


class SecurityAccessController:
    """
    Enforces hierarchical memory and database access clearance.
    Detects unauthorized queries, dispatches alerts, and generates compliant refusals.
    """

    def __init__(self):
        self.hierarchy = ROLE_HIERARCHY

    def get_role_level(self, role: Optional[str]) -> int:
        clean_role = (role or "user").strip().lower()
        return self.hierarchy.get(clean_role, 1)

    def evaluate_query_access(
        self,
        user_id: str,
        user_name: str,
        role: str,
        query: str
    ) -> AccessDecision:
        """
        Evaluates whether a user's role has sufficient clearance for the given query.
        If denied, automatically logs an alert to the Admin Inbox and returns AccessDecision.
        """
        user_level = self.get_role_level(role)
        query_lower = query.lower()

        for rule in RESTRICTED_PATTERNS:
            for pattern in rule["patterns"]:
                if re.search(pattern, query_lower):
                    min_level = rule["min_level"]
                    if user_level < min_level:
                        resource = rule["resource"]
                        clearance_req = rule["clearance_name"]
                        reason = f"User role '{role}' (level {user_level}) does not meet required clearance '{clearance_req}' (level {min_level}) for {resource}."

                        # Automatically record to Admin Alert Inbox
                        admin_alert_manager.log_alert(
                            user_id=user_id,
                            user_name=user_name,
                            role=role,
                            query=query,
                            resource_requested=resource,
                            clearance_required=clearance_req,
                            severity="HIGH"
                        )

                        return AccessDecision(
                            is_allowed=False,
                            reason=reason,
                            denial_message=RESTRICTED_ACCESS_MESSAGE,
                            resource=resource,
                            clearance_required=clearance_req
                        )

        return AccessDecision(is_allowed=True)

    def filter_memory_nodes(self, user_role: str, target_user_id: str, current_user_id: str, facts: List[str]) -> List[str]:
        """
        Filters out memory triples and facts if user lacks clearance
        (e.g., operator attempting to inspect director/admin personal memories).
        """
        user_level = self.get_role_level(user_role)

        # Users can always access their own personal memories
        if target_user_id == current_user_id:
            return facts

        # If inspecting another user's memories, requires Manager (Level 3+)
        if user_level < 3:
            logger.info(f"Filtered out cross-user memories for {current_user_id} regarding {target_user_id}")
            return []

        return facts


# Global singleton
security_access_controller = SecurityAccessController()
