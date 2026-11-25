"""Pydantic v2 request and response schemas for PayFlow."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _reject_blank_key(value: str | None) -> str | None:
    if value is not None and not value.strip():
        raise ValueError("idempotency_key must not be blank")
    return value.strip() if value is not None else None


class AccountCreate(BaseModel):
    owner_name: str = Field(min_length=1, max_length=255)
    currency: str = Field(min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    initial_balance: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))


class AccountResponse(BaseModel):
    id: str
    owner_name: str
    currency: str
    balance: Decimal
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BalanceResponse(BaseModel):
    account_id: str
    currency: str
    balance: Decimal


class DepositRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0.00"))
    idempotency_key: str | None = Field(default=None, max_length=255)

    @field_validator("idempotency_key")
    @classmethod
    def validate_key(cls, value: str | None) -> str | None:
        return _reject_blank_key(value)


class TransferRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: Decimal = Field(gt=Decimal("0.00"))
    idempotency_key: str | None = Field(default=None, max_length=255)

    @field_validator("idempotency_key")
    @classmethod
    def validate_key(cls, value: str | None) -> str | None:
        return _reject_blank_key(value)


class TransferResponse(BaseModel):
    id: str
    from_account_id: str | None
    to_account_id: str | None
    amount: Decimal
    currency: str
    target_amount: Decimal | None = None
    target_currency: str | None = None
    exchange_rate: Decimal | None = None
    transaction_type: str
    idempotency_key: str | None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ExchangeRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: Decimal = Field(gt=Decimal("0.00"))
    idempotency_key: str | None = Field(default=None, max_length=255)

    @field_validator("idempotency_key")
    @classmethod
    def validate_key(cls, value: str | None) -> str | None:
        return _reject_blank_key(value)


class ExchangeRateResponse(BaseModel):
    from_currency: str
    to_currency: str
    rate: Decimal


class ExchangeRatesListResponse(BaseModel):
    rates: list[ExchangeRateResponse]


class ReconciliationReportResponse(BaseModel):
    id: str
    report_date: str
    accounts_checked: int
    transactions_checked: int
    discrepancies_found: int
    outbox_pending: int
    status: str
    details_json: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
