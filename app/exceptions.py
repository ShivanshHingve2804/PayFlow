class PayFlowError(Exception):
    def __init__(self, message: str, detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(self.message)

class AccountNotFoundError(PayFlowError):
    def __init__(self, message: str = 'Account not found', detail: str = ""):
        super().__init__(message, detail)

class InsufficientFundsError(PayFlowError):
    def __init__(self, message: str = 'Insufficient funds', detail: str = ""):
        super().__init__(message, detail)

class CurrencyMismatchError(PayFlowError):
    def __init__(self, message: str = 'Currency mismatch between accounts', detail: str = ""):
        super().__init__(message, detail)

class DuplicateTransactionError(PayFlowError):
    def __init__(self, message: str = 'Duplicate transaction (idempotency key already used)', detail: str = ""):
        super().__init__(message, detail)

class InvalidOperationError(PayFlowError):
    def __init__(self, message: str = 'Invalid operation', detail: str = ""):
        super().__init__(message, detail)

class ExchangeRateNotFoundError(PayFlowError):
    def __init__(self, message: str = 'Exchange rate not found', detail: str = ""):
        super().__init__(message, detail)
