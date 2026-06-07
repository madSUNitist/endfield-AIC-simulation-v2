"""Run conveyor simulation from JSON test cases.

Usage:
    uv run python tools/runner.py tests/test_cases/belt_line.json
    uv run python tools/runner.py tests/test_cases/belt_line.json --render binary
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


def run_single(path: Path, render: str | None = None) -> None:
    """Load and run a single JSON test case.

    Args:
        path: Path to the JSON test case file.
        render: Optional render mode override ("type", "binary", etc.).
    """
    cfg = load_test_case(path)
    if render:
        cfg["render"] = render
    mode = cfg.get("render", RENDER_MODES[0])
    fac = Factory(cfg)
    name = cfg.get("name", path.stem)

    convs, cvgs, splts, stshs = _collect_components(fac)

    print(f"\n=== {name} ===  render={mode}")
    print(_render_frame(convs, cvgs, splts, stshs, mode, "init"))

    for t in range(cfg.get("ticks", 30)):
        fac.tick()
        print(_render_frame(convs, cvgs, splts, stshs, mode, f"tick={t:>3d}"))

    _report_unloaders(fac)


def run_all(test_dir: Path, render: str | None = None) -> None:
    """Run all JSON test cases in a directory.

    Args:
        test_dir: Directory containing ``*.json`` test case files.
        render: Optional render mode override.
    """
    for j in sorted(test_dir.glob("*.json")):
        run_single(j, render)
        print()


def main() -> None:
    """Parse command-line arguments and run test cases."""
    args = sys.argv[1:]
    render: str | None = None
    paths: list[str] = []

    i = 0
    while i < len(args):
        if args[i] == "--render" and i + 1 < len(args):
            render = args[i + 1]
            i += 2
        elif args[i] == "--all":
            paths = []
            break
        else:
            paths.append(args[i])
            i += 1

    test_dir = Path(__file__).parent.parent / "tests" / "test_cases"

    if not paths:
        run_all(test_dir, render)
        return

    for p in paths:
        run_single(Path(p), render)


if __name__ == "__main__":
    main()
