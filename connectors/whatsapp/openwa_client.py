"""
connectors/whatsapp/openwa_client.py
====================================
WhatsApp connector for SMAR using OpenWA Gateway (v0.23).
Reads incoming messages to ground the Knowledge Graph in daily communications,
and sends autonomous messages via OpenWA REST endpoints.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional
import httpx

from connectors.base import BaseConnector

logger = logging.getLogger("smar.connectors.whatsapp")


class OpenWAConnector(BaseConnector):
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("OPENWA_API_URL", "http://localhost:2785")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENWA_API_KEY", "")
        self.session_id = session_id or os.getenv("OPENWA_SESSION_ID", "wa-cbb0c2dcb63e3f0d")
        self._resolved_session: Optional[str] = None

    @property
    def name(self) -> str:
        return "WhatsApp (OpenWA)"

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def format_chat_id(self, recipient: str) -> str:
        """
        Normalizes phone numbers, group IDs, or LIDs into proper WhatsApp chatId format.
        Prefixes 10-digit numbers with India code '91'.
        """
        if not recipient:
            return ""
        clean = recipient.strip()
        if clean.endswith("@c.us") or clean.endswith("@lid") or clean.endswith("@g.us"):
            return clean

        digits = re.sub(r"\D", "", clean)
        if len(digits) == 10:
            digits = f"91{digits}"
        return f"{digits}@c.us"

    async def is_connected(self) -> bool:
        """Checks if OpenWA server is responsive."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{self.base_url}/api/health", headers=self._get_headers())
                if r.status_code == 200:
                    return True
                # Fallback check
                r_status = await client.get(f"{self.base_url}/health", headers=self._get_headers())
                return r_status.status_code == 200
        except Exception:
            return False

    async def resolve_session(self) -> Optional[str]:
        """Resolves active session ID from OpenWA."""
        if self._resolved_session:
            return self._resolved_session

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/sessions", headers=self._get_headers())
                if r.status_code == 200:
                    sessions = r.json()
                    if isinstance(sessions, list):
                        # Match by configured session ID
                        for s in sessions:
                            s_id = s.get("id") or s.get("name")
                            if s_id and (s_id == self.session_id or s.get("status") in ["ready", "WORKING"]):
                                self._resolved_session = s_id
                                return s_id
                        if sessions:
                            self._resolved_session = sessions[0].get("id") or sessions[0].get("name")
                            return self._resolved_session
        except Exception as e:
            logger.debug(f"Could not query OpenWA sessions: {e}")

        self._resolved_session = self.session_id
        return self._resolved_session

    async def fetch_context(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Fetches recent chats and messages to feed user context into Knowledge Graph.
        """
        if not await self.is_connected():
            return []

        session = await self.resolve_session()
        if not session:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{self.base_url}/api/sessions/{session}/chats"
                r = await client.get(url, headers=self._get_headers())
                if r.status_code == 200:
                    chats = r.json()
                    if isinstance(chats, list):
                        results = []
                        for c in chats[:limit]:
                            results.append({
                                "source": "whatsapp",
                                "chat_name": c.get("name") or c.get("formattedTitle") or "Unknown Contact",
                                "sender": c.get("id") or c.get("jid") or "",
                                "last_message": c.get("lastMessage", {}).get("body") or c.get("snippet") or "",
                                "timestamp": c.get("timestamp") or c.get("t") or 0,
                            })
                        return results
        except Exception as e:
            logger.error(f"Error fetching WhatsApp context: {e}")

        return []

    async def send_message(self, to: str, message: str) -> Dict[str, Any]:
        """
        Sends a WhatsApp message via OpenWA Gateway.
        """
        chat_id = self.format_chat_id(to)
        if not chat_id:
            return {"success": False, "error": "Invalid recipient format"}

        session = await self.resolve_session()
        if not session:
            return {"success": False, "error": "No active OpenWA session found"}

        endpoint = f"{self.base_url}/api/sessions/{session}/messages/send-text"
        payload = {
            "chatId": chat_id,
            "text": message.strip()
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                r = await client.post(endpoint, headers=self._get_headers(), json=payload)
                if r.status_code in [200, 201]:
                    logger.info(f"WhatsApp message dispatched to {chat_id}")
                    return {"success": True, "target": chat_id, "data": r.json()}
                else:
                    return {"success": False, "status_code": r.status_code, "error": r.text}
        except Exception as e:
            logger.error(f"Failed to dispatch WhatsApp message to {chat_id}: {e}")
            return {"success": False, "error": str(e)}

    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches action from Autonomous Work Intent."""
        act_norm = action.upper()
        if act_norm in ["SEND_MESSAGE", "WHATSAPP", "SEND"]:
            to = params.get("to") or params.get("target") or params.get("recipient")
            text = params.get("message") or params.get("text") or params.get("body")
            if not to or not text:
                return {"success": False, "error": "Missing 'to' or 'message' parameter"}
            return await self.send_message(to, text)
        return {"success": False, "error": f"Unsupported action: {action}"}
