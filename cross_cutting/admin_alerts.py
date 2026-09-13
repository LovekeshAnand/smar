"""
cross_cutting/admin_alerts.py
=============================
Admin Security Incident & Alert Inbox Service.
Maintains an auditable, persistent security event log for access violations,
unauthorized data inspection attempts, and memory clearance breaches.
"""

import os
import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("smar.cross_cutting.admin_alerts")

ALERTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "admin_alerts.json")


class AdminAlertManager:
    """
    Manages security alerts dispatched when users attempt to access
    restricted memory, confidential data, or unauthorized business actions.
    """

    def __init__(self, alerts_file: str = ALERTS_FILE):
        self.alerts_file = alerts_file
        os.makedirs(os.path.dirname(self.alerts_file), exist_ok=True)
        self.alerts: List[Dict[str, Any]] = []
        self._load_alerts()

    def _load_alerts(self) -> None:
        if os.path.exists(self.alerts_file):
            try:
                with open(self.alerts_file, "r", encoding="utf-8") as f:
                    self.alerts = json.load(f)
                logger.info(f"Loaded {len(self.alerts)} admin security alerts.")
                return
            except Exception as e:
                logger.warning(f"Error reading admin alerts file: {e}")
        self.alerts = []
        self._save_alerts()

    def _save_alerts(self) -> None:
        try:
            with open(self.alerts_file, "w", encoding="utf-8") as f:
                json.dump(self.alerts, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist admin alerts: {e}")

    def log_alert(
        self,
        user_id: str,
        user_name: str,
        role: str,
        query: str,
        resource_requested: str,
        clearance_required: str = "ADMIN",
        severity: str = "HIGH"
    ) -> Dict[str, Any]:
        """Log a new unauthorized access violation incident."""
        alert_id = f"ALT-{uuid.uuid4().hex[:6].upper()}"
        alert_record = {
            "id": alert_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "user_name": user_name,
            "role": role,
            "query": query,
            "resource_requested": resource_requested,
            "clearance_required": clearance_required,
            "severity": severity,
            "status": "UNRESOLVED",
            "resolution_note": None,
            "resolved_at": None,
            "resolved_by": None
        }
        self.alerts.insert(0, alert_record)  # Newest first
        self._save_alerts()
        logger.warning(
            f"SECURITY ALERT [{alert_id}]: User '{user_id}' (role: {role}) "
            f"attempted unauthorized access to '{resource_requested}' via query: '{query}'"
        )
        return alert_record

    def list_alerts(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List alerts, optionally filtered by status ('UNRESOLVED', 'RESOLVED')."""
        if not status:
            return self.alerts[:limit]
        return [a for a in self.alerts if a.get("status") == status.upper()][:limit]

    def resolve_alert(self, alert_id: str, resolved_by: str = "admin", note: str = "") -> Optional[Dict[str, Any]]:
        """Mark an alert as reviewed and resolved."""
        for alert in self.alerts:
            if alert["id"] == alert_id:
                alert["status"] = "RESOLVED"
                alert["resolved_at"] = datetime.now(timezone.utc).isoformat()
                alert["resolved_by"] = resolved_by
                alert["resolution_note"] = note or "Verified and dismissed by administrator."
                self._save_alerts()
                logger.info(f"Resolved security alert {alert_id} by {resolved_by}")
                return alert
        return None

    def get_unresolved_count(self) -> int:
        """Count how many alerts require administrator attention."""
        return sum(1 for a in self.alerts if a.get("status") == "UNRESOLVED")


# Global singleton
admin_alert_manager = AdminAlertManager()
