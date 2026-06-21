# AGENTS.md — simulation-v3

## Developer Commands

| Command | Action |
|---|---|
| `uv sync` | Install Python deps |
| `uv run mypy .` | Static type checking |
| `uv run pytest` | Run all tests |
| `uv run pytest --cov=simulation` | Tests with coverage |
| `uv run pytest -k test_name` | Run a single test |
| `uv run tools/runner.py --all --render type` | Run all JSON test cases with visual output |
| `uv run tools/runner.py tests/units/logistics_units/belt/test_conveyor.jsonc` | Run a single JSON case |
| `uv run tools/visualize.py` | Text + graphviz SVG of all test graphs |
| `uv run tools/visualize.py --no-graphviz` | Text-only graph dump |
| `pwsh server.ps1` | Compile TS + start dev server |
| `uv run frontend/server.py` | Start FastAPI dev server at `http://127.0.0.1:3000` |
| `cd frontend && npm run build` | Compile TypeScript → JS for frontend |
| `uv run pdoc simulation -o docs` | Regenerate API docs |

## TODO — 实验现象复现记录

- [x] **普通优先级** — 复现成功
- [x] **部分环** — 复现成功
- [x] **放置顺序带来的影响** — 已完全实现。Kahn BFS 分层拓扑排序中，同层节点按 placement index 排序。
- [ ] **环的手性** — 暂未复现
- [ ] **分流器-汇流器紧贴时的优先级** — 部分解释
- [ ] **4n 卡 1 现象** — **无法解释**
- [ ] **部分实验复现结果不佳** — `expr_results/expr_1.txt`

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
- Tests are JSONC-driven via `tests/test_runner.py` (see **Test Architecture** below)

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

## Test Architecture

All tests are **JSONC-driven** — assertions live in `.jsonc` config files (JSON with comments, parsed via `json5`).
A single parametrized pytest runner (`tests/test_runner.py`) discovers and executes all cases.

### File Layout
```
tests/
  test_runner.py           # Parametrized runner (discovers all test_*.jsonc)
  assertion_engine.py      # Target resolver + operator evaluator
  mocks.py                 # MockSink, MockSource, MockDownstream
  conftest.py              # Per-source-file headers in the terminal report
  _view.py                 # Render helpers for tools/runner.py
  units/
    logistics_units/belt/
      test_conveyor.jsonc
      test_splitter.jsonc
      test_converger.jsonc
      test_converger_claim.jsonc
      test_priority_splitter-conveyor-converger.jsonc
      test_priority_with_stash.jsonc
    depot_access/
      test_protocol_stash.jsonc
```

### Test Modes

| Mode | Description |
|---|---|
| `integration` | Build Factory → run N ticks → assert end state |
| `temporal` | Build Factory → warmup → observe window → assert on observations |
| `unit` | Create standalone instances + mocks → execute actions → assert |
| `hybrid` | Build Factory → execute actions on factory components → assert |

### Assertion Schema (flat predicate list)

```jsonc
"assertions": [
  { "target": "inventory.ore", "op": "<", "value": 9999 },
  { "target": "graph.order.len", "op": "==", "value": 3 },
  { "target": "components[type=LOGISTICS_BELT_CONVEYOR][0]._count", "op": ">", "value": 0 },
  { "target": "observe.splitter_downstream[-3:]", "op": "in", "value": [[true,false,true],[false,true,false]] },
  { "target": "ProtocolStash:0._inv.count()", "op": "==", "value": 1 }
]
```

### Target Expressions

| Pattern | Resolves to |
|---|---|
| `inventory.<item>` | `factory.inv.count(item)` |
| `graph.order.len` | `len(factory.graph.order)` |
| `components[type=<CT>].len` | Count by ComponentType |
| `components[type=<CT>][i].<attr>` | Component attribute |
| `components[type=<CT>].all.<attr>` | List of values (use with `min_matches`) |
| `ClassName:N.<attr_chain>` | Nth instance of class in factory |
| `observe.<name>` / `observe.<name>[-N:]` | Observation bool sequence |
| `<id>.<attr>` | Unit mode: mock instance by ID |

### Operators

`==`, `!=`, `<`, `>`, `<=`, `>=`, `in`, `all_true`, `any_true`, `is_none`, `not_none`, `between`, `between_inclusive`

### Adding a New Test

1. Add a new key to the appropriate `test_*.jsonc` file
2. Specify `mode`, component layout, and `assertions`
3. Run `uv run pytest tests/test_runner.py -k "new_key_name"` to verify
