"""
connectors/universal.py
=======================
Universal Connector for SMAR (Architecture Section 4.4).
Acts as the central abstraction bus:
1. Normalizes and aggregates incoming connector data (WhatsApp, Gmail, Calendar, Drive).
2. Dispatches autonomous Work Intents in the background without stalling spoken replies.
3. Logs all automated actions to Notion.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional

from .base import BaseConnector
from .whatsapp.openwa_client import OpenWAConnector
from .google.gmail import GmailConnector
from .google.calendar import CalendarConnector
from .google.docs_sheets import GoogleDocsSheetsConnector
from .notion.notion_logger import NotionConnector

logger = logging.getLogger("smar.connectors.universal")


class UniversalConnector:
    def __init__(
        self,
        whatsapp: Optional[OpenWAConnector] = None,
        gmail: Optional[GmailConnector] = None,
        calendar: Optional[CalendarConnector] = None,
        docs_sheets: Optional[GoogleDocsSheetsConnector] = None,
        notion: Optional[NotionConnector] = None,
    ):
        self.whatsapp = whatsapp or OpenWAConnector()
        self.gmail = gmail or GmailConnector()
        self.calendar = calendar or CalendarConnector()
        self.docs_sheets = docs_sheets or GoogleDocsSheetsConnector()
        self.notion = notion or NotionConnector()

        self.connectors: Dict[str, BaseConnector] = {
            "whatsapp": self.whatsapp,
            "gmail": self.gmail,
            "calendar": self.calendar,
            "docs_sheets": self.docs_sheets,
            "notion": self.notion,
        }

    async def get_connector_statuses(self) -> Dict[str, Any]:
        """Check live connection health for all integrated external services."""
        statuses = {}
        for key, conn in self.connectors.items():
            try:
                alive = await conn.is_connected()
                statuses[key] = {
                    "name": conn.name,
                    "connected": alive,
                    "status": "online" if alive else "not_configured"
                }
            except Exception as e:
                statuses[key] = {
                    "name": conn.name,
                    "connected": False,
                    "status": f"error: {e}"
                }
        return statuses

    async def fetch_all_external_data(self, per_service_limit: int = 5) -> List[Dict[str, Any]]:
        """
        Gathers raw event and communication items from all connected channels.
        """
        all_items = []
        for name, conn in self.connectors.items():
            if name == "notion":
                continue  # Notion is primarily an audit sink
            try:
                if await conn.is_connected():
                    items = await conn.fetch_context(limit=per_service_limit)
                    all_items.extend(items)
            except Exception as e:
                logger.error(f"Failed to fetch data from {conn.name}: {e}")

        return all_items

    async def dispatch_work_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Autonomous Work Intent Execution (Section 4.3 & 6):
        Executes task in the background and audits completion in Notion.
        """
        action = intent.get("action", "").upper()
        target = intent.get("target", "")
        raw = intent.get("raw_input", "")

        logger.info(f"[UniversalConnector] Dispatching Work Intent: {action} -> {target}")
        result = {"action": action, "target": target, "status": "failed"}

        try:
            if action in ["EMAIL", "SEND_EMAIL"]:
                # Dispatch through Gmail
                subject = f"Automated Update for {target}"
                body = f"Hello,\n\nThis is an automated action requested via SMAR:\n\"{raw}\"\n\nBest regards,\nSMAR Autonomous System"
                res = await self.gmail.execute_action("SEND_EMAIL", {"to": target, "subject": subject, "body": body})
                result = {"action": action, "target": target, "success": res.get("success", False), "details": res}

            elif action in ["WHATSAPP", "SEND_WHATSAPP", "MESSAGE"]:
                # Dispatch through OpenWA
                msg_body = f"Hello! Message from SMAR assistant regarding: {raw}"
                res = await self.whatsapp.execute_action("SEND_MESSAGE", {"to": target, "message": msg_body})
                result = {"action": action, "target": target, "success": res.get("success", False), "details": res}

            elif action in ["CALENDAR", "REMINDER", "SCHEDULE"]:
                # Dispatch through Google Calendar
                res = await self.calendar.execute_action("CREATE_EVENT", {"summary": target})
                result = {"action": action, "target": target, "success": res.get("success", False), "details": res}

            else:
                result = {"action": action, "target": target, "success": False, "error": f"Unknown action {action}"}

        except Exception as e:
            logger.error(f"Error dispatching work intent {action}: {e}")
            result["error"] = str(e)

        # Audit log in Notion asynchronously
        asyncio.create_task(self.notion.log_task(
            task_name=f"{action}: {target}",
            category="Work Intent",
            status="COMPLETED" if result.get("success") else "FAILED",
            details=f"Input: {raw} | Result: {result}"
        ))

        return result
