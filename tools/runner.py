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
from tests._view import render_belt, RENDER_MODES, load_test_case


def run_single(path: Path, render: str | None = None) -> None:
    cfg = load_test_case(path)
    if render:
        cfg["render"] = render
    mode = cfg.get("render", RENDER_MODES[0])
    f = Factory(cfg)
    name = cfg.get("name", path.stem)

    convs: list[Conveyor] = []
    for comp in f.graph.components.values():
        if isinstance(comp, Conveyor):
            convs.append(comp)

    print(f"\n=== {name} ===  render={mode}")
    print(f"  init   ", end="")
    for comp in convs:
        print(f"  {render_belt(comp, mode)}", end="")
    print()

    for t in range(cfg.get("ticks", 30)):
        f.tick()
        out = f"  tick={t:>3d}"
        for comp in convs:
            out += f"  {render_belt(comp, mode)}"
        print(out)

    for coord, comp in f.graph.components.items():
        ct = getattr(comp, 'component_type', None)
        if ct is CT.DEPOT_ACCESS_DEPOT_UNLOADER:
            print(f"  unloader @({coord.x},{coord.y})")


def run_all(test_dir: Path, render: str | None = None) -> None:
    for j in sorted(test_dir.glob("*.json")):
        run_single(j, render)
        print()


def main() -> None:
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
