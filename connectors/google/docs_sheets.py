"""
connectors/google/docs_sheets.py
================================
Google Docs, Sheets, and Drive connector for SMAR.
Extracts document text and spreadsheet tables to feed structured knowledge into memory.
"""

import logging
from typing import List, Dict, Any, Optional

from connectors.base import BaseConnector
from .auth import GoogleAuthManager

logger = logging.getLogger("smar.connectors.google.docs_sheets")


class GoogleDocsSheetsConnector(BaseConnector):
    def __init__(self, auth_mgr: Optional[GoogleAuthManager] = None):
        self.auth_mgr = auth_mgr or GoogleAuthManager()
        self._drive = None
        self._docs = None
        self._sheets = None

    @property
    def name(self) -> str:
        return "Google (Drive, Docs & Sheets)"

    def _get_drive(self):
        if self._drive is None:
            self._drive = self.auth_mgr.build_service("drive", "v3")
        return self._drive

    def _get_docs(self):
        if self._docs is None:
            self._docs = self.auth_mgr.build_service("docs", "v1")
        return self._docs

    def _get_sheets(self):
        if self._sheets is None:
            self._sheets = self.auth_mgr.build_service("sheets", "v4")
        return self._sheets

    async def is_connected(self) -> bool:
        """Check if Drive API is accessible."""
        try:
            drive = self._get_drive()
            if drive:
                res = drive.files().list(pageSize=1).execute()
                return "files" in res
        except Exception:
            return False
        return False

    def read_doc_text(self, document_id: str) -> str:
        """Extracts all text from a Google Doc."""
        docs = self._get_docs()
        if not docs:
            return ""
        try:
            doc = docs.documents().get(documentId=document_id).execute()
            text_parts = []
            for element in doc.get("body", {}).get("content", []):
                if "paragraph" in element:
                    for p_elem in element["paragraph"].get("elements", []):
                        if "textRun" in p_elem:
                            text_parts.append(p_elem["textRun"].get("content", ""))
            return "".join(text_parts).strip()
        except Exception as e:
            logger.error(f"Error reading Google Doc {document_id}: {e}")
            return ""

    def read_sheet_values(self, spreadsheet_id: str, range_name: str = "Sheet1!A1:Z50") -> List[List[Any]]:
        """Extracts rows and columns from a Google Sheet."""
        sheets = self._get_sheets()
        if not sheets:
            return []
        try:
            result = sheets.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Error reading Google Sheet {spreadsheet_id}: {e}")
            return []

    async def fetch_context(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Lists recently modified Docs and Sheets in Google Drive and extracts snippets for memory ingestion.
        """
        drive = self._get_drive()
        if not drive:
            return []

        try:
            query = "mimeType = 'application/vnd.google-apps.document' or mimeType = 'application/vnd.google-apps.spreadsheet'"
            results = drive.files().list(
                q=query,
                pageSize=limit,
                fields="files(id, name, mimeType, modifiedTime)"
            ).execute()

            files = results.get("files", [])
            context_items = []

            for f in files:
                file_id = f["id"]
                name = f["name"]
                mime = f["mimeType"]

                snippet = ""
                if "document" in mime:
                    snippet = self.read_doc_text(file_id)[:1000]
                elif "spreadsheet" in mime:
                    rows = self.read_sheet_values(file_id)
                    snippet = "; ".join([", ".join(map(str, row)) for row in rows[:5]])

                if snippet:
                    context_items.append({
                        "source": "google_drive",
                        "id": file_id,
                        "title": name,
                        "mime": mime,
                        "content": snippet
                    })

            return context_items
        except Exception as e:
            logger.error(f"Error fetching Drive documents: {e}")
            return []

    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        act_norm = action.upper()
        if act_norm in ["READ_DOC", "GET_DOC"]:
            doc_id = params.get("doc_id") or params.get("id")
            if not doc_id:
                return {"success": False, "error": "Missing doc_id"}
            text = self.read_doc_text(doc_id)
            return {"success": True, "content": text}
        return {"success": False, "error": f"Unsupported action: {action}"}
