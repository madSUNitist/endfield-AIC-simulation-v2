# 4-Stage Tick Engine — Architecture & Implementation Plan

> Status: **LOCKED**. Branch: `feat/4-stage-tick`.
> Full replacement of the v2 graph-traversal engine. No parallel / flag-gate.
> §7 is the authoritative component behaviour oracle.

---

## 0. Time model (LOCKED)

| Unit | Meaning |
|---|---|
| **subtick / stage** | The atomic update step. |
| **new tick** | 4 subticks; the exposed API tick. |
| **old tick** | 2 new ticks = 8 subticks (v2 `Factory.tick`). |

- A component runs a phase FSM `P1 → P2 → P1 → P2 …`, toggling once per subtick.
  One new tick = `[P1, P2, P1, P2]`.
- API advances in **new ticks**. Item moves **1 belt cell per 2 new ticks**
  (old: 1 cell/old tick).
- Derived from **"4n 卡 0.5"**: old tick = 8 subticks; drift 1 subtick/old-tick;
  4 old ticks = 4 subtick drift = 1/2 old tick = half a phase. Therefore
  phase = 4 subticks → **4-stage model**.
- Consequence: all JSONC `ticks` values double (see §6).

---

## 1. Why the old engine is discarded (the topo-sort problem)

The v2 engine (`Graph.tick`, `simulation/graph.py:139`) re-traverses the full
topological order twice per old tick. Correctness **depends on traversal order**
to make `fulfill_requests` see pull requests posted by downstreams earlier in the
same pass. This is not just a performance issue — it is a correctness dead-end:

1. **Fidelity** — `AGENTS.md` TODO phenomena (`环的手性`, `4n 卡 0.5`, and 20
   failing JSONC cases) are *sub-tick / simultaneity-sensitive*. A single-pass
   overlay of fulfill+request cannot express a half-phase drift.
2. **The only reason topo sort exists is to order `phase1`'s bundled
   fulfil→request so they interlock correctly in one pass.** Once satisfy this
   coupling by snapshot/commit (§2.4), the sort is unnecessary.
3. **Edge-cutting breaks chirality** — `_build_order` (`graph.py:173`) cuts the
   placement-first→last edge in every cycle. This explicitly destroys the
   clockwise/counterclockwise preference that `环的手性` depends on.

The answer is **not** to fix the topo sort. It is to delete it.

---

## 2. Architecture: the subtick pipeline

### 2.1 Per-component phase state machine

- States: **P1** / **P2**, toggling every subtick.
- **P1**: `fulfill_requests` → `self_update` → `request_upstream` (the old `phase1`).
- **P2**: zero-tick forward (the old `phase2`; default no-op; `ProtocolStash` overrides it).
- Initial state: **parked at P1, not running**. The component enters the active
  set only when an item first reaches it (see §2.2).
- Because components are activated at different subticks, they naturally acquire
  **different phase offsets** — the candidate mechanism for the half-phase drift.

### 2.2 Activation gating (cache tier 1) — replaces topo-sort execution scoping

The engine maintains an **active set** — the only components executed per subtick.

- **Seed**: `DepotLoader` is active from the start (it has items to push). A
  `ProtocolStash` with pre-filled inventory is also active from the start.
- **Propagation**: at the end of each subtick commit, every active component
  marks its `downstreams` for activation. Those downstreams enter the active set
  at the **next** subtick, at P1.
- **Effect**: the active set grows along item-flow paths, exactly tracking which
  parts of the graph have been "reached." Components never touched by items never
  execute. This is the first tier of cache — making the engine run only the
  relevant sub-graph, with zero static analysis.

```
DepotLoader (active, subtick 0, P1)
    → marks Conveyor[0] pending
Conveyor[0] (active, subtick 1, P1)
    → marks Conveyor[1] pending
    …
```

### 2.3 Why topo sort is unnecessary

In the subtick pipeline, dependency resolution works as follows:

1. At subtick _t_, a downstream `D` (active, in P1) runs `request_upstream` and
   writes a pull request into its own **outbox** (not into the upstream's live
   state — see §2.4).
