"""Parametrized test runner — discovers JSON test cases and executes them."""

from __future__ import annotations

import json5
import re
from pathlib import Path
from typing import Any

import pytest

from simulation.factory import Factory
from simulation.items.item import Item
from simulation.items.inventory import Inventory
from simulation._id_gen import IDGen
from simulation.units.logistics_units.belt.splitter import Splitter
from simulation.units.logistics_units.belt.converger import Converger
from simulation.units.logistics_units.belt.conveyor import Conveyor
from simulation.units.depot_access.protocol_stash import ProtocolStash

from tests.mocks import MockSink, MockSource, MockDownstream
from tests.assertion_engine import run_assertions


_CLASS_MAP: dict[str, type] = {
    "Splitter": Splitter,
    "Converger": Converger,
    "Conveyor": Conveyor,
    "ProtocolStash": ProtocolStash,
    "MockSink": MockSink,
    "MockSource": MockSource,
    "MockDownstream": MockDownstream,
}

_TESTS_ROOT = Path(__file__).parent


def _discover_cases() -> list[tuple[str, str, dict]]:
    """Discover all JSON test cases with assertions."""
    cases: list[tuple[str, str, dict]] = []
    for json_path in sorted(_TESTS_ROOT.rglob("test_*.jsonc")):
        rel = json_path.relative_to(_TESTS_ROOT).as_posix()
        try:
            data = json5.loads(json_path.read_text("utf-8"))
        except ValueError:
            continue
        for key, cfg in data.items():
            if "assertions" not in cfg:
                continue
            cases.append((rel, key, cfg))
    return cases


def _case_id(item: tuple[str, str, dict]) -> str:
    return f"{item[0]}::{item[1]}"


_ALL_CASES = _discover_cases()


def _resolve_observe_target(factory: Factory, target_cfg: dict) -> Any:
    """Resolve the component to observe from a target config."""
    comp_ref = target_cfg["component"]
    m = re.fullmatch(r"(\w+):(\d+)", comp_ref)
    assert m, f"Bad component ref: {comp_ref}"
    class_name, idx = m.group(1), int(m.group(2))

    cls = _CLASS_MAP[class_name]
    matches = [c for c in factory.graph.components if isinstance(c, cls)]
    comp = matches[idx]

    if "follow" in target_cfg:
        follow = target_cfg["follow"]
        parts = follow.split(".")
        direction = parts[0]
        target_cls_name = parts[1]
        target_cls = _CLASS_MAP[target_cls_name]

        if direction == "downstream":
            for d in comp.downstreams:
                if isinstance(d, target_cls):
                    comp = d
                    break
            else:
                raise AssertionError(f"No {target_cls_name} downstream of {comp}")
        elif direction == "upstream":
            for u in comp.upstreams:
                if isinstance(u, target_cls):
                    comp = u
                    break
            else:
                raise AssertionError(f"No {target_cls_name} upstream of {comp}")

    return comp


def _eval_expr(comp: Any, expr: str) -> bool:
    """Evaluate a simple expression against a component."""
    ns: dict[str, Any] = {"self": comp, "None": None, "True": True, "False": False}
    for attr in dir(comp):
        if not attr.startswith("__"):
            try:
                ns[attr] = getattr(comp, attr)
            except Exception:
                pass
    return bool(eval(expr, {"__builtins__": {}}, ns))


def _run_integration(cfg: dict) -> None:
    """Run integration mode test."""
    f = Factory(cfg)
    ticks = cfg.get("ticks", 0)
    if ticks:
        f.run(ticks)
    run_assertions(cfg["assertions"], factory=f)


def _run_temporal(cfg: dict) -> None:
    """Run temporal mode test with observation window."""
    f = Factory(cfg)
    observe_cfg = cfg["observe"]
    warmup = observe_cfg["warmup"]
    window = observe_cfg["window"]
    targets_cfg = observe_cfg["targets"]

    resolved_targets: dict[str, Any] = {}
    for name, tcfg in targets_cfg.items():
        resolved_targets[name] = (_resolve_observe_target(f, tcfg), tcfg["expr"])

    for _ in range(warmup):
        f.tick()

    observations: dict[str, list[bool]] = {name: [] for name in targets_cfg}
    for _ in range(window):
        f.tick()
        for name, (comp, expr) in resolved_targets.items():
            observations[name].append(_eval_expr(comp, expr))

    run_assertions(cfg["assertions"], factory=f, observations=observations)


def _resolve_factory_ref(factory: Factory, ref: str) -> Any:
    """Resolve a 'ClassName:Index' reference to a factory component."""
    m = re.fullmatch(r"(\w+):(\d+)", ref)
    assert m, f"Bad factory ref: {ref}"
    class_name, idx = m.group(1), int(m.group(2))
    cls = _CLASS_MAP[class_name]
    matches = [c for c in factory.graph.components if isinstance(c, cls)]
    return matches[idx]


def _resolve_hybrid_target(factory: Factory, target: str) -> tuple[Any, str]:
    """Resolve 'ClassName:Index.attr' → (component, attr_name)."""
    m = re.fullmatch(r"(\w+:\d+)\.(\w+)", target)
    assert m, f"Bad hybrid target: {target}"
    comp = _resolve_factory_ref(factory, m.group(1))
    return comp, m.group(2)


def _run_hybrid(cfg: dict) -> None:
    """Run hybrid mode: build Factory, optionally tick, execute actions, assert."""
    f = Factory(cfg)
    ticks = cfg.get("ticks", 0)
    if ticks:
        f.run(ticks)

    id_gen = IDGen(1000)
    actions = cfg.get("actions", [])
    _execute_hybrid_actions(actions, f, id_gen)

    run_assertions(cfg["assertions"], factory=f)


