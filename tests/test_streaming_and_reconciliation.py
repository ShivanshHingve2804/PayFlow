"""Tests for transactional outbox, Kafka deduplicating consumer, and daily reconciliation."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

from fastapi.testclient import TestClient

from airflow.dags.daily_reconciliation_dag import execute_daily_reconciliation
from app.models import Account, OutboxEvent, ProcessedEvent
from app.services.reconciliation_service import ReconciliationService
from app.streaming.kafka_worker import AuditEventConsumer, OutboxRelay
from tests.conftest import TestingSessionLocal


class _InMemoryPublisher:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, dict]] = []

    def publish(self, topic: str, key: str, value: bytes) -> None:
        self.messages.append((topic, key, json.loads(value.decode("utf-8"))))


def test_outbox_relay_and_consumer_deduplication(client: TestClient, seed_exchange_rates) -> None:
    """Every ledger write emits an outbox row; relay publishes it; consumer deduplicates replays."""
    usd = client.post(
        "/api/v1/accounts/",
        json={"owner_name": "Alice", "currency": "USD", "initial_balance": 500.00},
    ).json()["id"]
    eur = client.post(
        "/api/v1/accounts/",
        json={"owner_name": "Bob", "currency": "EUR", "initial_balance": 0.00},
    ).json()["id"]

    assert (
        client.post(f"/api/v1/accounts/{usd}/deposit", json={"amount": 100.00}).status_code == 201
    )
    assert (
        client.post(
            "/api/v1/exchange/",
            json={"from_account_id": usd, "to_account_id": eur, "amount": 200.00},
        ).status_code
        == 201
    )

    stats_before = client.get("/api/v1/reconciliation/outbox").json()
    assert stats_before["outbox_pending"] == 2
    assert stats_before["outbox_published"] == 0

    publisher = _InMemoryPublisher()
    db = TestingSessionLocal()
    try:
        published = OutboxRelay.publish_pending_batch(db, publisher, topic="payflow.test")
        assert published == 2
        assert len(publisher.messages) == 2

        # Second relay poll finds zero pending rows
        assert OutboxRelay.publish_pending_batch(db, publisher, topic="payflow.test") == 0

        # Deliver each message twice to verify consumer deduplication
        for _, _, envelope in publisher.messages:
            assert AuditEventConsumer.process_event(db, envelope) is True
            assert AuditEventConsumer.process_event(db, envelope) is False

        assert db.query(ProcessedEvent).count() == 2
        assert db.query(OutboxEvent).filter(OutboxEvent.status == "PUBLISHED").count() == 2
    finally:
        db.close()

    stats_after = client.get("/api/v1/reconciliation/outbox").json()
    assert stats_after["outbox_pending"] == 0
    assert stats_after["outbox_published"] == 2
    assert stats_after["consumer_processed"] == 2


def test_daily_reconciliation_passes_and_detects_tampering(
    client: TestClient, seed_exchange_rates, monkeypatch
) -> None:
    """Reconciliation verifies conservation of balances and flags out-of-band drift."""
    a1 = client.post(
        "/api/v1/accounts/",
        json={"owner_name": "A1", "currency": "USD", "initial_balance": 1000.00},
    ).json()["id"]
    a2 = client.post(
        "/api/v1/accounts/",
        json={"owner_name": "A2", "currency": "USD", "initial_balance": 100.00},
    ).json()["id"]
    cad = client.post(
        "/api/v1/accounts/",
        json={"owner_name": "CAD", "currency": "CAD", "initial_balance": 0.00},
    ).json()["id"]

    client.post(f"/api/v1/accounts/{a1}/deposit", json={"amount": 250.00})
    client.post(
        "/api/v1/transfers/",
        json={"from_account_id": a1, "to_account_id": a2, "amount": 400.00},
    )
    client.post(
        "/api/v1/exchange/",
        json={"from_account_id": a2, "to_account_id": cad, "amount": 100.00},
    )

    resp = client.post("/api/v1/reconciliation/run?report_date=2026-11-25")
    assert resp.status_code == 201
    report = resp.json()
    assert report["status"] == "PASSED"
    assert report["accounts_checked"] == 3
    assert report["transactions_checked"] == 3
    assert report["discrepancies_found"] == 0

    reports = client.get("/api/v1/reconciliation/reports").json()
    assert len(reports) == 1

    # Verify Airflow DAG callable passes against clean ledger
    monkeypatch.setattr("airflow.dags.daily_reconciliation_dag.SessionLocal", TestingSessionLocal)
    dag_summary = execute_daily_reconciliation(report_date="2026-11-26")
    assert dag_summary["status"] == "PASSED"

    # Simulate out-of-band ledger corruption and assert reconciliation catches it
    db = TestingSessionLocal()
    try:
        corrupted = db.query(Account).filter(Account.id == a1).first()
        assert corrupted is not None
        corrupted.balance += Decimal("99.00")
        db.commit()

        failed_report = ReconciliationService.run_daily_reconciliation(
            db, report_date=f"2026-11-{uuid.uuid4().hex[:2]}"
        )
        assert failed_report.status == "DISCREPANCY"
        assert failed_report.discrepancies_found == 1
    finally:
        db.close()
