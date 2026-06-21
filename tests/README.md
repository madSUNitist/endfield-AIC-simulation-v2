# Test Framework Documentation

## Overview

All tests in this project are **JSONC-driven**. Assertions, component layouts, and test
configuration live together in `.jsonc` files (JSON with comments, parsed via `json5`).
A single parametrized pytest runner (`tests/test_runner.py`) discovers and executes every
case that contains an `"assertions"` key.

No Python test files are needed to add new tests — just add a key to the appropriate `.jsonc` file.

### Key Components

| File | Role |
|---|---|
| `tests/test_runner.py` | Parametrized pytest entry point; mode dispatcher |
| `tests/assertion_engine.py` | Target expression resolver + operator evaluator |
| `tests/mocks.py` | Mock component classes for unit-mode tests |

---

## Running Tests

```bash
# Run all tests
uv run pytest

# Run all tests with verbose output
uv run pytest tests/test_runner.py -v

# Run a single test case by key name
uv run pytest -k "belt_line"

# Run all cases from one JSONC file
uv run pytest -k "test_conveyor.jsonc"

# Run with coverage
uv run pytest --cov=simulation

# Visual debugging (not assertions — frame-by-frame rendering)
uv run tools/runner.py tests/units/logistics_units/belt/test_conveyor.jsonc --render type
```

Test IDs follow the format: `test_case[<relative_jsonc_path>::<case_key>]`

Example: `test_case[units/logistics_units/belt/test_conveyor.jsonc::belt_line]`

---

## File Layout

```
tests/
├── test_runner.py              # Parametrized runner (discovers test_*.jsonc)
├── assertion_engine.py         # Target resolver + operator evaluator
├── mocks.py                    # MockSink, MockSource, MockDownstream
├── _view.py                    # Render helpers for tools/runner.py
├── __init__.py
├── blueprints/                 # Saved .blueprint files (used by runner tool)
└── units/
    ├── logistics_units/
    │   └── belt/
    │       ├── test_conveyor.jsonc
    │       ├── test_splitter.jsonc
    │       ├── test_converger.jsonc
    │       ├── test_converger_claim.jsonc
    │       └── test_placement_order.jsonc
    └── depot_access/
        └── test_protocol_stash.jsonc
```

Each `.jsonc` file is a dict of `{ "case_key": { ...config... }, ... }`.
JSONC supports `//` line comments and `/* */` block comments via the `json5` library.
Only entries with an `"assertions"` array are picked up by pytest.
Entries without assertions are still usable by `tools/runner.py` for visual debugging.

---

## Test Modes

Every test case must declare a `"mode"` field (defaults to `"integration"` if omitted).

### Integration

Build a Factory from the component layout, run N ticks, then assert on end state.

```jsonc
{
  "my_test": {
    "mode": "integration",
    "ticks": 20,
    "inventory": { "ore": 9999 },
    "components": [
      { "pos": [-1, 0], "type": "depot_loader", "rot": "ROT_0", "item": "ore" },
      { "path": [[0,1],[0,4]], "type": "conveyor", "direction_in": "up", "direction_out": "down" },
      { "pos": [-1, 5], "type": "depot_unloader", "rot": "ROT_0" }
    ],
    "assertions": [
      { "target": "graph.order.len", "op": "==", "value": 3 },
      { "target": "inventory.ore", "op": "<", "value": 9999 }
    ]
  }
}
```

**Lifecycle:** `Factory(cfg)` → `f.run(ticks)` → evaluate assertions against `f`.

---

### Temporal

Build a Factory, warm up for N ticks, then observe component state each tick over a
window of M ticks. Assert on the recorded observation sequences and/or final state.

```jsonc
{
  "my_temporal_test": {
    "mode": "temporal",
    "inventory": { "ore": 9999 },
    "components": [ /* ... */ ],
    "observe": {
      "warmup": 30,
      "window": 20,
      "targets": {
        "splitter_out": {
          "component": "Splitter:0",
          "follow": "downstream.Conveyor",
          "expr": "_slots[0] is not None"
        },
        "converger_out": {
          "component": "Converger:0",
          "follow": "downstream.Conveyor",
          "expr": "_slots[0] is not None"
        }
      }
    },
    "assertions": [
      { "target": "observe.splitter_out[-3:]", "op": "in", "value": [[true,false,true],[false,true,false]] },
      { "target": "observe.converger_out", "op": "all_true" }
    ]
  }
}
```

