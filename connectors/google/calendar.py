"""
connectors/google/calendar.py
=============================
Google Calendar connector for SMAR.
Reads upcoming schedule to inform memory and creates automated calendar events.
"""

import datetime
import logging
from typing import List, Dict, Any, Optional

from connectors.base import BaseConnector
from .auth import GoogleAuthManager

logger = logging.getLogger("smar.connectors.google.calendar")


class CalendarConnector(BaseConnector):
    def __init__(self, auth_mgr: Optional[GoogleAuthManager] = None):
        self.auth_mgr = auth_mgr or GoogleAuthManager()
        self._service = None

    @property
    def name(self) -> str:
        return "Google (Calendar)"

    def _get_service(self):
        if self._service is None:
            self._service = self.auth_mgr.build_service("calendar", "v3")
        return self._service

    async def is_connected(self) -> bool:
        """Check if Calendar service is authenticated."""
        try:
            service = self._get_service()
            if service:
                cal = service.calendars().get(calendarId="primary").execute()
                return bool(cal.get("id"))
        except Exception:
            return False
        return False

    async def fetch_context(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetches upcoming scheduled events to ground SMAR in the user's daily itinerary.
        """
        service = self._get_service()
        if not service:
            return []

        try:
            now = datetime.datetime.utcnow().isoformat() + "Z"
            events_result = service.events().list(
                calendarId="primary",
                timeMin=now,
                maxResults=limit,
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            items = events_result.get("items", [])
            events = []
            for item in items:
                start = item.get("start", {}).get("dateTime", item.get("start", {}).get("date"))
                end = item.get("end", {}).get("dateTime", item.get("end", {}).get("date"))
                events.append({
                    "source": "calendar",
                    "id": item.get("id"),
                    "summary": item.get("summary", "Untitled Meeting"),
                    "start": start,
                    "end": end,
                    "description": item.get("description", ""),
                    "attendees": [a.get("email") for a in item.get("attendees", []) if a.get("email")]
                })
            return events
        except Exception as e:
            logger.error(f"Error fetching Google Calendar context: {e}")
            return []

    async def create_event(
        self,
        summary: str,
        start_time_iso: str,
        end_time_iso: Optional[str] = None,
        description: Optional[str] = None,
        attendees: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Creates a new event in Google Calendar.
        """
        service = self._get_service()
        if not service:
            return {"success": False, "error": "Calendar service not connected."}

        try:
            # Default end time = start + 30 mins if not provided
            if not end_time_iso:
                dt = datetime.datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
                end_time_iso = (dt + datetime.timedelta(minutes=30)).isoformat()

            event_body = {
                "summary": summary,
                "description": description or "Scheduled automatically by SMAR voice assistant.",
                "start": {"dateTime": start_time_iso, "timeZone": "Asia/Kolkata"},
                "end": {"dateTime": end_time_iso, "timeZone": "Asia/Kolkata"},
            }
            if attendees:
                event_body["attendees"] = [{"email": email} for email in attendees]

            created = service.events().insert(calendarId="primary", body=event_body).execute()
            logger.info(f"Calendar event created: {summary} at {start_time_iso}")
            return {
                "success": True,
                "event_id": created.get("id"),
                "html_link": created.get("htmlLink"),
                "summary": summary
            }
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            return {"success": False, "error": str(e)}

    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        act_norm = action.upper()
        if act_norm in ["CREATE_EVENT", "CALENDAR", "SCHEDULE", "REMINDER"]:
            summary = params.get("summary") or params.get("title") or params.get("event") or "SMAR Scheduled Task"
            start_time = params.get("start_time") or params.get("time") or datetime.datetime.utcnow().isoformat()
            end_time = params.get("end_time")
            desc = params.get("description")
            return await self.create_event(summary=summary, start_time_iso=start_time, end_time_iso=end_time, description=desc)
        return {"success": False, "error": f"Unsupported action: {action}"}
