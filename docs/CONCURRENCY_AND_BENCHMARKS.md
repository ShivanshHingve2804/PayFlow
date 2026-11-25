# PayFlow Concurrency & Verification Results

All results below were observed directly against the local Docker Compose stack (`PostgreSQL 16` + `Redpanda/Kafka` + `FastAPI` + `outbox-relay` + `audit-consumer`).

---

## 1. Automated Suite & Static Analysis

- **Lint & Format:** `ruff check .` (0 issues), `ruff format --check .` (33 files formatted)
- **Type Check:** `mypy app/` (0 issues across 21 source files)
- **Alembic Migrations:** `alembic upgrade head` (`0001_initial_schema`) applied cleanly on PostgreSQL 16
- **Test Suite:** `pytest -v --cov=app --cov-fail-under=85` → **43 / 43 passed in `13.76s` (`87.16%` coverage)**

---

## 2. Multi-Threaded PostgreSQL 16 Contention Suite (`tests/test_postgres_concurrency.py`)

Executed across 20 simultaneous worker threads with independent PostgreSQL sessions exercising real `SELECT ... FOR UPDATE`:

| Exercise | Scenario | Verified Outcome |
|---|---|---|
| **Overdraft race prevention** | 20 threads simultaneously transfer `$200.00` from a `$1,000.00` account | **Passed:** Exactly `5` transfers succeeded, `15` raised `InsufficientFundsError`, final balances `$0.00` / `$1,000.00` |
| **AB-BA deadlock prevention** | 20 concurrent threads racing `A -> B` (`$10.00`) vs `B -> A` (`$10.00`) | **Passed:** `20/20` completed with `0` deadlocks via sorted account-ID lock ordering; balances conserved (`$1,000.00` / `$1,000.00`) |
| **Idempotency storm** | 20 threads simultaneously deposit `$50.00` with the same `idempotency_key` | **Passed:** `1` unique transaction & `1` outbox event created, `19` replays returned identical ID (`0` `500`s); mismatched payload raised `DuplicateTransactionError` (`409`) |

---

## 3. Live 5-Container Stack & Kafka/Redpanda Pipeline (2026-11-25)

Running `docker compose up -d` (`db`, `redpanda`, `app`, `outbox-relay`, `audit-consumer`):

- **Health Probe:** `GET /health` → `200 OK` (`status=healthy`, `database=connected`)
- **8-Currency Minor-Unit Exchange:** `100.00 USD -> 14950.00 JPY` (`rate=149.500000`)
- **50 Sequential End-to-End HTTP Transfers (`POST /api/v1/transfers/` with PostgreSQL `FOR UPDATE` + Outbox write):**
  - Average: **`25.51 ms`**
  - `p50`: **`24.18 ms`**
  - `p95`: **`37.77 ms`**
  - Max: **`93.83 ms`**
- **Post-Commit Kafka/Redpanda Delivery (`GET /api/v1/reconciliation/outbox`):**
  - `outbox_pending`: **`0`**
  - `outbox_published`: **`52`**
  - `consumer_processed`: **`52`**
- **Daily Ledger Reconciliation (`POST /api/v1/reconciliation/run`):**
  - `accounts_checked=3`, `transactions_checked=52`, `discrepancies_found=0`, `status="PASSED"`
