# AGENTS.md — simulation-v3

## Developer Commands

| Command | Action |
|---|---|
| `uv sync` | Install dependencies (uses Aliyun PyPI mirror via `pyproject.toml`) |
| `uv run mypy .` | Static type checking (mypy >=2.1.0) |
| `uv run pytest` | Run all tests (pytest >=9.0.3, pytest-cov installed) |
| `uv run pytest --cov=simulation` | Run tests with coverage |
| `uv run pytest tests/test_foo.py::test_bar` | Run a single test (standard pytest) |

## Project Structure

- **`simulation/`** — Main package (no `__main__.py` — no entry point / CLI)
  - **`_enums.py`** — Core enums: `Direction`, `Rotation`, `ComponentType`, `LinkType`
  - **`_types.py`** — Type aliases: `Coverage = Tuple[int, int]`, `RelativeOffset = Tuple[int, int]`
  - **`layout.py`** — `Layout` class: grid-based component placement with overlap detection at init
  - **`graph.py`** — `Graph` class: **WIP/incomplete** — builds connection graph from Layout but `__init__` is unfinished
  - **`mappings.py`** — `get_metadata()` (coverage + ports from JSON), `get_components()` (factory: ComponentType → class instance)
  - **`utils/`** — `Vec` (2D vector with rotate/towards), `Area` (coverage rectangle yielding offsets)
  - **`units/`** — Component classes (all `pass` stubs), organized into `depot_access/`, `logistics_units/`, `power_units/`, `production_units/`
- **`assets/unit_metadata.json`** — Component coverage and port definitions in JSON
- **`tests/`** — Exists but empty; no tests written yet

## Known Issues

- **`simulation/mappings.py:22`**: `open("../../assests/unit_metadata.json")` — path has a typo (`assests` → `assets`) and is relative to CWD, not the file. Use `pathlib.Path(__file__).parent.parent / "assets" / "unit_metadata.json"` instead.

## Coordinate System & Directions

- `Vec(x, y)` where `y` is "forward". Direction values: `UP = (0, +1)`, `DOWN = (0, -1)`, `LEFT = (+1, 0)`, `RIGHT = (-1, 0)`
- Rotations: `ROT_0` (none), `ROT_1` (CW 90°), `ROT_2` (180°), `ROT_3` (270°)
- `Vec.rotate(r)` uses standard rotation matrix. `Vec.towards(d)` returns `self + direction.value`
- `Direction @ Rotation` transforms a direction by a rotation
- `Rotation @ Rotation` composes two rotations

## Code Conventions (observed — no formatter config)

- `match`/`case` statements used throughout (Python ≥3.10, repo uses 3.13)
- Classes inherit from `object` explicitly (`class Base(object)`)
- `Vec`, `Layout`, `Area` implement `__iter__` to allow tuple unpacking
- Relative imports within the package
- No ruff, black, or other formatter/linter configured in `pyproject.toml` (only mypy listed)

## Missing Configuration

- **No root `.gitignore`** — `.mypy_cache/` and `.venv/` have their own, but `__pycache__/`, `*.pyc`, etc. are not ignored
- **No CI/CD** (no `.github/workflows/`)
- **No pre-commit hooks**
- **No formatter config** — if adding ruff/black, add to `pyproject.toml`
- **No tests** — `uv run pytest` runs zero tests
