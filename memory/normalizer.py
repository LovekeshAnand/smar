"""
memory/normalizer.py
====================
Data Normalizer for SMAR (Architecture Section 4.4).
Transforms heterogeneous external feeds (WhatsApp, Gmail, Calendar, Docs/Sheets)
into structured Knowledge Graph triples and semantic Vector entries.
Prevents duplicate entries and ensures dense, high-signal context.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from .context_manager import ContextManager

logger = logging.getLogger("smar.memory.normalizer")


class DataNormalizer:
    def __init__(self, context_mgr: Optional[ContextManager] = None):
        self.context_mgr = context_mgr or ContextManager()

    def clean_name(self, raw_name: str) -> str:
        """Sanitizes names, emails, and phone numbers for KG node consistency."""
        if not raw_name:
            return "Unknown"
        # If email format e.g. "John Doe <john@corp.com>"
        match = re.search(r"<([^>]+)>", raw_name)
        if match:
            return match.group(1).strip()
        # Clean special chars but keep alphanumerics and basic punctuation
        cleaned = re.sub(r"[^\w\s@.-]", "", raw_name).strip()
        return cleaned or "Unknown"

    def normalize_whatsapp_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Converts WhatsApp chat/message item into triples and vector chunk."""
        sender = self.clean_name(item.get("chat_name") or item.get("sender") or "Contact")
        last_msg = (item.get("last_message") or "").strip()
        if not last_msg:
            return {"triples": [], "vector_text": ""}

        triples = [
            (sender, "Platform", "WhatsApp"),
            (sender, "ChatWith", "User"),
        ]

        # Extract meeting or time hints
        lower = last_msg.lower()
        if any(w in lower for w in ["meet", "meeting", "call", "zoom", "schedule", "at ", "pm", "am"]):
            # Short summary of meeting topic
            short_msg = last_msg[:50]
            triples.append((sender, "SuggestedMeeting", short_msg))

        vector_text = f"[WhatsApp - {sender}]: {last_msg}"
        return {
            "triples": triples,
            "vector_text": vector_text,
            "category": "whatsapp",
            "metadata": {"sender": sender, "source": "whatsapp"}
        }

    def normalize_gmail_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Converts Gmail message item into triples and vector chunk."""
        sender = self.clean_name(item.get("sender") or "Unknown Sender")
        subject = (item.get("subject") or "No Subject").strip()
        snippet = (item.get("snippet") or "").strip()

        triples = [
            (sender, "Platform", "Gmail"),
            (sender, "SentEmail", subject[:60]),
        ]

        # Detect deadline or urgency
        text_corpus = f"{subject} {snippet}".lower()
        if any(w in text_corpus for w in ["deadline", "due", "urgent", "by friday", "by monday", "tomorrow"]):
            triples.append((sender, "ActionRequired", subject[:60]))

        vector_text = f"[Gmail from {sender}]: Subject: {subject}. Snippet: {snippet}"
        return {
            "triples": triples,
            "vector_text": vector_text,
            "category": "gmail",
            "metadata": {"sender": sender, "subject": subject, "source": "gmail"}
        }

    def normalize_calendar_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Converts Calendar event item into triples and vector chunk."""
        summary = (item.get("summary") or "Untitled Event").strip()
        start = item.get("start") or "Scheduled Time"

        triples = [
            ("User", "HasEvent", summary[:60]),
            (summary[:60], "ScheduledAt", str(start)),
        ]

        desc = (item.get("description") or "").strip()
        vector_text = f"[Calendar Event]: '{summary}' scheduled at {start}."
        if desc:
            vector_text += f" Details: {desc}"

        return {
            "triples": triples,
            "vector_text": vector_text,
            "category": "calendar",
            "metadata": {"summary": summary, "start": start, "source": "calendar"}
        }

    def normalize_docs_sheets_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Converts Google Docs / Sheets document into triples and vector chunk."""
        title = (item.get("title") or "Untitled Document").strip()
        source = item.get("source", "google_docs")
        doc_type = "Google Docs" if "doc" in source else "Google Sheets"
        content = item.get("text") or item.get("summary") or ""

        triples = [
            ("User", "OwnsDocument", title[:60]),
            (title[:60], "DocumentType", doc_type),
        ]

        vector_text = f"[{doc_type}: '{title}'] Content preview: {content[:300]}"
        return {
            "triples": triples,
            "vector_text": vector_text,
            "category": "documents",
            "metadata": {"title": title, "type": doc_type, "source": source}
        }

    def normalize_item(self, raw_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Routes item to appropriate normalizer based on its 'source' tag."""
        source = raw_item.get("source", "").lower()
        if source == "whatsapp":
            return self.normalize_whatsapp_item(raw_item)
        elif source == "gmail":
            return self.normalize_gmail_item(raw_item)
        elif source == "calendar":
            return self.normalize_calendar_item(raw_item)
        elif "doc" in source or "sheet" in source:
            return self.normalize_docs_sheets_item(raw_item)
        else:
            # Generic item fallback
            text = raw_item.get("text") or raw_item.get("content") or str(raw_item)
            return {
                "triples": [],
                "vector_text": f"[{source.upper()}]: {text[:300]}",
                "category": source or "external",
                "metadata": {"source": source}
            }

    def ingest_normalized_item(self, norm_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upserts triples into KG and upserts embedding into Vector Store."""
        ingested_triples = []
        for s, p, o in norm_data.get("triples", []):
            if s and p and o:
                self.context_mgr.kg.upsert_triple(s, p, o)
                ingested_triples.append(f"{s} --[{p}]--> {o}")

        vec_text = norm_data.get("vector_text", "").strip()
        vec_res = None
        if vec_text:
            category = norm_data.get("category", "general")
            # Dense upsert to prevent runaway database bloating
            vec_id, was_updated = self.context_mgr.vectors.upsert_by_similarity(
                text=vec_text,
                category=category,
                similarity_threshold=0.88
            )
            vec_res = {"id": vec_id, "updated": was_updated}

        return {
            "triples": ingested_triples,
            "vector": vec_res
        }

    def sync_feed(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Processes a batch of items from connectors into memory."""
        total_triples = 0
        total_vectors = 0
        for item in items:
            norm = self.normalize_item(item)
            if norm:
                res = self.ingest_normalized_item(norm)
                total_triples += len(res.get("triples", []))
                if res.get("vector"):
                    total_vectors += 1

        logger.info(f"[Normalizer] Synced feed: {total_triples} triples, {total_vectors} vector memories.")
        return {
            "processed_items": len(items),
            "ingested_triples": total_triples,
            "ingested_vectors": total_vectors
        }
