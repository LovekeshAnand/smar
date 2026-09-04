"""
connectors/google/gmail.py
==========================
Gmail connector for SMAR.
Reads emails to feed context into the Knowledge Graph and sends automated emails.
"""

import base64
import logging
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional

from connectors.base import BaseConnector
from .auth import GoogleAuthManager

logger = logging.getLogger("smar.connectors.google.gmail")


class GmailConnector(BaseConnector):
    def __init__(self, auth_mgr: Optional[GoogleAuthManager] = None):
        self.auth_mgr = auth_mgr or GoogleAuthManager()
        self._service = None

    @property
    def name(self) -> str:
        return "Google (Gmail)"

    def _get_service(self):
        if self._service is None:
            self._service = self.auth_mgr.build_service("gmail", "v1")
        return self._service

    async def is_connected(self) -> bool:
        """Check if Gmail API is authenticated and responsive."""
        try:
            service = self._get_service()
            if service:
                profile = service.users().getProfile(userId="me").execute()
                return bool(profile.get("emailAddress"))
        except Exception:
            return False
        return False

    async def fetch_context(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetches recent emails to build user context (senders, ongoing projects, tasks).
        """
        service = self._get_service()
        if not service:
            return []

        try:
            results = service.users().messages().list(userId="me", maxResults=limit, q="category:primary").execute()
            messages = results.get("messages", [])
            emails = []

            for msg in messages:
                msg_data = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
                headers = {h["name"].lower(): h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
                
                emails.append({
                    "source": "gmail",
                    "id": msg["id"],
                    "subject": headers.get("subject", "(No Subject)"),
                    "from": headers.get("from", "Unknown"),
                    "date": headers.get("date", ""),
                    "snippet": msg_data.get("snippet", ""),
                })
            return emails
        except Exception as e:
            logger.error(f"Error fetching Gmail context: {e}")
            return []

    async def send_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """
        Sends an email using Gmail API.
        """
        service = self._get_service()
        if not service:
            return {"success": False, "error": "Gmail service not connected. Please authorize via credentials.json"}

        try:
            message = MIMEText(body)
            message["to"] = to.strip()
            message["subject"] = subject.strip()
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            sent = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
            logger.info(f"Email successfully sent to {to} (Message ID: {sent.get('id')})")
            return {"success": True, "message_id": sent.get("id"), "to": to, "subject": subject}
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"success": False, "error": str(e)}

    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        act_norm = action.upper()
        if act_norm in ["SEND_EMAIL", "EMAIL"]:
            to = params.get("to") or params.get("target") or params.get("recipient")
            subject = params.get("subject", "Message from SMAR")
            body = params.get("body") or params.get("message") or params.get("text", "")
            if not to:
                return {"success": False, "error": "Missing recipient 'to' address."}
            return await self.send_email(to=to, subject=subject, body=body)
        return {"success": False, "error": f"Unsupported action: {action}"}
