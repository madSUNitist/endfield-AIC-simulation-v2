"""Test converger priority — A.json / B.json integration."""

import json
from pathlib import Path

from simulation.factory import Factory
from simulation._enums import ComponentType as CT

_CASES = Path(__file__).parent / "test_cases"


def _load(name: str) -> dict:
    """Load a JSON test case by filename from the test_cases directory."""
    with (_CASES / name).open(encoding="utf-8") as f:
        return json.load(f)


def _find(f: Factory, ctype):
    """Filter graph components by ComponentType from a Factory instance."""
    return [c for c in f.graph.components if c.component_type is ctype]


def test_blueprint_A_full_speed() -> None:
    """A: Converger upstreams = [splitter, copper_belt].
    Splitter has ONLY the converger as downstream, so it always
    delivers.  Copper is consumed only during warmup (before ore
    reaches the splitter); after warmup the splitter keeps the
    top priority and copper is starved."""
    cfg = _load("A.json")
    f = Factory(cfg)
    f.run(cfg["ticks"])

    assert f.inv.count("ore") < 9999, "Ore should have been consumed"
    consumed_copper = 9999 - f.inv.count("copper")
    assert 0 < consumed_copper <= 10, (
        f"Copper consumed during warmup only: {consumed_copper}"
    )
    assert f.inv.count("copper") > 9985, "Copper mostly starved after warmup"


def test_blueprint_B_half_speed() -> None:
    """B: Converger upstreams = [splitter, copper_belt].
    Splitter has two downstreams (converger + left belt).  The
    converger gets priority from the splitter via distance grouping,
    but still falls back to the copper belt when the splitter's
    buffer is empty between deliveries.  Both ore and copper are consumed."""
    cfg = _load("B.json")
    f = Factory(cfg)
    f.run(cfg["ticks"])

    assert f.inv.count("ore") < 9999, "Ore should have been consumed"
    assert f.inv.count("copper") < 9999, (
        "Copper should have been consumed (fallback when splitter buffer empty)"
    )

    splitters = _find(f, CT.LOGISTICS_BELT_SPLITTER)
    assert len(splitters) == 1
    s = splitters[0]
    assert len(s._original_downstreams) == 2, "Splitter should have 2 downstreams"
