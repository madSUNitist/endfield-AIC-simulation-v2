# simulation-v3 Frontend

Web-based simulation viewer with a canvas rendering engine and FastAPI backend.

## Setup

```bash
cd frontend
npm install          # installs TypeScript
npm run build        # compile TS → static/js/
cd ..
uv run python server.py   # start at http://127.0.0.1:8000
```

## Architecture

```
index.html  →  static/ts/*.ts  (compiled to static/js/*.js)  →  Canvas 2D rendering
                        ↕ REST API (JSON)
server.py  ←→  simulation package (Factory, Graph, tick)
```

## Key Directories

| Path | Purpose |
|------|---------|
| `static/ts/` | TypeScript source (compiled to `static/js/`) |
| `static/index.html` | Main page |
| `static/css/style.css` | Layout and styling |
| `server.py` | FastAPI backend |

## TypeScript Modules

| File | Exports |
|------|---------|
| `types.ts` | Interfaces: `LayoutComponent`, `ComponentState`, `Edge`, `Viewport`, `Placement`, `PaletteItem` |
| `api.ts` | REST wrappers: `fetchCases`, `loadCase`, `sendLayout`, `tick`, `resetSim` |
| `renderer.ts` | Canvas drawing, animation (persistent RAF loop), pan/zoom |
| `main.ts` | App state, event handlers, auto-play |
| `palette.ts` | Component palette UI, `buildPlacement` |

## Coordinate System

Matches the simulation backend and Canvas pixel space:

- **Origin**: top-left of the viewport
- **+x**: right
- **+y**: down

### Directions (Canvas-aligned)

| Direction | Vector | Meaning |
|-----------|--------|---------|
| `up` | `(0, -1)` | Negative y |
| `down` | `(0, +1)` | Positive y |
| `left` | `(-1, 0)` | Negative x |
| `right` | `(+1, 0)` | Positive x |

### Rotations

| Rotation | Description |
|----------|-------------|
| `ROT_0` | No rotation |
| `ROT_1` | 90° clockwise |
| `ROT_2` | 180° clockwise |
| `ROT_3` | 270° clockwise |

## Animation Model

- **Persistent RAF loop**: `init()` starts an infinite `requestAnimationFrame` → `draw()` cycle.
- **Timer-based interpolation**: each `setState()` call records `animStartTime`. Progress is `(now - startTime) / duration`.
- **Duration control**: `setAnimDuration(ms)` sets the interpolation window. `0` = snap immediately (used for initial load and reset).
- **Item animation**: `slot_map` keys are `"x,y"` strings. Items are matched across ticks by `id`. Entering items slide from the `direction_in` side; leaving items slide toward the `direction_out` side.

## Component State

| Component | State Fields |
|-----------|--------------|
| Conveyor | `slot_map`: `{ "x,y": {type, id} \| null }` — head maps to `cells[0]`, tail to `cells[-1]` |
| Splitter / Converger | `buffer`: `{type, id} \| null` |
| ProtocolStash | `buffer` + `inventory` (item count) |
| DepotLoader | `count` (items in global inventory of this type) |
| DepotUnloader | `count` |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/cases` | List test case names |
| `GET` | `/api/component_types` | Palette metadata |
| `POST` | `/api/load` | Load a test case by name |
| `POST` | `/api/layout` | Submit a custom layout |
| `POST` | `/api/tick` | Advance N ticks |
| `POST` | `/api/reset` | Reset to tick 0 |

See `server.py` for request/response schemas.
