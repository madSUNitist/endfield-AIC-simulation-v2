"""Assertion engine — resolves target expressions and evaluates predicates."""

from __future__ import annotations

import collections
import itertools
import math
import re
from typing import Any, Sequence

from simulation._enums import ComponentType as CT
from simulation.factory import Factory
from simulation.units.base import Base


_EXPR_SCOPE: dict[str, Any] = {
    "math": math,
    "re": re,
    "itertools": itertools,
    "collections": collections,
}


_CT_MAP: dict[str, CT] = {m.name: m for m in CT}


def _resolve_attr_chain(obj: Any, chain: str) -> Any:
    """Resolve a dotted attribute chain with support for indexing, .len, and method calls."""
    parts = re.split(r"\.(?![^\[]*\])", chain)
    current = obj
    for part in parts:
        if part == "len":
            current = len(current)
        elif m := re.fullmatch(r"(.+)\(\)", part):
            method_name = m.group(1)
            if m2 := re.fullmatch(r"(.+)\[(-?\d+)\]", method_name):
                attr_name, idx = m2.group(1), int(m2.group(2))
                current = getattr(current, attr_name)[idx]()
            else:
                current = getattr(current, method_name)()
        elif m := re.fullmatch(r"(.+)\[(-?\d+)\]", part):
            attr_name, idx = m.group(1), int(m.group(2))
            current = getattr(current, attr_name)[idx]
        elif part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
            current = current[int(part)]
        else:
            current = getattr(current, part)
    return current


def _find_by_type(factory: Factory, ct_name: str) -> list[Base]:
    """Return all components whose ComponentType name equals *ct_name*."""
    ct = _CT_MAP[ct_name]
    return [c for c in factory.graph.components if c.component_type is ct]


def _find_by_class(factory: Factory, class_name: str, index: int) -> Base:
    """Return the *index*-th component that is an instance of *class_name*.

    Args:
        factory: The built factory whose components are searched.
        class_name: One of ``Splitter``/``Converger``/``Conveyor``/``ProtocolStash``.
        index: Zero-based position among matching instances.
    """
    from simulation.units.logistics_units.belt.splitter import Splitter
    from simulation.units.logistics_units.belt.converger import Converger
    from simulation.units.logistics_units.belt.conveyor import Conveyor
    from simulation.units.depot_access.protocol_stash import ProtocolStash

    class_map: dict[str, type] = {
        "Splitter": Splitter,
        "Converger": Converger,
        "Conveyor": Conveyor,
        "ProtocolStash": ProtocolStash,
    }
    cls = class_map[class_name]
    matches = [c for c in factory.graph.components if isinstance(c, cls)]
    return matches[index]


def resolve_target(
    target: str,
    *,
    factory: Factory | None = None,
    instances: dict[int, Any] | None = None,
    observations: dict[str, list[bool]] | None = None,
) -> Any:
    """Resolve a target expression string to a value."""

    if target.startswith("observe."):
        assert observations is not None
        rest = target[len("observe."):]
        if m := re.fullmatch(r"(.+)\[(-?\d+):\]", rest):
            name, start = m.group(1), int(m.group(2))
            return observations[name][start:]
        return observations[rest]

    if target.startswith("inventory."):
        assert factory is not None
        item_type = target[len("inventory."):]
        return factory.inv.count(item_type)

    if target == "graph.order.len":
        assert factory is not None
        return len(factory.graph.order)

    if m := re.fullmatch(r"components\[type=(.+?)\]\.len", target):
        assert factory is not None
        return len(_find_by_type(factory, m.group(1)))

    if m := re.fullmatch(r"components\[type=(.+?)\]\[(\d+)\]\.(.+)", target):
        assert factory is not None
        comps = _find_by_type(factory, m.group(1))
        idx = int(m.group(2))
        return _resolve_attr_chain(comps[idx], m.group(3))

    if m := re.fullmatch(r"components\[type=(.+?)\]\.any\.(.+)", target):
        assert factory is not None
        comps = _find_by_type(factory, m.group(1))
        attr = m.group(2)
        return [_resolve_attr_chain(c, attr) for c in comps]

    if m := re.fullmatch(r"components\[type=(.+?)\]\.all\.(.+)", target):
        assert factory is not None
        comps = _find_by_type(factory, m.group(1))
        attr = m.group(2)
        return [_resolve_attr_chain(c, attr) for c in comps]

    if m := re.fullmatch(r"components\[type=(.+?)\]\.count_where\.(.+)", target):
        assert factory is not None
        comps = _find_by_type(factory, m.group(1))
        attr = m.group(2)
        return [_resolve_attr_chain(c, attr) for c in comps]

    if m := re.fullmatch(r"(\w+):(\d+)\.(.+)", target):
        assert factory is not None
        class_name, idx_str, attr_chain = m.group(1), m.group(2), m.group(3)
        comp = _find_by_class(factory, class_name, int(idx_str))
        return _resolve_attr_chain(comp, attr_chain)

    if instances is not None:
        if m := re.fullmatch(r"(\d+)\.(.+)", target):
            inst_id = int(m.group(1))
            attr_chain = m.group(2)
            return _resolve_attr_chain(instances[inst_id], attr_chain)

    raise ValueError(f"Cannot resolve target: {target!r}")


