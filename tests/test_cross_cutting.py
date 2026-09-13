"""
tests/test_cross_cutting.py
===========================
Unit tests for SMAR Cross-Cutting Services Layer:
- Business Rules Engine (ingestion, persistence, semantic keyword matching)
- Hierarchical RBAC & Security Access Controller
- Admin Alert Inbox & Incident Resolution
"""

import os
import pytest
from cross_cutting import (
    BusinessRulesEngine,
    SecurityAccessController,
    AdminAlertManager,
    RESTRICTED_ACCESS_MESSAGE
)


@pytest.fixture
def temp_rules_engine(tmp_path):
    rules_file = os.path.join(tmp_path, "test_rules.json")
    return BusinessRulesEngine(rules_file=rules_file)


@pytest.fixture
def temp_alert_manager(tmp_path):
    alerts_file = os.path.join(tmp_path, "test_alerts.json")
    return AdminAlertManager(alerts_file=alerts_file)


def test_business_rules_defaults(temp_rules_engine):
    rules = temp_rules_engine.list_rules()
    assert len(rules) >= 6
    categories = {r["category"] for r in rules}
    assert "safety" in categories
    assert "pricing" in categories
    assert "operations" in categories


def test_business_rules_matching(temp_rules_engine):
    # Query about bulk orders
    matched = temp_rules_engine.get_applicable_rules("What discount do we offer for bulk orders over 500 units?")
    assert len(matched) > 0
    assert "500" in matched[0]["description"] or "discount" in matched[0]["title"].lower()

    # Query about hazmat / chemicals
    matched_haz = temp_rules_engine.get_applicable_rules("Where do we store hazardous chemical materials?")
    assert len(matched_haz) > 0
    assert "Zone C" in matched_haz[0]["description"]


def test_business_rules_custom_upload(temp_rules_engine):
    doc = """
    # Battery Storage Protocols
    Lithium-ion batteries must be stored in fire-retardant dry cabinets with automatic halon suppression.
    
    # Priority Express Pick SLA
    Express orders must be picked and packed within 15 minutes of intake.
    """
    added = temp_rules_engine.ingest_rules_document(doc)
    assert len(added) == 2

    # Verify retrieval of new rule
    matches = temp_rules_engine.get_applicable_rules("What is the protocol for lithium-ion battery storage?")
    assert len(matches) > 0
    assert "fire-retardant" in matches[0]["description"]


def test_security_rbac_denial_for_operator():
    controller = SecurityAccessController()
    
    # Operator queries salary (requires Level 3 Manager)
    decision = controller.evaluate_query_access(
        user_id="rajesh",
        user_name="Rajesh",
        role="operator",
        query="What is the average salary of employees in warehouse A?"
    )
    assert not decision.is_allowed
    assert decision.denial_message == RESTRICTED_ACCESS_MESSAGE
    assert decision.clearance_required == "MANAGER"


def test_security_rbac_allowed_for_manager_and_admin():
    controller = SecurityAccessController()

    # Manager queries salary
    decision_mgr = controller.evaluate_query_access(
        user_id="priya",
        user_name="Priya",
        role="manager",
        query="What is the average salary of employees in warehouse A?"
    )
    assert decision_mgr.is_allowed

    # Admin queries root security
    decision_admin = controller.evaluate_query_access(
        user_id="lovekesh",
        user_name="Lovekesh",
        role="admin",
        query="Show system security audit logs"
    )
    assert decision_admin.is_allowed


def test_admin_alerts_logging_and_resolution(temp_alert_manager):
    initial_unresolved = temp_alert_manager.get_unresolved_count()
    
    alert = temp_alert_manager.log_alert(
        user_id="rajesh",
        user_name="Rajesh",
        role="operator",
        query="Show me the executive bonus pool and salaries",
        resource_requested="Employee Salaries & Payroll Records",
        clearance_required="MANAGER",
        severity="HIGH"
    )
    assert alert["status"] == "UNRESOLVED"
    assert temp_alert_manager.get_unresolved_count() == initial_unresolved + 1

    # Resolve the alert
    resolved = temp_alert_manager.resolve_alert(alert["id"], resolved_by="lovekesh", note="Coached operator on data policy.")
    assert resolved is not None
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolved_by"] == "lovekesh"
    assert temp_alert_manager.get_unresolved_count() == initial_unresolved
