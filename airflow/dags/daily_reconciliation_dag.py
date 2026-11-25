"""Airflow daily reconciliation DAG verifying ledger conservation and outbox health."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.services.reconciliation_service import ReconciliationService


def execute_daily_reconciliation(report_date: str | None = None) -> dict[str, object]:
    """Run ledger reconciliation and raise on balance discrepancy."""
    db = SessionLocal()
    try:
        report = ReconciliationService.run_daily_reconciliation(db, report_date=report_date)
        summary = {
            "report_id": report.id,
            "report_date": report.report_date,
            "accounts_checked": report.accounts_checked,
            "transactions_checked": report.transactions_checked,
            "discrepancies_found": report.discrepancies_found,
            "outbox_pending": report.outbox_pending,
            "status": report.status,
        }
        if report.status != "PASSED":
            raise RuntimeError(
                f"Ledger reconciliation failed on {report.report_date}: {report.details_json}"
            )
        return summary
    finally:
        db.close()


try:
    from airflow.operators.python import PythonOperator  # type: ignore[import-not-found]

    from airflow import DAG  # type: ignore[import-not-found]

    with DAG(
        dag_id="payflow_daily_ledger_reconciliation",
        description="Daily ACID ledger conservation and outbox completeness audit",
        schedule="@daily",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        catchup=False,
        max_active_runs=1,
        default_args={
            "owner": "payflow",
            "retries": 2,
            "retry_delay": timedelta(minutes=5),
        },
        tags=["fintech", "reconciliation", "ledger"],
    ) as dag:
        reconcile_ledger = PythonOperator(
            task_id="reconcile_ledger_balances",
            python_callable=execute_daily_reconciliation,
        )
except ImportError:
    dag = None
    reconcile_ledger = None
