from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
DECIMAL_HUNDRED = Decimal("100")
METRIC_QUANT = Decimal("0.00000001")


def to_decimal(value: Any) -> Decimal | None:
    """
    Convert numeric-ish input to Decimal safely.
    Returns None for missing or invalid values.
    """
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def quantize_metric(value: Decimal | None) -> Decimal | None:
    """
    Normalize computed metric precision to 8 decimal places,
    matching the ComputedMetricSnapshot.metric_value field scale.
    """
    if value is None:
        return None
    return value.quantize(METRIC_QUANT, rounding=ROUND_HALF_UP)


def safe_div(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    """
    Safe division helper.
    Returns None if numerator/denominator is missing or denominator is zero.
    """
    if numerator is None or denominator is None or denominator == DECIMAL_ZERO:
        return None
    return numerator / denominator


def pct_change(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    """
    Percentage change as a decimal fraction.
    Example:
      current=120, previous=100 => 0.20
    """
    if current is None or previous is None or previous == DECIMAL_ZERO:
        return None
    return (current - previous) / abs(previous)


def average_two(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    """
    Average of two values if both are present.
    Falls back to whichever exists if only one exists.
    """
    if current is not None and previous is not None:
        return (current + previous) / Decimal("2")
    if current is not None:
        return current
    if previous is not None:
        return previous
    return None


def sum_present(*values: Decimal | None) -> Decimal | None:
    """
    Sum values that are present. Returns None if all are missing.
    """
    present = [v for v in values if v is not None]
    if not present:
        return None
    total = DECIMAL_ZERO
    for value in present:
        total += value
    return total


def abs_decimal(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return abs(value)


def flag(condition: bool) -> Decimal:
    """
    Store boolean signals as 1 or 0.
    """
    return DECIMAL_ONE if condition else DECIMAL_ZERO