2. The outbox is committed at the end of subtick _t_. Upstream `U` sees the pull
   in the snapshot it reads at subtick _t+1_.
3. `U` resolves it at its **next P1** (which may be subtick _t+1_ or _t+2_,
   depending on phase offset).

The key property: **no component reads another component's live state.** Every
read goes through the snapshot. Every write goes through the outbox. Therefore
the order in which components execute within a single subtick is irrelevant —
each reads only the frozen state of the previous subtick. The pipeline's cadence
(subtick→commit→subtick) is the only ordering the system needs.

This eliminates the Kahn sort / edge-cut / `_build_order` in `graph.py` entirely.
The Graph shrinks to pass 1 (instantiation) + pass 2 (port connections) only.

### 2.4 Snapshot → commit per subtick — eliminates the three coupling points

Each subtick is executed in three phases:

1. **Read** — extract a frozen snapshot containing every active component's
   `can_pull()` result, buffer/slot occupancy, current `_distance_rr`, and the
   aggregate list of pull requests addressed to it (merging outboxes from the
   previous subtick).
2. **Step** — each active component runs its current `P1` or `P2` logic.
   **All state writes go to a per-component outbox** (new pull requests to
   upstreams, new RR indices, buffer/slot updates, item transfers). No component
   ever writes directly into another component's live state.
3. **Commit** — the engine merges outboxes: pull requests are delivered to their
   target components' state; RR indices / buffers / slots are atomically swapped
   in. The active set is updated (pending activations added). All live state for
   the next subtick is now frozen.

This eliminates the three coupling points from the old model by construction:
- `Converger.request_upstream` mutating upstream's `pull_requests` (`converger.py:53`)
- `Splitter.fulfill_requests` mutating `_distance_rr` mid-pass (`splitter.py:58`)
- `Conveyor._accept_pos` supporting multiple accepts per pass / `add_pull` LIFO (`conveyor.py:112`, `base.py:133`)

---

## 3. Distance-based routing — without topo sort

The *old* reason to keep topo sort was `topo_index` used by Splitter and
ProtocolStash for distance-priority RR. The *new* way: a simple **multi-source
BFS from sinks**.

### 3.1 BFS distance-to-sink

```
for each DepotUnloader (sink):
    queue.push(sink, distance=0)

while queue:
    (component, dist) = queue.pop()
    for each upstream of component:
        if not visited:
            component.distance_to_sink = dist + 1
            queue.push(upstream, dist + 1)
```

- Belt loops: BFS is shortest-path only and terminates — a loop cell gets the
  **minimum** distance from any sink, which is the correct routing metric (nearest
  sink wins).
- **Zero edge-cutting** — BFS reads distance, it does not break cycles.
- This runs **once** at engine initialisation (after Graph pass 2). It replaces
  everything in `graph._build_order`: the Kahn loop, the inline DFS cycle-breaker,
  the layer computation, and the final sort (`graph.py:152–276`).

### 3.2 `distance_to_sink` → the new `topo_index`

- `distance_to_sink` is stored as a per-component field.
- `finalize()` and `_build_distance_groups` still work exactly as before, now keyed on
  `distance_to_sink` instead of `topo_index`.
- Lower distance = nearer sink = higher routing priority — same semantics,
  computed without any sort or edge-cut.

---

## 4. Cache architecture

Cache is **not deferred** — activation gating is cache tier 1 and is part of the
engine from the start. The three tiers:

### Tier 1 — Activation gating (integral to the engine, §2.2)
Only components reached by items execute. Without this, the engine would execute
the full component list every subtick. This is the fundamental efficiency gain
over full-graph traversal.

### Tier 2 — Deactivation / parking
A component that stays idle (holds no item, has no pending pull request, and all
its neighbours are also stable) is **parked back to P1 and removed from the active
set**. It re-enters when the next item arrives. This is what keeps a
steady-state belt from running 4× per new tick forever. The exact deactivation
predicate is a tuning knob (§9).

