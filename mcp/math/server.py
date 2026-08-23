from __future__ import annotations

import ast
import json
import math
import operator
import re
from typing import Any, Callable

import sympy as sp
from mcp.server.fastmcp import FastMCP
from pint import UnitRegistry


mcp = FastMCP("titan-math")
ureg = UnitRegistry(autoconvert_offset_to_baseunit=True)

_BINARY_OPERATORS: dict[type[ast.operator], Callable[..., Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[..., Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_CONSTANTS: dict[str, int | float | complex] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
}


def _safe_factorial(value: int) -> int:
    if value < 0 or value > 10000:
        raise ValueError("factorial input must be between 0 and 10000")
    return math.factorial(value)


def _safe_comb(n: int, k: int) -> int:
    if n < 0 or k < 0 or n > 100000 or k > n:
        raise ValueError("comb inputs are out of range")
    return math.comb(n, k)


def _safe_perm(n: int, k: int | None = None) -> int:
    if n < 0 or n > 100000 or (k is not None and (k < 0 or k > n)):
        raise ValueError("perm inputs are out of range")
    return math.perm(n, k) if k is not None else math.factorial(n)


def _safe_round(value: float, ndigits: int = 0) -> int | float:
    if abs(ndigits) > 1000:
        raise ValueError("ndigits is out of range")
    return round(value, ndigits)


_FUNCTIONS: dict[str, Callable[..., Any]] = {
    # Basic numeric helpers.
    "abs": abs,
    "min": min,
    "max": max,
    "sum": lambda *values: sum(values),
    "round": _safe_round,
    "ceil": math.ceil,
    "floor": math.floor,
    "trunc": math.trunc,
    "fabs": math.fabs,
    # Powers, roots, exponentials, and logarithms.
    "sqrt": math.sqrt,
    "cbrt": getattr(math, "cbrt", lambda value: math.copysign(abs(value) ** (1 / 3), value)),
    "pow": pow,
    "exp": math.exp,
    "expm1": math.expm1,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "log1p": math.log1p,
    # Trigonometry and angle conversion. Arguments are radians.
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "asinh": math.asinh,
    "acosh": math.acosh,
    "atanh": math.atanh,
    "hypot": math.hypot,
    "degrees": math.degrees,
    "radians": math.radians,
    "erf": math.erf,
    "erfc": math.erfc,
    "gamma": math.gamma,
    "lgamma": math.lgamma,
    "copysign": math.copysign,
    "frexp": math.frexp,
    "ldexp": math.ldexp,
    "nextafter": math.nextafter,
    "ulp": math.ulp,
    # Integer and combinatorics helpers.
    "factorial": _safe_factorial,
    "gcd": math.gcd,
    "lcm": math.lcm,
    "comb": _safe_comb,
    "perm": _safe_perm,
    # Comparisons and floating-point helpers.
    "isclose": math.isclose,
    "isfinite": math.isfinite,
    "isinf": math.isinf,
    "isnan": math.isnan,
}


def _check_result(value: Any) -> Any:
    if isinstance(value, complex):
        if not (math.isfinite(value.real) and math.isfinite(value.imag)):
            raise ValueError("result is not finite")
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, bool) or not math.isfinite(float(value)):
            raise ValueError("result is not finite")
        if abs(value) > 1e300:
            raise ValueError("result is too large")
        return value
    raise ValueError("result is not numeric")


def _number(expression: str) -> int | float | complex:
    if len(expression) > 2000:
        raise ValueError("expression is too long")
    tree = ast.parse(expression, mode="eval")

    def visit(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, complex)):
            if isinstance(node.value, bool):
                raise ValueError("booleans are not numbers")
            return node.value
        if isinstance(node, ast.Name) and node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            return _check_result(_BINARY_OPERATORS[type(node.op)](visit(node.left), visit(node.right)))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            return _check_result(_UNARY_OPERATORS[type(node.op)](visit(node.operand)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
            if node.keywords:
                raise ValueError("keyword arguments are not supported")
            values = [visit(argument) for argument in node.args]
            return _check_result(_FUNCTIONS[node.func.id](*values))
        raise ValueError("unsupported expression or function")

    return _check_result(visit(tree))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, default=str)


@mcp.tool()
def calculator(expression: str) -> str:
    """Evaluate safe scientific arithmetic with a whitelist of math functions."""
    try:
        result = _number(expression)
        return _json({"expression": expression, "result": result})
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        return _json({"error": str(exc), "expression": expression})


_SYMPY_NAMES = {
    "pi", "E", "I", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "sinh", "cosh", "tanh", "sqrt", "cbrt", "log", "log10", "log2", "exp",
    "Abs", "abs", "floor", "ceiling", "factorial", "Min", "Max",
}


@mcp.tool()
def solve_equation(equation: str, variable: str = "x") -> str:
    """Solve a safe algebraic equation such as 2*x+1=7 for x."""
    if not re.fullmatch(r"[A-Za-z_]\w{0,30}", variable):
        return _json({"error": "invalid variable name"})
    if len(equation) > 2000 or not re.fullmatch(r"[0-9A-Za-z_+\-*/^().=, \t]+", equation):
        return _json({"error": "equation contains unsupported characters"})
    names = set(re.findall(r"[A-Za-z_]\w*", equation))
    if any(name != variable and name not in _SYMPY_NAMES for name in names):
        return _json({"error": "equation contains an unsupported name"})
    try:
        symbol = sp.Symbol(variable)
        locals_map = {name: getattr(sp, name, None) for name in _SYMPY_NAMES}
        locals_map[variable] = symbol
        locals_map = {name: value for name, value in locals_map.items() if value is not None}
        parts = equation.replace("^", "**").split("=")
        if len(parts) == 1:
            solutions = sp.solve(sp.sympify(parts[0], locals=locals_map), symbol)
        elif len(parts) == 2:
            left = sp.sympify(parts[0], locals=locals_map)
            right = sp.sympify(parts[1], locals=locals_map)
            solutions = sp.solve(sp.Eq(left, right), symbol)
        else:
            raise ValueError("equation must contain at most one equals sign")
        return _json({"equation": equation, "variable": variable, "solutions": [str(x) for x in solutions]})
    except (TypeError, ValueError, SyntaxError, sp.SympifyError) as exc:
        return _json({"error": str(exc), "equation": equation})


@mcp.tool()
def unit_convert(value: float, from_unit: str, to_unit: str) -> str:
    """Convert a number between compatible physical units using Pint."""
    try:
        converted = (value * ureg(from_unit)).to(to_unit)
        return _json({"value": value, "from": from_unit, "to": to_unit, "result": converted.magnitude})
    except Exception as exc:  # Pint has several exception types across versions.
        return _json({"error": str(exc), "value": value, "from": from_unit, "to": to_unit})


if __name__ == "__main__":
    mcp.run(transport="stdio")
