"""PayFlow — Fintech Payment API application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import get_db, init_db
from app.exceptions import (
    PayFlowError, AccountNotFoundError, InsufficientFundsError,
    CurrencyMismatchError, DuplicateTransactionError,
    InvalidOperationError, ExchangeRateNotFoundError,
)
from app.routes import accounts, transfers, exchange
from app.services.exchange_service import ExchangeService


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup/shutdown lifecycle for the application."""
    # Startup: create tables and seed exchange rates
    init_db()
    db = next(get_db())
    try:
        ExchangeService.seed_default_rates(db)
    finally:
        db.close()
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="PayFlow",
    description="Production-grade fintech payment API with ACID transfers, "
                "currency exchange, and idempotent transactions.",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Exception Handlers ──────────────────────────────────────────────────────

@app.exception_handler(AccountNotFoundError)
async def account_not_found_handler(request: Request, exc: AccountNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ExchangeRateNotFoundError)
async def exchange_rate_not_found_handler(request: Request, exc: ExchangeRateNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InsufficientFundsError)
async def insufficient_funds_handler(request: Request, exc: InsufficientFundsError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(CurrencyMismatchError)
async def currency_mismatch_handler(request: Request, exc: CurrencyMismatchError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(InvalidOperationError)
async def invalid_operation_handler(request: Request, exc: InvalidOperationError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(DuplicateTransactionError)
async def duplicate_transaction_handler(request: Request, exc: DuplicateTransactionError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(PayFlowError)
async def generic_payflow_error_handler(request: Request, exc: PayFlowError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ── Routers ──────────────────────────────────────────────────────────────────

app.include_router(accounts.router)
app.include_router(transfers.router)
app.include_router(exchange.router)


# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Health check endpoint."""
    return {"name": "PayFlow", "version": "0.1.0", "status": "healthy"}