### Tier 3 — Steady-state region memoisation
Stable sub-graphs (e.g. a full saturated belt segment) can cache their per-subtick
"null transform" (no state change) and be skipped at the dirty-check level before
reaching the component step. Invalidation: any item entering/exiting the region
marks it dirty, forcing re-eval for one subtick. This is a performance
optimisation implemented after correctness is verified.

---

## 5. What happens to `Graph`

| Pass | Fate |
|---|---|
| Pass 1 — instantiation (`graph.py:64–80`) | **Kept.** Iterates placements, creates component instances, builds `cell_origin`/`origin_cells`. |
| Pass 2 — port connections (`graph.py:82–127`) | **Kept.** Bilateral port matching, `add_link` calls, `_owner_downstreams` recording. |
| Pass 3 — Kahn sort + edge-cut + topo_index (`graph.py:129–276`) | **Deleted entirely.** Replaced by: BFS `distance_to_sink` (§3.1) + `Engine` (§2). |
| `graph.tick()` | **Deleted.** Replaced by `Engine.tick()`. |
| `graph.order` / `graph.order_coords` | **Deleted.** No longer meaningful — execution order is at the mercy of the subtick pipeline. |

### 5.1 New `Engine` class (`simulation/engine.py`)

```python
class Engine:
    components: list[Base]           # from Graph pass 1
    active: set[int]                 # component ids
    pending_activation: set[int]     # ids activating next subtick
    subtick: int                     # global monotonic counter
    snapshot: Snapshot               # frozen view for current subtick
    outboxes: dict[int, Outbox]      # per-component writes, merged at commit

    def tick() -> None:              # advance 4 subticks (= 1 new tick)
    def _subtick_advance() -> None:  # read snapshot → step active set → commit
```

### 5.2 `Factory` integration

- `Factory.__init__` still builds `Layout` + `Graph` (passes 1–2). It then calls
  `Engine(graph.components)`, runs BFS distance-to-sink, calls `comp.finalize()`
  on each component.
- `Factory.tick()` delegates to `self.engine.tick()`.
- `Factory.run(ticks)` default formula doubles: `max(self.engine.component_count * 4 + 20, 40)`.

---

## 6. Compatibility & test migration

- Oracle: `tests/units/**/*.jsonc`, 52 passing + 20 currently failing.
- Target: keep the 52 green; flip the 20.
- **`ticks` ×2**:
  - `integration` cases: `ticks` value ×2. Clean — end-state at an even tick
    boundary coincides with old tick boundary.
  - `temporal` / `observe` cases: sampled per-tick. Under new ticks they see
    intermediate sub-tick states. **Cannot be mechanically ×2** — hand-review
    each, updating observation windows and sequences.
  - `unit` / `hybrid` cases: direct API checks; `ticks` value likely unchanged
    (they set up standalone instances, not a factory).
- `Factory.run` default ticks doubles.
- Frontend `/api/tick`: advances 1 new tick. The frontend must account for 2×
  ticks per belt cell.

---

## 7. Component behaviour reference (authoritative)

This is the behavioural contract the new engine must reproduce. It documents the
**current on-disk implementation** as the source of truth.

### 7.1 Core protocol (`Base`, `units/base.py`)

- **Adjacency**: `add_link` populates `upstreams` / `downstreams` and
  `in_degree` / `out_degree` by `LinkType`.
- **Pull queue / priority**: `add_pull(requester)` inserts at the front
  (index 0) of `pull_requests`; consumers `pull_requests.pop(0)`. Net effect:
  the most recently registered requester is served first (**LIFO priority**).
- **`finalize()`**: snapshots `_original_downstreams`; sorts `downstreams` by
  `topo_index` (→ `distance_to_sink` under the new engine); builds
  `_downstream_groups` (ranges of equal topo_index) with parallel
  `_downstream_rr`; then calls `_build_distance_groups`.
- **`_build_distance_groups()`**: buckets `_original_downstreams` by topo_index,
  orders buckets **ascending** (nearest sink first). Connection order preserved
  within a bucket. `_distance_rr` starts at 0 per group.
- **`_owner_downstreams`**: downstreams this component connected during port
  matching; downstreams connected later by *other* components are "foreign."
- **`can_pull`** default `False`. **`self_update`** default no-op.
  **`_accept_item`** abstract.