**Lifecycle:**
1. `Factory(cfg)`
2. Tick `warmup` times (no recording)
3. Tick `window` times, evaluating each `targets[name].expr` on the resolved component per tick
4. Evaluate assertions against observations + final factory state

#### Observe Target Config

| Field | Required | Description |
|---|---|---|
| `component` | yes | Reference to component: `"ClassName:Index"` (e.g. `"Splitter:0"`) |
| `follow` | no | Navigate from that component: `"downstream.ClassName"` or `"upstream.ClassName"` |
| `expr` | yes | Python expression evaluated per tick against the resolved component's attributes |

The `expr` is evaluated with all non-dunder attributes of the target component available
as local variables (e.g. `_slots`, `_buffer`, `_count`).

---

### Unit

Create standalone component/mock instances, wire them manually, execute a sequence of
actions, then assert on instance state. No Factory is built.

```jsonc
{
  "splitter_rr_231": {
    "mode": "unit",
    "setup": {
      "instances": [
        { "id": 0, "class": "Splitter" },
        { "id": 1, "class": "MockSink" },
        { "id": 2, "class": "MockSink" },
        { "id": 3, "class": "MockSink" }
      ],
      "wiring": {
        "0.downstreams": [1, 2, 3],
        "0._owner_downstreams": [1, 2, 3]
      },
      "finalize": [0]
    },
    "actions": [
      { "repeat": 6, "steps": [
        { "set": "0._buffer", "item": "ore" },
        { "set": "0.pull_requests", "refs": [1, 2, 3] },
        { "call": "0.fulfill_requests" }
      ]}
    ],
    "assertions": [
      { "target": "1.received", "op": "==", "value": [1, 1] },
      { "target": "2.received", "op": "==", "value": [2, 2] },
      { "target": "3.received", "op": "==", "value": [3, 3] }
    ]
  }
}
```

**Lifecycle:**
1. Create instances from `setup.instances`
2. Wire attributes from `setup.wiring`
3. Call `finalize()` on listed instances
4. Apply `setup.overrides` (optional)
5. Execute `actions` sequentially
6. Evaluate assertions against instance state

#### Setup Schema

| Field | Description |
|---|---|
| `instances` | Array of `{ "id": N, "class": "ClassName", "args": {...} }` |
| `wiring` | Dict of `"<id>.<attr>": [ref_id, ...]` — sets attribute to list of instance refs |
| `finalize` | Array of instance IDs to call `.finalize()` on |
| `overrides` | Dict of `"<id>.<method>": <return_value>` — replaces method with a lambda |

#### Available Classes

| Class | Base | Extra State |
|---|---|---|
| `Splitter` | — | `_buffer` |
| `Converger` | — | `_buffer`, `_skip_idx`, `_predictor` |
| `Conveyor` | — | `_slots`, `_count` |
| `ProtocolStash` | — | `_buffer`, `_inv` |
| `MockSink` | Splitter | `received: list[int]` |
| `MockSource` | Converger | `pulls_received: int` |
| `MockDownstream` | Conveyor | `received_ids: list[int]` |

#### Instance Args

| Class | Supported Args |
|---|---|
| `ProtocolStash` | `inventory_size` (default 6) |
| `Conveyor` | `length` (default 4) |
| Others | None |

---

### Hybrid

Build a Factory from a component layout, optionally run ticks, then execute actions that
reference factory components by `ClassName:Index`, then assert on factory state.

Useful for testing component internals (e.g. `_accept_item`, `phase2`) in a properly
wired environment without reimplementing the Factory's wiring logic.

