"""Daily financial ledger and outbox reconciliation engine."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Account, OutboxEvent, ReconciliationReport, Transaction


class ReconciliationService:
    """Recomputes expected balances from immutable ledger records and audits outbox state."""

    @staticmethod
    def run_daily_reconciliation(
        db: Session, *, report_date: str | None = None
    ) -> ReconciliationReport:
        target_date = report_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        accounts = db.query(Account).all()
        tx_count = db.query(func.count(Transaction.id)).scalar() or 0
        outbox_pending = (
            db.query(func.count(OutboxEvent.id)).filter(OutboxEvent.status == "PENDING").scalar()
            or 0
        )

        expected: dict[str, Decimal] = {acc.id: Decimal(acc.initial_balance) for acc in accounts}

        transactions = db.query(Transaction).filter(Transaction.status == "COMPLETED").all()
        for tx in transactions:
            if tx.transaction_type == "DEPOSIT":
                if tx.to_account_id in expected:
                    expected[tx.to_account_id] += Decimal(tx.amount)
            elif tx.transaction_type == "TRANSFER":
                if tx.from_account_id in expected:
                    expected[tx.from_account_id] -= Decimal(tx.amount)
                if tx.to_account_id in expected:
                    expected[tx.to_account_id] += Decimal(tx.amount)
            elif tx.transaction_type == "EXCHANGE":
                if tx.from_account_id in expected:
                    expected[tx.from_account_id] -= Decimal(tx.amount)
                if tx.to_account_id in expected and tx.target_amount is not None:
                    expected[tx.to_account_id] += Decimal(tx.target_amount)

        discrepancies: list[dict[str, str]] = []
        for acc in accounts:
            exp_bal = expected[acc.id].quantize(Decimal("0.01"))
            actual_bal = Decimal(acc.balance).quantize(Decimal("0.01"))
            if exp_bal != actual_bal:
                discrepancies.append(
                    {
                        "account_id": acc.id,
                        "currency": acc.currency,
                        "expected_balance": str(exp_bal),
                        "actual_balance": str(actual_bal),
                        "delta": str(actual_bal - exp_bal),
                    }
                )

        status = "PASSED" if not discrepancies else "DISCREPANCY"
        existing = (
            db.query(ReconciliationReport)
            .filter(ReconciliationReport.report_date == target_date)
            .first()
        )
        if existing is not None:
            existing.accounts_checked = len(accounts)
            existing.transactions_checked = int(tx_count)
            existing.discrepancies_found = len(discrepancies)
            existing.outbox_pending = int(outbox_pending)
            existing.status = status
            existing.details_json = json.dumps(discrepancies)
            db.commit()
            db.refresh(existing)
            return existing

        report = ReconciliationReport(
            id=str(uuid.uuid4()),
            report_date=target_date,
            accounts_checked=len(accounts),
            transactions_checked=int(tx_count),
            discrepancies_found=len(discrepancies),
            outbox_pending=int(outbox_pending),
            status=status,
            details_json=json.dumps(discrepancies),
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def list_reports(db: Session, *, limit: int = 30) -> list[ReconciliationReport]:
        return (
            db.query(ReconciliationReport)
            .order_by(ReconciliationReport.report_date.desc())
            .limit(limit)
            .all()
        )