### 7.2 Conveyor (`belt/conveyor.py`) — 1-in / 1-out, fixed-length FIFO

- Slot array: `slots[0]` = tail/exit, `slots[length-1]` = head/entry; `_count`.
- At most one downstream (assert on OUTPUT link).
- `can_pull`: tail occupied.
- `fulfill_requests`: if tail occupied and a request exists, pop tail and give
  to `pull_requests.pop(0)`; restore on reject.
- `self_update`: shift items one slot toward tail (i=1..length-1: if slot[i-1]
  empty and slot[i] full, move). One slot per invocation. Resets `_accept_pos`.
- `request_upstream`: if head empty and upstreams[0].can_pull, `add_pull(self)`.
- `_accept_item`: rejects if full; writes at `_accept_pos` backward from head.
  Supports multiple accepts per tick.

### 7.3 Splitter (`belt/splitter.py`) — 1-to-N, single-slot buffer

- `can_pull`: buffer occupied.
- `fulfill_requests` (grants **one** item):
  1. Buffer empty → clear pull_requests, return. No requests → return.
  2. **Foreign downstreams first**: serve the first requester not in `_owner_downstreams`.
  3. Iterate `_distance_groups` (nearest sink first); within a group, RR with
     **increment-before-select** (`rr=(rr+1)%n`, pick `group[rr]`); serve match.
  4. Nothing matched → clear pull_requests.
- `request_upstream`: if buffer empty, upstreams[0].can_pull → `add_pull(self)`.
- `_accept_item`: accept iff buffer empty.

> AGENTS.md claims Splitter overrides `_build_distance_groups` for Converger
> priority. **No such override exists in code.** Converger priority arises only
> from generic `distance_to_sink` grouping.

### 7.4 Converger (`belt/converger.py`) — N-to-1, single-slot buffer

- `can_pull`: buffer occupied.
- `fulfill_requests`: give buffer to `pull_requests.pop(0)`; restore on reject.
- `request_upstream`: if buffer occupied → skip. Remove self from every
  upstream's `pull_requests`. Then:
  - if any **shared** upstream (`out_degree > 1`) can pull → broadcast
    `add_pull(self)` to all upstreams that can pull;
  - else → `add_pull(self)` to the first upstream that can pull.
- `_accept_item`: accept iff buffer empty.

### 7.5 ProtocolStash (`depot_access/protocol_stash.py`) — buffer + Inventory(6×50), zero-tick

- `can_pull`: buffer occupied **or** inventory non-empty.
- `fulfill_requests`: saves pulls, distributes `available = (buffer?1:0) +
  inv.count()` across `_distance_groups` RR to pull-requesters; buffer first,
  then inventory; restores on reject.
- `request_upstream`: skip iff buffer occupied and inv full; else `add_pull`
  to every upstream that can pull.
- `_accept_item`: buffer if empty, else inventory if not full, else reject.
- `_p2` (zero-tick passthrough, was `phase2`): if buffer occupied, route to
  downstreams in distance-priority RR (honouring saved pull requests); if none
  accept, stash in inventory or keep in buffer.

### 7.6 DepotLoader (`depot_access/depot_loader.py`) — source, fixed item type

- `can_pull`: `inv.count(item_type) > 0`.
- `fulfill_requests`: pop one `item_type` from inv, give to
  `pull_requests.pop(0)`; push back on reject.
- `request_upstream`: no-op.
- `_accept_item`: always `False`.

### 7.7 DepotUnloader (`depot_access/depot_unloader.py`) — sink

- `can_pull`: `False`.
- `fulfill_requests`: no-op.
- `request_upstream`: upstreams[0].can_pull → `add_pull(self)`.
- `_accept_item`: `inv.push(item)`.

### 7.8 Item model (`items/`)

- **Item**: unique `id` + hashable `type`; hashes on `(id, type)`.
- **ItemStack**: single type, capacity (default 50), count. `pop` mints new Item
  with fresh id. `push` rejects on type mismatch or full.