```jsonc
{
  "stash_fulfill_clears_pulls": {
    "mode": "hybrid",
    "ticks": 0,
    "inventory": { "ore": 9999 },
    "components": [
      { "pos": [0, -1], "type": "depot_loader", "rot": "ROT_0", "item": "ore" },
      { "pos": [1, 0], "type": "protocol_stash", "rot": "ROT_0" },
      { "path": [[1,3],[1,4]], "type": "conveyor", "direction_in": "up", "direction_out": "down" },
      { "pos": [1, 5], "type": "depot_unloader", "rot": "ROT_0" }
    ],
    "actions": [
      { "set": "ProtocolStash:0._buffer", "item": "ore" },
      { "call": "ProtocolStash:0.add_pull", "ref": "Conveyor:0" },
      { "call": "ProtocolStash:0.fulfill_requests" }
    ],
    "assertions": [
      { "target": "ProtocolStash:0.pull_requests.len", "op": "==", "value": 0 }
    ]
  }
}
```

**Lifecycle:**
1. `Factory(cfg)`
2. `f.run(ticks)` if ticks > 0
3. Execute actions (referencing factory components)
4. Evaluate assertions against factory state

#### Hybrid Action Types

| Action | Description | Example |
|---|---|---|
| `set` | Set attribute on a factory component | `{ "set": "ProtocolStash:0._buffer", "item": "ore" }` |
| `call` | Call method on a factory component | `{ "call": "ProtocolStash:0.fulfill_requests" }` |
| `call` + `item` | Call method with an Item argument | `{ "call": "ProtocolStash:0._accept_item", "item": "ore" }` |
| `call` + `ref` | Call method with another component as argument | `{ "call": "ProtocolStash:0.add_pull", "ref": "Conveyor:0" }` |
| `push_inv` | Push items into a component's inventory | `{ "push_inv": "ProtocolStash:0._inv", "item": "ore", "count": 3 }` |
| `repeat` | Repeat a block of steps N times | `{ "repeat": 5, "steps": [...] }` |

---

## Assertion Schema Reference

### Structure

```jsonc
"assertions": [
  { "target": "<target_expr>", "op": "<operator>", "value": <expected> },
  { "target": "<target_expr>", "op": "<operator>", "value": <expected>, "min_matches": N },
  { "target": "<target_expr>", "op": "is_none" }
]
```

- `target`: Expression string resolved to a value (see Target Expressions below)
- `op`: Comparison operator
- `value`: Expected value (omitted for unary operators like `is_none`, `all_true`)
- `min_matches`: When target resolves to a list, require at least N elements to satisfy the op

---

### Target Expressions

| Pattern | Resolves to | Mode |
|---|---|---|
| `inventory.<item>` | `factory.inv.count(item)` | integration, temporal, hybrid |
| `graph.order.len` | `len(factory.graph.order)` | integration, temporal, hybrid |
| `components[type=<CT>].len` | Count of components with that ComponentType | integration, hybrid |
| `components[type=<CT>][i].<attr>` | The i-th component's attribute | integration, hybrid |
| `components[type=<CT>].any.<attr>` | List of attribute values from all matching components | integration, hybrid |
| `components[type=<CT>].all.<attr>` | List of attribute values (use with `min_matches`) | integration, hybrid |
| `ClassName:N.<attr_chain>` | N-th instance of ClassName in factory, then resolve chain | integration, temporal, hybrid |
| `observe.<name>` | Full observation bool sequence | temporal |
| `observe.<name>[-N:]` | Last N entries of observation sequence | temporal |
| `<id>.<attr>` | Instance by numeric ID (unit mode only) | unit |

#### ComponentType Names

Use the enum member name from `simulation._enums.ComponentType`:

```
LOGISTICS_BELT_CONVEYOR
LOGISTICS_BELT_SPLITTER
LOGISTICS_BELT_CONVERGER
DEPOT_ACCESS_DEPOT_LOADER
DEPOT_ACCESS_DEPOT_UNLOADER
DEPOT_ACCESS_PROTOCOL_STASH
```

#### Attribute Chains

Target expressions support dotted attribute traversal with:

| Syntax | Meaning |
|---|---|
| `.attr` | `getattr(obj, "attr")` |
| `.len` | `len(obj)` |
| `.method()` | `obj.method()` (no-arg call) |
| `._slots[-1]` | Negative indexing on a list attribute |
| `._slots[0]` | Positive indexing on a list attribute |

