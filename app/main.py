"""PayFlow — Fintech Payment API application entry point."""

import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.exceptions import (
    AccountNotFoundError,
    CurrencyMismatchError,
    DuplicateTransactionError,
    ExchangeRateNotFoundError,
    InsufficientFundsError,
    InvalidOperationError,
    PayFlowError,
    TransactionNotFoundError,
)
from app.routes import accounts, exchange, reconciliation, transfers
from app.services.exchange_service import ExchangeService


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle: ensure schema exists (dev/SQLite) and seed 8-currency FX rates."""
    init_db()
    db = next(get_db())
    try:
        ExchangeService.seed_default_rates(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="PayFlow",
    description=(
        "ACID multi-currency fintech API with ordered row locking, idempotency "
        "fingerprinting, transactional Kafka outbox streaming, and daily reconciliation."
    ),
    version="0.2.0",
    lifespan=lifespan,
)


# ── Exception Handlers ──────────────────────────────────────────────────────


@app.exception_handler(AccountNotFoundError)
async def account_not_found_handler(_request: Request, exc: AccountNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(TransactionNotFoundError)
async def transaction_not_found_handler(
    _request: Request, exc: TransactionNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ExchangeRateNotFoundError)
async def exchange_rate_not_found_handler(
    _request: Request, exc: ExchangeRateNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InsufficientFundsError)
async def insufficient_funds_handler(
    _request: Request, exc: InsufficientFundsError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(CurrencyMismatchError)
async def currency_mismatch_handler(_request: Request, exc: CurrencyMismatchError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(InvalidOperationError)
async def invalid_operation_handler(_request: Request, exc: InvalidOperationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(DuplicateTransactionError)
async def duplicate_transaction_handler(
    _request: Request, exc: DuplicateTransactionError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(PayFlowError)
async def generic_payflow_error_handler(_request: Request, exc: PayFlowError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ── Routers ─────────────────────────────────────────────────────────────────

app.include_router(accounts.router)
app.include_router(transfers.router)
app.include_router(exchange.router)
app.include_router(reconciliation.router)


# ── Dashboard & Health Check ────────────────────────────────────────────────


@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard() -> HTMLResponse:
    """Serve the interactive dashboard."""
    html_path = pathlib.Path(__file__).parent / "dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/", response_model=None)
def root(db: Session = Depends(get_db)) -> JSONResponse | dict[str, str]:
    """Readiness & health check verifying database connectivity."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "name": "PayFlow",
                "version": "0.2.0",
                "status": "unhealthy",
                "detail": str(exc),
            },
        )
    return {"name": "PayFlow", "version": "0.2.0", "status": "healthy", "database": "connected"}


@app.get("/health", response_model=None)
def health(db: Session = Depends(get_db)) -> JSONResponse | dict[str, str]:
    """Alias health check endpoint for container orchestration."""
    return root(db)
