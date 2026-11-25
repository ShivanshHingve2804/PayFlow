"""ISO 4217 currency definitions, minor-unit precision guards, and FX base matrix."""

from decimal import ROUND_HALF_UP, Decimal

from app.exceptions import InvalidOperationError

CURRENCY_DECIMALS: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "INR": 2,
    "JPY": 0,
    "AUD": 2,
    "CAD": 2,
    "CHF": 2,
}

SUPPORTED_CURRENCIES: set[str] = set(CURRENCY_DECIMALS.keys())

# Reference rates relative to 1.00 USD for complete 8-currency (56-pair) cross-rates.
USD_BASE_RATES: dict[str, Decimal] = {
    "USD": Decimal("1.000000"),
    "EUR": Decimal("0.920000"),
    "GBP": Decimal("0.790000"),
    "INR": Decimal("83.500000"),
    "JPY": Decimal("149.500000"),
    "AUD": Decimal("1.530000"),
    "CAD": Decimal("1.380000"),
    "CHF": Decimal("0.880000"),
}


def currency_step(currency: str) -> Decimal:
    """Return smallest monetary increment (`1` for JPY, `0.01` for 2-decimal currencies)."""
    decimals = CURRENCY_DECIMALS.get(currency)
    if decimals is None:
        raise InvalidOperationError(f"Unsupported currency: {currency}")
    return Decimal("1") if decimals == 0 else Decimal("1").scaleb(-decimals)


def validate_and_quantize_input(amount: Decimal, currency: str) -> Decimal:
    """Reject inputs with excess sub-unit precision and normalize to currency minor unit."""
    step = currency_step(currency)
    quantized = amount.quantize(step, rounding=ROUND_HALF_UP)
    if amount != quantized:
        decimals = CURRENCY_DECIMALS[currency]
        raise InvalidOperationError(
            f"Amount {amount} exceeds {decimals} decimal places allowed for {currency}"
        )
    return quantized.quantize(Decimal("0.01"))


def quantize_converted(amount: Decimal, target_currency: str) -> Decimal:
    """Round converted FX proceeds cleanly to the target currency minor unit."""
    step = currency_step(target_currency)
    return amount.quantize(step, rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))
