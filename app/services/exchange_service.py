import uuid
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import Account, Transaction, ExchangeRate
from app.schemas import ExchangeRequest, ExchangeRateResponse
from app.exceptions import (ExchangeRateNotFoundError, InsufficientFundsError,
                            InvalidOperationError)
from app.services.account_service import AccountService

class ExchangeService:
    @staticmethod
    def seed_default_rates(db: Session) -> None:
        """Seed default exchange rates."""
        if db.query(ExchangeRate).count() > 0:
            return

        rates = {
            ('USD', 'EUR'): Decimal('0.92'),
            ('USD', 'GBP'): Decimal('0.79'),
            ('USD', 'INR'): Decimal('83.50'),
            ('USD', 'JPY'): Decimal('149.50'),
            ('EUR', 'GBP'): Decimal('0.86'),
            ('EUR', 'INR'): Decimal('90.76'),
            ('GBP', 'INR'): Decimal('105.63')
        }

        for (from_curr, to_curr), rate in rates.items():
            db.add(ExchangeRate(id=str(uuid.uuid4()), from_currency=from_curr, to_currency=to_curr, rate=rate))
            db.add(ExchangeRate(id=str(uuid.uuid4()), from_currency=to_curr, to_currency=from_curr, rate=Decimal('1.0') / rate))
        
        db.commit()

    @staticmethod
    def get_rates(db: Session) -> list[ExchangeRateResponse]:
        """Get all exchange rates."""
        rates = db.query(ExchangeRate).all()
        return [ExchangeRateResponse(
            from_currency=r.from_currency,
            to_currency=r.to_currency,
            rate=r.rate
        ) for r in rates]

    @staticmethod
    def get_rate(db: Session, from_currency: str, to_currency: str) -> Decimal:
        """Get exchange rate for a specific pair."""
        if from_currency == to_currency:
            return Decimal('1.0')
        
        rate_obj = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency
        ).first()
        
        if not rate_obj:
            raise ExchangeRateNotFoundError(f"Exchange rate from {from_currency} to {to_currency} not found")
        
        return rate_obj.rate

    @staticmethod
    def create_exchange(db: Session, data: ExchangeRequest) -> Transaction:
        """Create an exchange transaction."""
        if data.idempotency_key:
            existing_tx = db.query(Transaction).filter(
                Transaction.idempotency_key == data.idempotency_key
            ).first()
            if existing_tx:
                return existing_tx

        from_account = AccountService.get_account(db, data.from_account_id)
        to_account = AccountService.get_account(db, data.to_account_id)

        if from_account.currency == to_account.currency:
            raise InvalidOperationError('Use /transfers for same-currency transfers')

        rate = ExchangeService.get_rate(db, from_account.currency, to_account.currency)

        sorted_ids = sorted([data.from_account_id, data.to_account_id])
        for aid in sorted_ids:
            try:
                db.execute(select(Account).where(Account.id == aid).with_for_update())
            except Exception:
                db.expire_all()

        # Re-fetch after locking to get latest balances
        db.refresh(from_account)
        db.refresh(to_account)

        converted_amount = round(data.amount * rate, 2)

        if from_account.balance < data.amount:
            raise InsufficientFundsError("Insufficient funds for exchange")

        from_account.balance -= data.amount
        to_account.balance += converted_amount

        transaction = Transaction(
            id=str(uuid.uuid4()),
            from_account_id=data.from_account_id,
            to_account_id=data.to_account_id,
            amount=data.amount,
            currency=from_account.currency,
            transaction_type='EXCHANGE',
            idempotency_key=data.idempotency_key,
            status='COMPLETED'
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        return transaction
