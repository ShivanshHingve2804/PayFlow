from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from datetime import datetime

class AccountCreate(BaseModel):
    owner_name: str = Field(min_length=1, max_length=255)
    currency: str = Field(min_length=3, max_length=3, pattern='^[A-Z]{3}$')
    initial_balance: Decimal = Field(default=Decimal('0.00'), ge=Decimal('0.00'))

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
    amount: Decimal = Field(gt=Decimal('0.00'))
    idempotency_key: str | None = None

class TransferRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: Decimal = Field(gt=Decimal('0.00'))
    idempotency_key: str | None = None

class TransferResponse(BaseModel):
    id: str
    from_account_id: str | None
    to_account_id: str | None
    amount: Decimal
    currency: str
    transaction_type: str
    idempotency_key: str | None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ExchangeRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: Decimal = Field(gt=Decimal('0.00'))
    idempotency_key: str | None = None

class ExchangeRateResponse(BaseModel):
    from_currency: str
    to_currency: str
    rate: Decimal

class ExchangeRatesListResponse(BaseModel):
    rates: list[ExchangeRateResponse]
