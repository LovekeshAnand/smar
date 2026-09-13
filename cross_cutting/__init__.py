"""
cross_cutting
=============
Cross-Cutting Services Layer for SMAR.
Provides:
- Business Rules Engine (Policy ingestion, storage, semantic retrieval)
- Security & Privacy (Hierarchical RBAC, clearance verification)
- Admin Alert Inbox (Security incident auditing & real-time dispatch)
"""

from cross_cutting.business_rules import (
    BusinessRulesEngine,
    business_rules_engine
)
from cross_cutting.admin_alerts import (
    AdminAlertManager,
    admin_alert_manager
)
from cross_cutting.telegram_notifier import (
    TelegramNotifier,
    telegram_notifier
)
from cross_cutting.security_ruleset import (
    SecurityAccessController,
    security_access_controller,
    AccessDecision,
    ROLE_HIERARCHY,
    RESTRICTED_ACCESS_MESSAGE
)

__all__ = [
    "BusinessRulesEngine",
    "business_rules_engine",
    "AdminAlertManager",
    "admin_alert_manager",
    "TelegramNotifier",
    "telegram_notifier",
    "SecurityAccessController",
    "security_access_controller",
    "AccessDecision",
    "ROLE_HIERARCHY",
    "RESTRICTED_ACCESS_MESSAGE"
]