def apply_op(value: Any, op: str, expected: Any = None, *, min_matches: int | None = None) -> bool:
    """Apply an operator to a resolved value."""
    match op:
        case "==":
            return value == expected
        case "!=":
            return value != expected
        case "<":
            return value < expected
        case ">":
            return value > expected
        case "<=":
            return value <= expected
        case ">=":
            return value >= expected
        case "in":
            return list(value) in [list(v) for v in expected] if isinstance(value, list) else value in expected
        case "all_true":
            return all(value)
        case "any_true":
            return any(value)
        case "is_none":
            return value is None
        case "not_none":
            return value is not None
        case "between":
            lo, hi = expected
            return lo < value < hi
        case "between_inclusive":
            lo, hi = expected
            return lo <= value <= hi
        case "expr":
            scope = {**_EXPR_SCOPE, "_": value}
            return bool(eval(expected, scope))
        case _:
            raise ValueError(f"Unknown operator: {op!r}")


def evaluate_assertion(
    assertion: dict,
    *,
    factory: Factory | None = None,
    instances: dict[int, Any] | None = None,
    observations: dict[str, list[bool]] | None = None,
) -> tuple[bool, str]:
    """Evaluate a single assertion dict. Returns (passed, message)."""
    if "expr" in assertion:
        expr_str = assertion["expr"]
        def _resolve(t: str) -> Any:
            return resolve_target(t, factory=factory, instances=instances, observations=observations)
        scope = {**_EXPR_SCOPE, "factory": factory, "instances": instances, "observations": observations, "resolve": _resolve}
        result = bool(eval(expr_str, scope))
        return result, f"expr {expr_str!r} → {result}"

    target_expr = assertion["target"]
    op = assertion["op"]
    expected = assertion.get("value")
    min_matches = assertion.get("min_matches")

    value = resolve_target(
        target_expr,
        factory=factory,
        instances=instances,
        observations=observations,
    )

    if op in ("any_true", "all_true") and min_matches is not None:
        pass

    if min_matches is not None and isinstance(value, list):
        count = sum(1 for v in value if apply_op(v, op, expected))
        passed = count >= min_matches
        msg = f"{target_expr}: {count} matches (need >= {min_matches})"
    elif op in ("any_true",) and isinstance(value, list) and not isinstance(value[0], bool):
        passed = any(apply_op(v, ">" if expected is not None else "!=", expected if expected is not None else None) for v in value)
        msg = f"{target_expr}: any satisfies op"
    elif op == "expr":
        passed = apply_op(value, op, expected)
        msg = f"{target_expr} | expr {expected!r} → {passed}"
    else:
        passed = apply_op(value, op, expected)
        msg = f"{target_expr} {op} {expected!r} → got {value!r}"

    return passed, msg


def run_assertions(
    assertions: list[dict],
    *,
    factory: Factory | None = None,
    instances: dict[int, Any] | None = None,
    observations: dict[str, list[bool]] | None = None,
) -> None:
    """Run all assertions; raise AssertionError on first failure."""
    for a in assertions:
        passed, msg = evaluate_assertion(
            a,
            factory=factory,
            instances=instances,
            observations=observations,
        )
        assert passed, msg