- **Inventory**: fixed slot array. `push` → first compatible/empty slot. `pop(type)`
  → first matching slot, clears emptied slot. `count(type)`. `is_full` → every
  slot present and at capacity. Global inventory = 50 slots; ProtocolStash = 6.

### 7.9 Stubs (raise `NotImplementedError`)

`BeltBridge`, `ItemControlPort`, all pipe / power / production / conduit /
fluid-tank units — keep as stubs unchanged.

---

## 8. Implementation plan (ordered, no flag-gate)

### Step 1 — Scaffold `Engine` + outbox model (`simulation/engine.py`)
- `Engine` class with `components`, `active`/`pending_activation` sets, `subtick`
  counter, per-component `Outbox` dataclass.
- `Snapshot` read helper: collects `can_pull`, buffer/slot snapshots, aggregated
  pull requests from previous commit.
- `tick()` runs 4 subticks.
- **No integration with Factory yet** — tested with unit-mode mocks.

### Step 2 — Add FSM + outbox hooks to `Base`
- `_phase: int` (0=P1, 1=P2), `_active: bool`, `activate()`.
- `step(subtick, snapshot, outbox)` dispatches to `_run_p1` / `_run_p2`.
- `_run_p1`: `fulfill_requests()` → `self_update()` → `request_upstream()`. All
  cross-node writes go to `outbox` (pull requests are `outbox.add_pull(target_id)`,
  not direct `target.add_pull(self)`).
- `_run_p2`: `phase2()` (only ProtocolStash has logic).
- Old `phase1`/`phase2` kept temporarily as implementation reference; deleted
  after all components verified.

### Step 3 — Wire Engine into Factory (replace `graph.tick`)
- `Factory.__init__` builds Graph passes 1–2, then creates `Engine(graph.components)`.
- Run BFS distance-to-sink (§3.1).
- `comp.finalize()` on each component (now keyed on `distance_to_sink`).
- `Factory.tick()` → `self.engine.tick()`.
- **Delete** `graph.tick()`, `graph.order`, `graph.order_coords`,
  `graph._build_order` (lines 129–276 of `graph.py`).
- **Delete** `Graph.tick` (lines 139–150).
- **Delete** `topo_index` field from Base; add `distance_to_sink`.

### Step 4 — Components: migrate writes from direct → outbox
- Every `target.add_pull(self)` → `outbox.add_pull(target_id)`.
- Every `target._accept_item(item)` → `outbox.transfer(target_id, item)`.
- Every `_distance_rr` mutation stays local but commits to outbox for snapshot.
- `Converger.request_upstream`'s cross-node pull_requests removal becomes an
  outbox-driven diff: the engine merges outboxes after collecting all.

### Step 5 — Test ×2 migration
- Script: `tools/migrate_ticks.py` → for each `integration` case, multiply
  `"ticks"` by 2.
- Hand-review `temporal`/`observe` cases; list the per-case decisions.

### Step 6 — Validation
- Run `uv run pytest -k` on the 52 previously-passing cases — must be green.
- Run the 20 previously-failing cases — should now pass or progress.
- Add subtick-level observation harness to verify "4n 卡 0.5" drift.
- Run `uv run mypy .`.

---

## 9. Open questions

1. **P1/P2 exact behavior at subtick granularity** — the working model (§2.1)
   maps P1 to fulfill+update+request and P2 to zero-tick forward. Confirm this
   split against observed game behavior; it may need sub-tuning.
2. **Belt-advance cadence** — which subtick triggers the 1-cell shift (once per
   8 subticks = once per old tick). Conveyor maintains an internal counter mod
   some value.
3. **Deactivation predicate** — the exact condition for a component to park
   (idle) and leave the active set. Candidate: holds no item, no pending pull
   request, all downstreams parked, and no item in transit toward it.
4. **Chirality** — does snapshot + subtick ordering alone reproduce `环的手性`,
   or is an explicit tiebreak needed?
5. **`temporal`/`observe` re-timing** — per-case decisions for non-mechanical
   migrations.
6. **Frontend `/api/tick`** — the API now delivers 1 new tick (4 subticks) per
   call. Does the frontend need adaptation (2× call rate), or is a new subtick
   API needed?