def _execute_hybrid_actions(actions: list[dict], factory: Factory, id_gen: IDGen) -> None:
    """Execute actions that reference factory components by ClassName:Index."""
    for action in actions:
        if "repeat" in action:
            for _ in range(action["repeat"]):
                _execute_hybrid_actions(action["steps"], factory, id_gen)
        elif "set" in action:
            target = action["set"]
            comp, attr = _resolve_hybrid_target(factory, target)
            if "item" in action:
                value: Any = Item(id_gen.next(), action["item"])
            elif "value" in action:
                value = action["value"]
            else:
                value = None
            setattr(comp, attr, value)
        elif "call" in action:
            target = action["call"]
            comp, method_name = _resolve_hybrid_target(factory, target)
            method = getattr(comp, method_name)
            if "item" in action:
                method(Item(id_gen.next(), action["item"]))
            elif "ref" in action:
                ref_comp = _resolve_factory_ref(factory, action["ref"])
                method(ref_comp)
            else:
                method()
        elif "push_inv" in action:
            target = action["push_inv"]
            m = re.fullmatch(r"(\w+:\d+)\.(.+)", target)
            assert m, f"Bad push_inv target: {target}"
            comp = _resolve_factory_ref(factory, m.group(1))
            inv_obj = getattr(comp, m.group(2))
            item_type = action["item"]
            count = action.get("count", 1)
            for _ in range(count):
                inv_obj.push(Item(id_gen.next(), item_type))


def _create_unit_instance(inst_cfg: dict, id_gen: IDGen) -> Any:
    """Create a component instance for unit mode."""
    cls = _CLASS_MAP[inst_cfg["class"]]
    comp_id = inst_cfg["id"]
    args = inst_cfg.get("args", {})

    if cls is ProtocolStash:
        inv_size = args.get("inventory_size", 6)
        inv = Inventory(inv_size, id_gen)
        return cls(comp_id, id_gen=id_gen, inventory=inv)
    elif cls is MockDownstream:
        return cls(comp_id)
    elif cls is Conveyor:
        length = args.get("length", 4)
        return cls(comp_id, length=length)
    else:
        return cls(comp_id)


def _run_unit(cfg: dict) -> None:
    """Run unit mode test."""
    setup = cfg["setup"]
    id_gen = IDGen()

    instances: dict[int, Any] = {}
    for inst_cfg in setup["instances"]:
        inst = _create_unit_instance(inst_cfg, id_gen)
        instances[inst_cfg["id"]] = inst

    wiring = setup.get("wiring", {})
    for wire_target, wire_value in wiring.items():
        m = re.fullmatch(r"(\d+)\.(\w+)", wire_target)
        assert m, f"Bad wiring target: {wire_target}"
        inst_id = int(m.group(1))
        attr_name = m.group(2)
        resolved = [instances[ref_id] for ref_id in wire_value]
        setattr(instances[inst_id], attr_name, resolved)

    for inst_id in setup.get("finalize", []):
        instances[inst_id].finalize()

    overrides = setup.get("overrides", {})
    for override_target, override_value in overrides.items():
        m = re.fullmatch(r"(\d+)\.(\w+)", override_target)
        assert m, f"Bad override target: {override_target}"
        inst_id = int(m.group(1))
        attr_name = m.group(2)
        setattr(instances[inst_id], attr_name, lambda v=override_value: v)

    actions = cfg.get("actions", [])
    _execute_actions(actions, instances, id_gen)

    run_assertions(cfg["assertions"], instances=instances)


def _execute_actions(actions: list[dict], instances: dict[int, Any], id_gen: IDGen) -> None:
    """Execute a list of action dicts."""
    for action in actions:
        if "repeat" in action:
            count = action["repeat"]
            steps = action["steps"]
            for _ in range(count):
                _execute_actions(steps, instances, id_gen)
        elif "set" in action:
            _execute_set(action, instances, id_gen)
        elif "call" in action:
            _execute_call(action, instances, id_gen)


def _execute_set(action: dict, instances: dict[int, Any], id_gen: IDGen) -> None:
    """Execute a 'set' action."""
    target = action["set"]
    m = re.fullmatch(r"(\d+)\.(\w+)", target)
    assert m, f"Bad set target: {target}"
    inst_id = int(m.group(1))
    attr_name = m.group(2)

    if "item" in action:
        value: Any = Item(id_gen.next(), action["item"])
    elif "refs" in action:
        value = [instances[ref_id] for ref_id in action["refs"]]
    elif "value" in action:
        value = action["value"]
    else:
        value = None

    setattr(instances[inst_id], attr_name, value)


def _execute_call(action: dict, instances: dict[int, Any], id_gen: IDGen) -> None:
    """Execute a 'call' action."""
    target = action["call"]
    m = re.fullmatch(r"(\d+)\.(\w+)", target)
    assert m, f"Bad call target: {target}"
    inst_id = int(m.group(1))
    method_name = m.group(2)

    method = getattr(instances[inst_id], method_name)

    if "item" in action:
        method(Item(id_gen.next(), action["item"]))
    else:
        method()


@pytest.mark.parametrize("case", _ALL_CASES, ids=[_case_id(c) for c in _ALL_CASES])
def test_case(case: tuple[str, str, dict]) -> None:
    """Execute a single JSON-defined test case."""
    _, _, cfg = case
    mode = cfg.get("mode", "integration")
    match mode:
        case "integration":
            _run_integration(cfg)
        case "temporal":
            _run_temporal(cfg)
        case "unit":
            _run_unit(cfg)
        case "hybrid":
            _run_hybrid(cfg)
        case _:
            raise ValueError(f"Unknown test mode: {mode!r}")