Examples:
- `ProtocolStash:0._inv.count()` → calls `stash._inv.count()`
- `ProtocolStash:0.pull_requests.len` → `len(stash.pull_requests)`
- `Conveyor:0._slots[-1]` → last slot of conveyor
- `Splitter:0._original_downstreams.len` → number of original downstreams

---

### Operators

| Operator | Arity | Semantics |
|---|---|---|
| `==` | binary | `value == expected` |
| `!=` | binary | `value != expected` |
| `<` | binary | `value < expected` |
| `>` | binary | `value > expected` |
| `<=` | binary | `value <= expected` |
| `>=` | binary | `value >= expected` |
| `in` | binary | `value` is one of the items in `expected` (list of acceptable values) |
| `all_true` | unary | Every element in the sequence is truthy |
| `any_true` | unary | At least one element is truthy |
| `is_none` | unary | `value is None` |
| `not_none` | unary | `value is not None` |
| `between` | binary | `expected[0] < value < expected[1]` (exclusive) |
| `between_inclusive` | binary | `expected[0] <= value <= expected[1]` (inclusive) |

#### The `in` Operator

Used for multi-possible-state assertions. The `value` field is a list of acceptable values.
The assertion passes if the resolved target equals any one of them.

```jsonc
{ "target": "observe.splitter_out[-3:]", "op": "in", "value": [[true,false,true],[false,true,false]] }
```

This means: the last 3 observations must be either `[T,F,T]` or `[F,T,F]`.

#### The `min_matches` Field

When used with `.all.<attr>`, the target resolves to a list. Instead of comparing the
whole list, the engine counts how many elements satisfy `op` + `value`, and passes if
that count >= `min_matches`.

```jsonc
{ "target": "components[type=LOGISTICS_BELT_CONVEYOR].all._count", "op": "==", "value": 0, "min_matches": 3 }
```

This means: at least 3 conveyors must have `_count == 0`.

```jsonc
{ "target": "components[type=LOGISTICS_BELT_CONVEYOR].all._count", "op": ">", "value": 0, "min_matches": 1 }
```

This means: at least 1 conveyor has `_count > 0` (equivalent to "any").

---

## Mock Classes

Defined in `tests/mocks.py`. Used exclusively in `unit` mode.

### MockSink (extends Splitter)

Accepts all items; records `self.id` into `received` list on each accept.

| Attribute | Type | Description |
|---|---|---|
| `received` | `list[int]` | Appended with `self.id` each time `_accept_item` is called |

### MockSource (extends Converger)

Always reports `can_pull() = True`; counts pull requests.

| Attribute | Type | Description |
|---|---|---|
| `pulls_received` | `int` | Incremented each time `add_pull` is called |

### MockDownstream (extends Conveyor)

Accepts items into a 50-slot belt; records `self.id` into `received_ids` on each accept.

| Attribute | Type | Description |
|---|---|---|
| `received_ids` | `list[int]` | Appended with `self.id` each time `_accept_item` is called |

---

## Adding a New Test

### Step 1: Choose the JSON file

Place tests in the appropriate category:
- Belt components → `tests/units/logistics_units/belt/test_<component>.jsonc`
- Depot access → `tests/units/depot_access/test_<component>.jsonc`

### Step 2: Add a new key

```jsonc
{
  "existing_test": { /* ... */ },
  "my_new_test": {
    "mode": "integration",
    "ticks": 20,
    "inventory": { "ore": 9999 },
    "components": [ /* ... */ ],
    "assertions": [
      { "target": "inventory.ore", "op": "<", "value": 9999 }
    ]
  }
}
```

### Step 3: Run and verify

```bash
uv run pytest -k "my_new_test" -v
```

### Step 4: Visual debugging (optional)

```bash
uv run tools/runner.py tests/units/.../test_file.jsonc --key my_new_test --render type
```

---

## Complete Examples

### Integration Mode — Basic Belt

