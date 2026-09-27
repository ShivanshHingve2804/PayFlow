import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

class Account(Base):
    __tablename__ = 'accounts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal('0.00'))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

class Transaction(Base):
    __tablename__ = 'transactions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_account_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('accounts.id'), nullable=True)
    to_account_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('accounts.id'), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)  # TRANSFER, EXCHANGE, DEPOSIT
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='COMPLETED')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    
    from_account = relationship('Account', foreign_keys=[from_account_id])
    to_account = relationship('Account', foreign_keys=[to_account_id])

class ExchangeRate(Base):
    __tablename__ = 'exchange_rates'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    
    __table_args__ = (UniqueConstraint('from_currency', 'to_currency', name='uq_currency_pair'),)
