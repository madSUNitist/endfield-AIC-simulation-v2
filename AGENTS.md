# AGENTS.md — simulation-v3

## Developer Commands

| Command | Action |
|---|---|
| `uv sync` | Install Python deps |
| `uv run mypy .` | Static type checking |
| `uv run pytest` | Run all tests |
| `uv run pytest --cov=simulation` | Tests with coverage |
| `uv run pytest -k test_name` | Run a single test |
| `uv run python tools/runner.py --all --render type` | Run all JSON test cases with visual output |
| `uv run python tools/runner.py tests/test_cases/belt_line.json` | Run a single JSON case |
| `uv run python tools/visualize.py` | Text + graphviz SVG of all test graphs |
| `uv run python tools/visualize.py --no-graphviz` | Text-only graph dump |
| `pwsh server.ps1` | Compile TS + start dev server |
| `uv run python frontend/server.py` | Start FastAPI dev server at `http://127.0.0.1:3000` |
| `cd frontend && npm run build` | Compile TypeScript → JS for frontend |
| `uv run pdoc simulation -o docs` | Regenerate API docs |

## Architecture

### Pipeline
```
JSON config → Factory → Layout (grid occupancy) + Graph (port connections + topological order)
                           → components[Vec] → reverse-topological tick loop
```

### Tick Loop (two-phase: sinks→sources then sources→sinks)
```python
for coord in graph.order:
    comp.phase1()                 # fulfill_requests() + request_upstream()
for coord in reversed(graph.order):
    comp.phase2()                 # zero-tick forwarding (no-op by default)
```

Components auto-connect via port direction matching + rotation. No manual wiring.

### Key Classes
- `Vec(x, y)` — 2D coordinate; y=forward; `rotate(r)`, `towards(d)`, `@` operator, `__iter__`
- `AreaCoverage(w, h)` / `PathCoverage(waypoints)` — rectangular vs polyline footprints
- `Layout` — occupancy grid with overlap detection at init
- `Graph` — builds edges via port-direction matching; Kahn topological sort
- `Factory` — assembles everything from JSON config; owns IDGen, Inventory, Layout, Graph
- `Base(ABC)` — upstreams/downstreams, pull_requests (RR), `phase1()` / `phase2()` hooks
- `IDGen` — monotonic integer allocator

### Converger Priority

The Splitter's `_build_distance_groups` override places Convergers in the highest-priority
distance group. When a Splitter has a Converger among its downstreams, the Converger is
always served before non-Converger downstreams regardless of topo_index (distance to sink).

## Conventions

- Python 3.13, `match`/`case` throughout
- Core data classes inherit from `object` explicitly
- Components inherit from `Base(ABC)`
- Relative imports within `simulation` package
- `mypy` only; no formatter/linter configured
- Tests load JSON cases from `tests/test_cases/`

## Key Quirks

- **Conveyors use path-based placement**: JSON requires `path` (waypoints list), `direction_in`, `direction_out` instead of `pos`/`rot`
- **`mappings.py` loads JSON relative to CWD**: works from repo root (`uv run`); fails if CWD differs
- **Only belt component implementations exist** — `Conveyor`, `Splitter`, `Converger`, `ProtocolStash`. `BeltBridge` and `ItemControlPort` are stubs that raise `NotImplementedError`. All pipe, power, production, conduit, and fluid tank units are stubs that raise `NotImplementedError`.
- **`docs/` is pdoc-generated**: rebuild with `pdoc simulation -o docs` after API changes
- **Assets directory is `assets/`** (not `assests/`)

## Frontend

- **Backend**: `frontend/server.py` — FastAPI serving REST API at `/api/*`
- **Frontend**: `frontend/static/` — HTML + TypeScript (compiled to JS), canvas-based simulation viewer
- API endpoints: `/api/cases`, `/api/component_types`, `/api/load`, `/api/layout`, `/api/tick`, `/api/reset`, `/api/blank`, `/api/save`, `/api/load-blueprint`, `/api/validate-path`