```jsonc
{
  "belt_line": {
    "mode": "integration",
    "ticks": 6,
    "inventory": { "ore": 9999 },
    "components": [
      { "pos": [-1, 0], "type": "depot_loader", "rot": "ROT_0", "item": "ore" },
      { "path": [[0,1],[0,4]], "type": "conveyor", "direction_in": "up", "direction_out": "down" },
      { "pos": [-1, 5], "type": "depot_unloader", "rot": "ROT_0" }
    ],
    "assertions": [
      { "target": "graph.order.len", "op": "==", "value": 3 },
      { "target": "components[type=LOGISTICS_BELT_CONVEYOR].len", "op": "==", "value": 1 },
      { "target": "components[type=LOGISTICS_BELT_CONVEYOR][0]._count", "op": ">", "value": 0 }
    ]
  }
}
```

### Temporal Mode — Splitter/Converger Observation

```jsonc
{
  "order_splitter_first": {
    "mode": "temporal",
    "inventory": { "ore": 9999 },
    "components": [
      { "type": "depot_loader", "pos": [6, 1], "rot": "ROT_0", "item": "ore" },
      { "type": "conveyor", "path": [[7, 2], [8, 2]], "direction_in": "up", "direction_out": "down" },
      { "type": "splitter", "pos": [8, 3], "rot": "ROT_0" },
      { "type": "converger", "pos": [9, 3], "rot": "ROT_0" },
      { "type": "conveyor", "path": [[8, 4], [8, 6], [7, 6]], "direction_in": "up", "direction_out": "down" },
      { "type": "conveyor", "path": [[9, 4], [9, 6], [10, 6]], "direction_in": "up", "direction_out": "down" },
      { "type": "depot_unloader", "pos": [6, 7], "rot": "ROT_0" },
      { "type": "depot_unloader", "pos": [9, 7], "rot": "ROT_0" }
    ],
    "observe": {
      "warmup": 30,
      "window": 20,
      "targets": {
        "splitter_downstream": {
          "component": "Splitter:0",
          "follow": "downstream.Conveyor",
          "expr": "_slots[0] is not None"
        },
        "converger_downstream": {
          "component": "Converger:0",
          "follow": "downstream.Conveyor",
          "expr": "_slots[0] is not None"
        }
      }
    },
    "assertions": [
      { "target": "observe.splitter_downstream[-3:]", "op": "in", "value": [[true,false,true],[false,true,false]] },
      { "target": "observe.converger_downstream", "op": "all_true" }
    ]
  }
}
```

### Unit Mode — Round-Robin Verification

```jsonc
{
  "converger_rr_cycling": {
    "mode": "unit",
    "setup": {
      "instances": [
        { "id": 0, "class": "Converger" },
        { "id": 1, "class": "MockSource" },
        { "id": 2, "class": "MockSource" }
      ],
      "wiring": {
        "0.upstreams": [1, 2]
      }
    },
    "actions": [
      { "repeat": 5, "steps": [
        { "call": "0.request_upstream" }
      ]}
    ],
    "assertions": [
      { "target": "1.pulls_received", "op": "==", "value": 1 },
      { "target": "2.pulls_received", "op": "==", "value": 1 }
    ]
  }
}
```

### Hybrid Mode — Factory Component Manipulation

```jsonc
{
  "stash_accept_step1_forward": {
    "mode": "hybrid",
    "ticks": 0,
    "inventory": { "ore": 9999 },
    "components": [
      { "pos": [0, -1], "type": "depot_loader", "rot": "ROT_0", "item": "ore" },
      { "pos": [1, 0], "type": "protocol_stash", "rot": "ROT_0" },
      { "path": [[1,3],[1,4]], "type": "conveyor", "direction_in": "up", "direction_out": "down" },
      { "pos": [1, 5], "type": "depot_unloader", "rot": "ROT_0" }
    ],
    "actions": [
      { "call": "ProtocolStash:0._accept_item", "item": "ore" },
      { "call": "ProtocolStash:0.phase2" }
    ],
    "assertions": [
      { "target": "Conveyor:0._slots[-1]", "op": "not_none" },
      { "target": "ProtocolStash:0._buffer", "op": "is_none" }
    ]
  }
}
```
