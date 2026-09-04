"""
connectors/notion/notion_logger.py
==================================
Notion connector for SMAR.
Automatically logs tasks, action audits, and newly learned knowledge graph facts
into a structured Notion database.
"""

import os
import datetime
import logging
from typing import List, Dict, Any, Optional
import httpx

from connectors.base import BaseConnector

logger = logging.getLogger("smar.connectors.notion")


class NotionConnector(BaseConnector):
    def __init__(
        self,
        api_key: Optional[str] = None,
        database_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("NOTION_API_KEY", "")
        self.database_id = database_id or os.getenv("NOTION_DATABASE_ID", "")
        self.base_url = "https://api.notion.com/v1"

    @property
    def name(self) -> str:
        return "Notion"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

    async def is_connected(self) -> bool:
        """Verify Notion token validity."""
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/users/me", headers=self._get_headers())
                return r.status_code == 200
        except Exception:
            return False

    async def log_task(
        self,
        task_name: str,
        category: str,
        status: str = "COMPLETED",
        details: str = "",
    ) -> Dict[str, Any]:
        """
        Appends an action log row to the Notion database.
        """
        if not self.api_key or not self.database_id:
            logger.debug("Notion credentials not set; skipping remote log.")
            return {"logged": False, "reason": "No credentials"}

        now_iso = datetime.datetime.utcnow().isoformat()

        payload = {
            "parent": {"database_id": self.database_id},
            "properties": {
                "Task": {
                    "title": [{"text": {"content": task_name[:100]}}]
                },
                "Category": {
                    "select": {"name": category[:50]}
                },
                "Status": {
                    "status": {"name": status}
                },
                "Timestamp": {
                    "date": {"start": now_iso}
                },
                "Details": {
                    "rich_text": [{"text": {"content": details[:2000]}}]
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    f"{self.base_url}/pages",
                    headers=self._get_headers(),
                    json=payload
                )
                if r.status_code in [200, 201]:
                    logger.info(f"Task logged to Notion: {task_name}")
                    return {"logged": True, "page_id": r.json().get("id")}
                else:
                    logger.warning(f"Notion log returned {r.status_code}: {r.text}")
                    return {"logged": False, "error": r.text}
        except Exception as e:
            logger.error(f"Failed to log task to Notion: {e}")
            return {"logged": False, "error": str(e)}

    async def fetch_context(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Queries Notion database to retrieve recent task history and active projects.
        """
        if not self.api_key or not self.database_id:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    f"{self.base_url}/databases/{self.database_id}/query",
                    headers=self._get_headers(),
                    json={"page_size": limit}
                )
                if r.status_code == 200:
                    data = r.json()
                    results = []
                    for page in data.get("results", []):
                        props = page.get("properties", {})
                        title_parts = props.get("Task", {}).get("title", [])
                        task_text = title_parts[0].get("text", {}).get("content", "") if title_parts else "Task"
                        results.append({
                            "source": "notion",
                            "id": page.get("id"),
                            "title": task_text,
                        })
                    return results
        except Exception as e:
            logger.error(f"Error fetching Notion context: {e}")
        return []

    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        act_norm = action.upper()
        if act_norm in ["LOG", "LOG_TASK", "NOTION_LOG"]:
            task = params.get("task") or params.get("title") or "Automated Action"
            cat = params.get("category", "General")
            status = params.get("status", "COMPLETED")
            details = params.get("details", "")
            return await self.log_task(task_name=task, category=cat, status=status, details=details)
        return {"success": False, "error": f"Unsupported action: {action}"}
