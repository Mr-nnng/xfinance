from __future__ import annotations

from datetime import date

import pytest

from app.domain.expression import (
    ExpressionError,
    align_series,
    evaluate,
    parse,
    references,
    validate,
)
from app.domain.models import NumericSeries

DAYS = [date(2026, 1, day) for day in range(1, 7)]


def series(values: list[float], start: int = 0) -> NumericSeries:
    dates = DAYS[start : start + len(values)]
    return NumericSeries(tuple(dates), tuple(values))


def resolver(mapping: dict[tuple[str, bool], NumericSeries]):
    def resolve(symbol: str, custom: bool) -> NumericSeries:
        return mapping[(symbol, custom)]

    return resolve


def test_parse_references_and_custom_names() -> None:
    node = parse("@金油比 + XAUUSD")
    refs = references(node)
    assert {(ref.symbol, ref.custom) for ref in refs} == {
        ("金油比", True),
        ("XAUUSD", False),
    }


def test_precedence_and_parentheses() -> None:
    data = {("X", False): series([1.0, 2.0])}
    plain = evaluate(parse("X + 2 * 3"), resolver(data))
    grouped = evaluate(parse("(X + 2) * 3"), resolver(data))
    assert plain.values == (7.0, 8.0)
    assert grouped.values == (9.0, 12.0)


def test_power_is_right_associative_and_unary_binds_outer() -> None:
    data = {("X", False): series([2.0])}
    assert evaluate(parse("X + 2 ^ 3 ^ 2"), resolver(data)).values == (514.0,)
    assert evaluate(parse("X ^ 3"), resolver(data)).values == (8.0,)
    assert evaluate(parse("-X ^ 2"), resolver(data)).values == (-4.0,)


def test_ratio_of_two_series() -> None:
    data = {
        ("XAUUSD", False): series([2000.0, 2100.0, 2200.0]),
        ("WTIUSD", False): series([100.0, 100.0, 110.0]),
    }
    result = evaluate(parse("XAUUSD / WTIUSD"), resolver(data))
    assert result.values == pytest.approx((20.0, 21.0, 20.0))


def test_custom_reference_resolution() -> None:
    data = {("金油比", True): series([20.0, 21.0])}
    result = evaluate(parse("@金油比 * 2"), resolver(data))
    assert result.values == (40.0, 42.0)


def test_division_by_zero_drops_point() -> None:
    data = {
        ("A", False): series([1.0, 2.0, 3.0]),
        ("B", False): series([1.0, 0.0, 3.0]),
    }
    result = evaluate(parse("A / B"), resolver(data))
    assert result.values == (1.0, 1.0)
    assert len(result.dates) == 2


def test_functions_abs_min_max() -> None:
    data = {
        ("A", False): series([-3.0, 4.0]),
        ("B", False): series([2.0, 5.0]),
    }
    assert evaluate(parse("abs(A)"), resolver(data)).values == (3.0, 4.0)
    assert evaluate(parse("min(A, B)"), resolver(data)).values == (-3.0, 4.0)
    assert evaluate(parse("max(A, B)"), resolver(data)).values == (2.0, 5.0)


def test_alignment_truncates_and_forward_fills() -> None:
    left = series([1.0, 2.0, 3.0, 4.0], start=0)
    right = NumericSeries(
        (date(2026, 1, 2), date(2026, 1, 4)),
        (10.0, 40.0),
    )
    dates, aligned = align_series({("L", False): left, ("R", False): right})
    assert dates == [date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4)]
    assert aligned[("R", False)] == [10.0, 10.0, 40.0]


@pytest.mark.parametrize(
    "expression",
    ["", "X +", "(X", "X Y", "X.__class__", "abs(X, Y)", "sum(X)"],
)
def test_invalid_expressions(expression: str) -> None:
    with pytest.raises(ExpressionError):
        validate(expression)


def test_validate_reports_supported_functions_only() -> None:
    validate("max(X, Y) + abs(Z)")
    with pytest.raises(ExpressionError):
        validate("round(X)")
