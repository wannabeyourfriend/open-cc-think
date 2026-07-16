"""Deterministic local tools for the agentic research fixture."""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .models import Json


class ToolExecutionError(ValueError):
    pass


@dataclass(frozen=True)
class LocalTool:
    name: str
    description: str
    input_schema: Json
    handler: Callable[[Json], Any]

    @property
    def bedrock_spec(self) -> Json:
        return {
            "toolSpec": {
                "name": self.name,
                "description": self.description,
                "inputSchema": {"json": self.input_schema},
            }
        }


class ToolRegistry:
    def __init__(self, tools: List[LocalTool]):
        self._tools = {tool.name: tool for tool in tools}

    @property
    def tool_config(self) -> Json:
        return {"tools": [tool.bedrock_spec for tool in self._tools.values()]}

    def execute(self, name: str, arguments: Json) -> Any:
        if name not in self._tools:
            raise ToolExecutionError("unknown tool: %s" % name)
        return self._tools[name].handler(arguments)


_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Num):  # Python 3.9 compatibility
        return node.n
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise ToolExecutionError("exponent is outside the safe range")
        value = _BINARY[type(node.op)](left, right)
        if abs(value) > 1e15:
            raise ToolExecutionError("result is outside the safe range")
        return value
    raise ToolExecutionError("calculator accepts arithmetic expressions only")


def calculator(arguments: Json) -> Json:
    expression = str(arguments.get("expression", ""))
    if not expression or len(expression) > 200:
        raise ToolExecutionError("a short expression is required")
    tree = ast.parse(expression, mode="eval")
    return {"expression": expression, "value": _safe_eval(tree)}


CATALOG = {
    "SENSOR-A": {"sku": "SENSOR-A", "unit_price_usd": 129.50, "stock": 30},
    "CASE-R": {"sku": "CASE-R", "unit_price_usd": 47.25, "stock": 12},
}


def catalog_lookup(arguments: Json) -> Json:
    sku = str(arguments.get("sku", "")).upper()
    if sku not in CATALOG:
        return {"found": False, "sku": sku}
    return {"found": True, **CATALOG[sku]}


def policy_lookup(arguments: Json) -> Json:
    topic = str(arguments.get("topic", ""))
    if topic != "shipping_and_approval":
        return {"found": False, "topic": topic}
    return {
        "found": True,
        "topic": topic,
        "free_shipping_subtotal_usd": 1000.00,
        "standard_shipping_usd": 35.00,
        "manager_approval_above_usd": 1200.00,
        "rules": "Free shipping applies at subtotal >= 1000; manager approval is required only above 1200.",
    }


def procurement_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            LocalTool(
                "catalog_lookup",
                "Look up the authoritative unit price and stock for exactly one SKU.",
                {
                    "type": "object",
                    "properties": {"sku": {"type": "string"}},
                    "required": ["sku"],
                    "additionalProperties": False,
                },
                catalog_lookup,
            ),
            LocalTool(
                "calculator",
                "Evaluate an arithmetic expression. Use prices returned by catalog_lookup.",
                {
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"],
                    "additionalProperties": False,
                },
                calculator,
            ),
            LocalTool(
                "policy_lookup",
                "Retrieve the authoritative shipping and approval policy.",
                {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "enum": ["shipping_and_approval"]}
                    },
                    "required": ["topic"],
                    "additionalProperties": False,
                },
                policy_lookup,
            ),
        ]
    )

