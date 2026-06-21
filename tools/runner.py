"""Run conveyor simulation from JSON test cases.

Usage:
    uv run python tools/runner.py tests/units/logistics_units/belt/test_conveyor.json
    uv run python tools/runner.py tests/units/logistics_units/belt/test_conveyor.json --key belt_line
    uv run python tools/runner.py --all --render type
"""

import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.factory import Factory
from simulation._enums import ComponentType as CT
from simulation.units.logistics_units.belt.conveyor import Conveyor
from simulation.units.logistics_units.belt.converger import Converger
from simulation.units.logistics_units.belt.splitter import Splitter
from simulation.units.depot_access.protocol_stash import ProtocolStash
from tests._view import render_belt, render_converger, render_splitter, render_stash, RENDER_MODES, load_test_case


def _collect_components(fac: Factory) -> tuple[
    list[Conveyor],
    list[tuple[Converger, int, int]],
    list[tuple[Splitter, int, int]],
    list[tuple[ProtocolStash, int, int]],
]:
    """Group components by type from the factory graph.

    Args:
        fac: A built Factory instance.

    Returns:
        Tuple of (conveyors, convergers, splitters, stashes) where each
        converger/splitter/stash entry is ``(comp, x, y)``.
    """
    convs: list[Conveyor] = []
    cvgs: list[tuple[Converger, int, int]] = []
    splts: list[tuple[Splitter, int, int]] = []
    stshs: list[tuple[ProtocolStash, int, int]] = []

    for coord, idx in fac.graph.coord_idx.items():
        comp = fac.graph.components[idx]
        if isinstance(comp, Conveyor):
            convs.append(comp)
        elif isinstance(comp, Converger):
            cvgs.append((comp, coord.x, coord.y))
        elif isinstance(comp, Splitter):
            splts.append((comp, coord.x, coord.y))
        elif isinstance(comp, ProtocolStash):
            stshs.append((comp, coord.x, coord.y))

    return convs, cvgs, splts, stshs


def _render_frame(
    convs: list[Conveyor],
    cvgs: list[tuple[Converger, int, int]],
    splts: list[tuple[Splitter, int, int]],
    stshs: list[tuple[ProtocolStash, int, int]],
    mode: str,
    label: str,
) -> str:
    """Build a single frame of text output.

    Args:
        convs: Conveyor instances.
        cvgs: Converger instances with coords.
        splts: Splitter instances with coords.
        stshs: Stash instances with coords.
        mode: Render mode name.
        label: Label prefix (e.g. "init" or "tick=  0").

    Returns:
        Single-line string for this frame.
    """
    parts = [f"{label:<9s}"]
    for belt in convs:
        parts.append(f"  {render_belt(belt, mode)}")
    for cvg, _, _ in cvgs:
        parts.append(f"  cvrg {render_converger(cvg, mode)}")
    for splt, _, _ in splts:
        parts.append(f"  splt {render_splitter(splt, mode)}")
    for stash, _, _ in stshs:
        parts.append(f"  stash{render_stash(stash, mode)}")
    return "".join(parts)


def _report_unloaders(fac: Factory) -> None:
    """Print positions of all unloader components in the graph."""
    for coord, idx in fac.graph.coord_idx.items():
        comp = fac.graph.components[idx]
        ct = getattr(comp, 'component_type', None)
        if ct is CT.DEPOT_ACCESS_DEPOT_UNLOADER:
            print(f"  unloader @({coord.x},{coord.y})")


def run_case(cfg: dict, name: str, render: str | None = None) -> None:
    """Run a single test case config.

    Args:
        cfg: Test case configuration dict.
        name: Display name for the case.
        render: Optional render mode override ("type", "binary", etc.).
    """
    if render:
        cfg["render"] = render
    mode = cfg.get("render", RENDER_MODES[0])
    fac = Factory(cfg)

    convs, cvgs, splts, stshs = _collect_components(fac)

    print(f"\n=== {name} ===  render={mode}")
    print(_render_frame(convs, cvgs, splts, stshs, mode, "init"))

    for t in range(cfg.get("ticks", 30)):
        fac.tick()
        print(_render_frame(convs, cvgs, splts, stshs, mode, f"tick={t:>3d}"))

    _report_unloaders(fac)


def run_file(path: Path, render: str | None = None, key: str | None = None) -> None:
    """Load a multi-case JSON file and run cases.

    Args:
        path: Path to a JSON file containing keyed test cases.
        render: Optional render mode override.
        key: If given, run only this case; otherwise run all cases in the file.
    """
    data = load_test_case(path)
    if key:
        cfg = data[key]
        run_case(cfg, cfg.get("name", key), render)
    else:
        for k, cfg in data.items():
            run_case(cfg, cfg.get("name", k), render)
            print()


def run_all(render: str | None = None) -> None:
    """Run all JSON test cases under tests/.

    Args:
        render: Optional render mode override.
    """
    test_root = Path(__file__).parent.parent / "tests"
    for j in sorted(test_root.rglob("test_*.jsonc")):
        run_file(j, render)


def main() -> None:
    """Parse command-line arguments and run test cases."""
    args = sys.argv[1:]
    render: str | None = None
    key: str | None = None
    paths: list[str] = []
    run_all_flag = False

    i = 0
    while i < len(args):
        if args[i] == "--render" and i + 1 < len(args):
            render = args[i + 1]
            i += 2
        elif args[i] == "--key" and i + 1 < len(args):
            key = args[i + 1]
            i += 2
        elif args[i] == "--all":
            run_all_flag = True
            i += 1
        else:
            paths.append(args[i])
            i += 1

    if run_all_flag:
        run_all(render)
        return

    for p in paths:
        run_file(Path(p), render, key)


if __name__ == "__main__":
    main()
