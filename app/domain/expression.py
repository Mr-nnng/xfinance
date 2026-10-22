"""A small arithmetic DSL for custom indices.

Supported: numbers, series references, ``@name`` custom-index references,
``+ - * / ^``, parentheses, and ``abs/min/max``. No Python eval, no attribute
access, no names outside the resolver.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from .models import NumericSeries


class ExpressionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NumberNode:
    value: float


@dataclass(frozen=True, slots=True)
class RefNode:
    symbol: str
    custom: bool = False


@dataclass(frozen=True, slots=True)
class UnaryNode:
    op: str
    operand: Node


@dataclass(frozen=True, slots=True)
class BinaryNode:
    op: str
    left: Node
    right: Node


@dataclass(frozen=True, slots=True)
class CallNode:
    name: str
    args: tuple[Node, ...]


Node = NumberNode | RefNode | UnaryNode | BinaryNode | CallNode

_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<number>\d+(?:\.\d+)?|\.\d+)
      | (?P<at>@[^\s()+\-*/^,]+)
      | (?P<ident>[A-Za-z][A-Za-z0-9_]*)
      | (?P<op>[+\-*/^(),])
    )
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    text: str
    position: int


def tokenize(expression: str) -> list[Token]:
    tokens: list[Token] = []
    position = 0
    while position < len(expression):
        match = _TOKEN_RE.match(expression, position)
        if not match:
            if expression[position:].strip() == "":
                break
            raise ExpressionError(f"无法识别的字符：{expression[position]!r}")
        kind = match.lastgroup or ""
        text = match.group(kind)
        if kind == "op":
            kind = "op"
        tokens.append(Token(kind, text, match.start(kind)))
        position = match.end()
    tokens.append(Token("eof", "", len(expression)))
    return tokens


class _Parser:
    def __init__(self, expression: str) -> None:
        self.expression = expression
        self.tokens = tokenize(expression)
        self.index = 0

    def parse(self) -> Node:
        node = self._expression()
        if self._peek().kind != "eof":
            raise ExpressionError(f"多余的输入：{self._peek().text!r}")
        return node

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _take(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _accept(self, text: str) -> bool:
        if self._peek().text == text:
            self.index += 1
            return True
        return False

    def _expression(self) -> Node:
        node = self._term()
        while self._peek().text in {"+", "-"}:
            op = self._take().text
            node = BinaryNode(op, node, self._term())
        return node

    def _term(self) -> Node:
        node = self._unary()
        while self._peek().text in {"*", "/"}:
            op = self._take().text
            node = BinaryNode(op, node, self._unary())
        return node

    def _unary(self) -> Node:
        if self._peek().text in {"+", "-"}:
            op = self._take().text
            return UnaryNode(op, self._unary())
        return self._power()

    def _power(self) -> Node:
        node = self._primary()
        if self._accept("^"):
            return BinaryNode("^", node, self._unary())
        return node

    def _primary(self) -> Node:
        token = self._peek()
        if token.kind == "number":
            self._take()
            return NumberNode(float(token.text))
        if token.kind == "at":
            self._take()
            return RefNode(token.text[1:], custom=True)
        if token.kind == "ident":
            self._take()
            if self._accept("("):
                args: list[Node] = []
                if not self._accept(")"):
                    while True:
                        args.append(self._expression())
                        if self._accept(")"):
                            break
                        if not self._accept(","):
                            raise ExpressionError("函数参数之间需要逗号")
                return CallNode(token.text.lower(), tuple(args))
            return RefNode(token.text)
        if self._accept("("):
            node = self._expression()
            if not self._accept(")"):
                raise ExpressionError("括号不匹配")
            return node
        raise ExpressionError("表达式不完整")

def parse(expression: str) -> Node:
    text = expression.strip()
    if not text:
        raise ExpressionError("表达式不能为空")
    return _Parser(text).parse()


def references(node: Node) -> list[RefNode]:
    found: list[RefNode] = []
    _walk(node, found)
    return found


def _walk(node: Node, found: list[RefNode]) -> None:
    if isinstance(node, RefNode):
        found.append(node)
    elif isinstance(node, UnaryNode):
        _walk(node.operand, found)
    elif isinstance(node, BinaryNode):
        _walk(node.left, found)
        _walk(node.right, found)
    elif isinstance(node, CallNode):
        for arg in node.args:
            _walk(arg, found)


def validate(expression: str) -> list[RefNode]:
    node = parse(expression)
    for ref in references(node):
        if not ref.symbol:
            raise ExpressionError("引用不能为空")
    for call in _calls(node):
        if call.name not in {"abs", "min", "max"}:
            raise ExpressionError(f"不支持的函数：{call.name}")
        if call.name == "abs" and len(call.args) != 1:
            raise ExpressionError("abs 需要 1 个参数")
        if call.name in {"min", "max"} and len(call.args) < 2:
            raise ExpressionError(f"{call.name} 至少需要 2 个参数")
    return references(node)


def _calls(node: Node) -> Iterable[CallNode]:
    if isinstance(node, CallNode):
        yield node
        for arg in node.args:
            yield from _calls(arg)
    elif isinstance(node, UnaryNode):
        yield from _calls(node.operand)
    elif isinstance(node, BinaryNode):
        yield from _calls(node.left)
        yield from _calls(node.right)


Resolver = Callable[[str, bool], NumericSeries]


def evaluate(node: Node, resolve: Resolver) -> NumericSeries:
    refs = {(ref.symbol, ref.custom) for ref in references(node)}
    resolved: dict[tuple[str, bool], NumericSeries] = {}
    for ref in refs:
        resolved[ref] = resolve(*ref)
    dates, aligned = align_series(resolved)
    values = _eval(node, aligned, len(dates))
    output_dates: list[date] = []
    output_values: list[float] = []
    for day, value in zip(dates, values):
        if value is not None and math.isfinite(value):
            output_dates.append(day)
            output_values.append(value)
    return NumericSeries(tuple(output_dates), tuple(output_values))


def _eval(node: Node, env: Mapping[tuple[str, bool], list[float]], length: int) -> list[float | None]:
    if isinstance(node, NumberNode):
        return [node.value] * length
    if isinstance(node, RefNode):
        return list(env[(node.symbol, node.custom)])
    if isinstance(node, UnaryNode):
        operand = _eval(node.operand, env, length)
        return [(-value if value is not None else None) for value in operand]
    if isinstance(node, BinaryNode):
        left = _eval(node.left, env, length)
        right = _eval(node.right, env, length)
        return [_binary(node.op, a, b) for a, b in zip(left, right)]
    if isinstance(node, CallNode):
        args = [_eval(arg, env, length) for arg in node.args]
        return [_call(node.name, values) for values in zip(*args)]
    raise ExpressionError("未知节点")


def _binary(op: str, left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return None if right == 0 else left / right
    if op == "^":
        try:
            return left**right
        except (OverflowError, ValueError):
            return None
    return None


def _call(name: str, values: tuple[float | None, ...]) -> float | None:
    if any(value is None for value in values):
        return None
    numbers = [value for value in values if value is not None]
    if name == "abs":
        return abs(numbers[0])
    if name == "min":
        return min(numbers)
    if name == "max":
        return max(numbers)
    return None


def align_series(
    series: Mapping[object, NumericSeries],
) -> tuple[list[date], dict[object, list[float]]]:
    """Union of dates, forward-filled, truncated to shared coverage."""
    if not series:
        return [], {}
    starts = [value.dates[0] for value in series.values() if value.dates]
    ends = [value.dates[-1] for value in series.values() if value.dates]
    if not starts or not ends:
        return [], {}
    start = max(starts)
    end = min(ends)
    all_dates = sorted({day for value in series.values() for day in value.dates})
    dates = [day for day in all_dates if start <= day <= end]
    aligned: dict[object, list[float]] = {}
    for key, value in series.items():
        lookup = dict(zip(value.dates, value.values))
        filled: list[float] = []
        current: float | None = None
        for day in dates:
            if day in lookup:
                current = lookup[day]
            filled.append(current if current is not None else float("nan"))
        aligned[key] = filled
    return dates, aligned
