"""Tests for the stubbed payment/entitlement layer.

The charge path must stay dark: charge() and create_entitlement() refuse,
check_entitlement() is informational and never enforces. These tests pin
the gate so a future wiring can't silently slip past them.
"""

import pytest

from levi.demandpulse import payments


def test_no_processor_wired():
    assert payments.PAYMENT_PROCESSOR is None


def test_charge_refuses():
    with pytest.raises(payments.PaymentNotAuthorized):
        payments.charge("cust-1")


def test_charge_refusal_names_owner_gate():
    with pytest.raises(payments.PaymentNotAuthorized) as exc:
        payments.charge("cust-1", amount=6.0)
    assert "owner" in str(exc.value).lower()


def test_create_entitlement_refuses():
    with pytest.raises(payments.PaymentNotAuthorized):
        payments.create_entitlement("cust-1")


def test_check_entitlement_never_enforces():
    status = payments.check_entitlement("cust-1")
    assert status.customer_id == "cust-1"
    assert status.active is False
    assert status.enforced is False
    assert status.reason  # the reason is always on the record


def test_activation_checklist_names_five_decisions():
    checklist = payments.activation_checklist()
    assert len(checklist["owner_decisions_required"]) == 5
    assert checklist["status"].startswith("dark")
    assert checklist["processor"] is None


def test_gate_note_mentions_chauncey():
    assert "Chauncey" in payments.OWNER_GATE_NOTE
