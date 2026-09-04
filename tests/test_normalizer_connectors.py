"""
tests/test_normalizer_connectors.py
===================================
Unit tests for SMAR Data Normalizer, Connectors, and Universal Bus.
"""

import os
import tempfile
import asyncio
import pytest
from memory.context_manager import ContextManager
from memory.normalizer import DataNormalizer
from connectors.universal import UniversalConnector


def test_data_normalizer_whatsapp():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_norm.db")
    ctx = ContextManager(db_path=db_path)
    normalizer = DataNormalizer(context_mgr=ctx)

    wa_item = {
        "source": "whatsapp",
        "chat_name": "Alice Tech Lead",
        "sender": "919876543210@c.us",
        "last_message": "Let's schedule a Zoom meeting at 4pm today regarding sprint planning.",
        "timestamp": 1718000000
    }

    norm = normalizer.normalize_item(wa_item)
    assert norm is not None
    assert norm["category"] == "whatsapp"
    assert any(t[1] == "Platform" and t[2] == "WhatsApp" for t in norm["triples"])
    assert any(t[1] == "SuggestedMeeting" for t in norm["triples"])

    # Ingest
    res = normalizer.ingest_normalized_item(norm)
    assert len(res["triples"]) > 0

    # Retrieve context
    ctx_text = ctx.retrieve_context("Alice meeting")
    assert "Alice" in ctx_text


def test_data_normalizer_gmail():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_norm_gmail.db")
    ctx = ContextManager(db_path=db_path)
    normalizer = DataNormalizer(context_mgr=ctx)

    gmail_item = {
        "source": "gmail",
        "sender": "John Boss <boss@company.com>",
        "subject": "Urgent: Q3 Budget Review Deadline Tomorrow",
        "snippet": "Please submit your numbers before noon tomorrow.",
        "date": "2026-09-04"
    }

    norm = normalizer.normalize_item(gmail_item)
    assert norm is not None
    assert norm["category"] == "gmail"
    assert any(t[1] == "SentEmail" for t in norm["triples"])
    assert any(t[1] == "ActionRequired" for t in norm["triples"])

    # Ingest feed
    feed_stats = normalizer.sync_feed([gmail_item])
    assert feed_stats["ingested_triples"] >= 2
    assert feed_stats["ingested_vectors"] == 1


def test_data_normalizer_calendar():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_norm_cal.db")
    ctx = ContextManager(db_path=db_path)
    normalizer = DataNormalizer(context_mgr=ctx)

    cal_item = {
        "source": "calendar",
        "summary": "Engineering All-Hands",
        "start": "2026-09-05T10:00:00Z",
        "description": "Monthly engineering roadmap discussion"
    }

    norm = normalizer.normalize_item(cal_item)
    assert any(t[1] == "HasEvent" for t in norm["triples"])
    assert any(t[1] == "ScheduledAt" for t in norm["triples"])


def test_universal_connector_statuses():
    async def _test():
        bus = UniversalConnector()
        statuses = await bus.get_connector_statuses()
        assert "whatsapp" in statuses
        assert "gmail" in statuses
        assert "calendar" in statuses
        assert "docs_sheets" in statuses
        assert "notion" in statuses
    asyncio.run(_test())


def test_universal_connector_dispatch():
    async def _test():
        bus = UniversalConnector()
        res = await bus.dispatch_work_intent({
            "action": "EMAIL",
            "target": "test@example.com",
            "raw_input": "Send update to test@example.com"
        })
        assert res["action"] == "EMAIL"
        assert res["target"] == "test@example.com"
    asyncio.run(_test())

