# Endfield AIC Simulation (v3)

Conveyor belt logistics simulation for Arknights: Endfield. Grid-based component placement with pull-model item transport.

## Project Structure

```
simulation/
├── _enums.py        Direction, Rotation, ComponentType, LinkType
├── _types.py        Coverage, RelativeOffset type aliases
├── _id_gen.py       IDGen — monotonic ID allocator
├── factory.py       Factory — builds Layout + Graph from JSON config
├── layout.py        Layout — grid occupancy, overlap detection
├── graph.py         Graph — port-based connections, topological sort, tick
├── mappings.py      Metadata lookup (coverage, ports), component factory
├── items/
│   ├── item.py      Item (id + type)
│   ├── itemstack.py ItemStack (typed stack with capacity)
│   └── inventory.py Inventory (slot array with push/pop/pop(type))
├── units/
│   ├── base.py      Base(ABC) — upstreams/downstreams, pull_requests, tick hooks
│   ├── depot_access/  DepotLoader (source), DepotUnloader (sink), ProtocolStash
│   └── logistics_units/belt/  Conveyor, Splitter, Converger, BeltBridge, ItemControlPort
└── utils/
    ├── vec.py       Vec(x, y) with rotate/towards
    └── area.py      Area coverage rectangle

assets/unit_metadata.json   Port and coverage definitions
tests/
├── _view.py              Belt rendering helpers (shared by runner + pytest)
├── test_cases/*.json     JSON test case definitions
└── test_conveyor.py      pytest test suite

tools/
└── runner.py        CLI: run JSON test cases with verbose output
```

## Tick Loop

Single-pass reverse-topological traversal (pull model):

```
for coord in reversed(graph.order):   # sinks → sources
    comp.fulfill_requests()            # give items to downstream pullers
    comp.request_upstream()            # register pull on upstream, advance ptr
```

Components are fully connected via the graph builder (port direction matching + rotation). No manual wiring.

## Components

| Component | Input | Output | Behavior |
|-----------|-------|--------|----------|
| **Conveyor** | 1 max | 1 max | Circular buffer with programmable length; ptr advances each tick |
| **DepotLoader** | 0 | ≥1 | Pop items from global inventory by type |
| **DepotUnloader** | ≥1 | 0 | Push received items to global inventory |
| **Splitter** | 1 | 3 | Distribute to multiple outputs |
| **Converger** | 3 | 1 | Merge from multiple inputs |

## Running

```bash
uv sync                        # install deps (Aliyun mirror)
uv run pytest -v               # run tests
uv run python tools/runner.py --all --render type   # run all test cases
uv run python tools/runner.py tests/test_cases/belt_line.json --render binary
```

## Coordinate System

```
Vec(x, y)  y is "forward"

UP    = ( 0, +1)
DOWN  = ( 0, -1)
LEFT  = (+1,  0)
RIGHT = (-1,  0)

Rotation: ROT_0 (0°), ROT_1 (CW 90°), ROT_2 (180°), ROT_3 (270°)
```
