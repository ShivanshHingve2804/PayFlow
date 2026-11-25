# PayFlow API Reference

All endpoints default to JSON over HTTP (`http://localhost:8000`). Interactive Swagger docs are served at `/docs` and the dark-themed ledger dashboard at `/dashboard`.

---

## Health & Dashboard

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Service readiness & live PostgreSQL connectivity probe (`SELECT 1`; `200` / `503`) |
| `GET` | `/health` | Container orchestration liveness/readiness alias |
| `GET` | `/dashboard` | Interactive multi-currency ledger & transaction dashboard |

---

## Accounts

| Method | Path | Query / Body | Notes |
|---|---|---|---|
| `GET` | `/api/v1/accounts/` | `?limit=100&offset=0` | Paginated account list (8 supported currencies) |
| `POST` | `/api/v1/accounts/` | `{"owner_name", "currency", "initial_balance"}` | Validates currency & minor-unit scale (`201`) |
| `GET` | `/api/v1/accounts/{account_id}` | — | Account details (`404` if missing) |
| `GET` | `/api/v1/accounts/{account_id}/balance` | — | Committed account balance |
| `POST` | `/api/v1/accounts/{account_id}/deposit` | `{"amount", "idempotency_key?"}` | Atomic credit + outbox emission (`409` on key/payload mismatch) |

---

## Transfers & Ledger

| Method | Path | Query / Body | Notes |
|---|---|---|---|
| `GET` | `/api/v1/transfers/` | `?limit=100&offset=0&transaction_type=TRANSFER` | Filter `TRANSFER`, `DEPOSIT`, `EXCHANGE`, or `ALL` |
| `POST` | `/api/v1/transfers/` | `{"from_account_id", "to_account_id", "amount", "idempotency_key?"}` | Same-currency ACID transfer with ordered row locks (`400` overdraft/mismatch, `409` idempotency conflict) |
| `GET` | `/api/v1/transfers/{transfer_id}` | — | Transaction lookup (`404` `TransactionNotFoundError`) |

---

## Multi-Currency Exchange

| Method | Path | Body | Notes |
|---|---|---|---|
| `GET` | `/api/v1/exchange/rates` | — | All 56 directed currency pairs (`USD`, `EUR`, `GBP`, `INR`, `JPY`, `AUD`, `CAD`, `CHF`) |
| `POST` | `/api/v1/exchange/` | `{"from_account_id", "to_account_id", "amount", "idempotency_key?"}` | Cross-currency conversion recording `target_amount`, `target_currency`, and `exchange_rate` |

---

## Reconciliation & Outbox Audit

| Method | Path | Query | Notes |
|---|---|---|---|
| `POST` | `/api/v1/reconciliation/run` | `?report_date=YYYY-MM-DD` | Recomputes ledger conservation & outbox backlog (`201`) |
| `GET` | `/api/v1/reconciliation/reports` | `?limit=30` | Recent daily reconciliation reports |
| `GET` | `/api/v1/reconciliation/outbox` | — | Live `outbox_pending`, `outbox_published`, and `consumer_processed` counts |
