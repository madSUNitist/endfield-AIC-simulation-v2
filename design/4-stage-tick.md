# Design — Cache-Based 4-Stage Tick

> Status: **DESIGN LOCKED, implementation pending**. Branch: `feat/4-stage-tick`.
> §0–§6 fix the model and the plan; §7 is the authoritative behaviour reference
> the new engine must reproduce; §8 lists the remaining open questions.

## 0. Time model (LOCKED)

| Unit | Meaning |
|---|---|
| **subtick / stage** | The atomic update step. |
| **new tick** | `4 subticks` = the externally exposed tick. |
| **old tick** | `2 new ticks` = `8 subticks` (the v2 / current `Factory.tick`). |

- A component runs a phase state machine `P1 → P2 → P1 → P2 …`, toggling **once
  per subtick**. One new tick = `[P1, P2, P1, P2]` ("1 tick = 4 phase").
- Externally the engine advances in **new ticks**. An item moves **1 belt cell
  per 2 new ticks** (the old "1 cell per old tick").
- Derivation from **"4n 卡 0.5"**: 1 old tick = 8 subticks; the system drifts
  1 subtick/old-tick, so after 4 old ticks the drift is 4 subticks = 1/2 old
  tick = half a phase. Hence phase = 4 subticks and the model is **4-stage**.

Consequence for tests: exposed tick is redefined (new tick = old 1/2 tick), so
**all JSONC `ticks` values are doubled** (see §5).

## 1. Motivation

The current engine re-traverses the full topological order **twice per old tick**
(`Graph.tick`, `simulation/graph.py:139`). Correctness depends on the traversal
order coinciding with an implicit request→grant ordering. Two problems:

1. **Fidelity** — phenomena in `AGENTS.md` TODO (`环的手性`, `4n 卡 1` /
   `4n 卡 0.5`), imperfectly reproduced in `expr_results/`, are *sub-tick /
   simultaneity-sensitive*; the coarse 2-phase model cannot express a half-phase
   drift. At the branch point 20 JSONC cases fail (converger RR, stash
   placement-order priority) — the trigger for the rewrite.
2. **Cost** — full-graph traversal is wasteful when most of the graph is in
   steady state. The new model only updates components that items have reached.

## 2. Current model recap (what we are replacing)

`Base.phase1` (`base.py:153`) bundles three sub-steps in one sink→source pass:
`fulfill_requests()` + `self_update()` + `request_upstream()`.
`Base.phase2` (`base.py:163`) is the source→sink zero-tick forward pass (only
`ProtocolStash` overrides it, `protocol_stash.py:144`).

### Coupling points that block a clean stage split (must be removed)

- `Converger.request_upstream` rewrites an upstream's `pull_requests` list
  (`converger.py:53`) — cross-node, order-sensitive mutation.
- `Splitter.fulfill_requests` mutates `_distance_rr` and pops `pull_requests`
  mid-pass (`splitter.py:58`).
- `Conveyor._accept_pos` allows multiple accepts per pass (`conveyor.py:112`);
  `Base.add_pull` is LIFO insertion (`base.py:133`).

All rely on "who runs first in the pass". The new model makes each subtick a pure
function over the **previous subtick's frozen snapshot** (double buffering), so
results are independent of iteration order.

## 3. The 4-stage model (LOCKED)

### 3.1 Per-component phase state machine

- Each component owns a phase FSM with two states: **P1** and **P2**.
- It is **parked at P1 and does not advance** until an item first propagates to
  it. From the first arrival onward it advances one state per subtick.
- **P1** carries the semantics of the old `phase1` (fulfil downstream requests →
  advance internal state → request upstream).
- **P2** carries the semantics of the old `phase2` (zero-tick forward).
- Because components are activated at different subticks (when items first reach
  them), they acquire **different phase offsets** — the candidate mechanism
  behind the half-phase drift of "4n 卡 0.5".

### 3.2 Activation gating

- The scheduler maintains an **active set**. A component enters it when an item
  first reaches it (or it is an always-on source that has items to push).
- Each subtick only the active set runs — "一次只需要更新部分组件".
- v1: once active, stay active (correct but not yet optimised). Deactivation /
  re-parking to P1 on going idle is a §4 (cache) optimisation.

### 3.3 Snapshot → commit per subtick

- Each subtick: read the frozen snapshot of the previous subtick's state, compute
  each active component's next state into a fresh buffer, then **commit** (swap).
- This removes the three coupling points in §2 by construction.

## 4. Cache (deferred — "correct first, cache later")

- **Activation gating (§3.2) is core**, already restricting work to reached
  components.
- **Deactivation / parking**: a component returns to idle (parked P1, removed
  from active set) when it holds no item and has no pending request; re-activated
  on the next inbound item. This recovers steady-state savings.
- **Memoisation**: cache resolved request→grant decisions / propagation closures
  for stable sub-graphs; invalidate via dirty-flag propagation across ports when
  buffer occupancy or neighbour availability changes.
- Granularity (per-component vs per-region) and the invalidation contract are
  decided in the cache phase, after correctness is locked against §5.

## 5. Compatibility

- Oracle: the JSONC suite (`tests/units/**/*.jsonc`). Target: keep the 52
  currently-passing cases green; flip the 20 currently-failing ones.
- **`ticks` ×2 migration** (exposed tick redefined):
  - `integration` (end-state) cases: multiply `ticks` by 2 — clean, because the
    new model's even-subtick boundary coincides with the old tick boundary.
  - `temporal` / `observe` cases: sampled per tick. Under new ticks they observe
    sub-tick intermediate states the old model never exposed, so their sequences
    change meaning and **cannot be mechanically ×2** — review case-by-case.
  - `Factory.run` default tick count (`max(len(order)*2+10, 20)`, `factory.py`)
    is in old-tick units → ×2.
- Public surface: `Factory.tick()` / `Factory.run()` and `/api/tick` now advance
  one **new** tick; the frontend speed/step mapping must account for 2× ticks per
  belt cell.

## 6. Implementation plan

1. **New engine module, parallel to old.** Add `simulation/engine/` (subtick
   scheduler + active set + snapshot/commit) without deleting `graph.tick`; gate
   behind a flag so both can run for diffing.
2. **`Base` refactor.** Replace `phase1`/`phase2` hooks with: a phase-FSM field,
   `step()` dispatching to `_p1()` / `_p2()`, and pure snapshot-reading +
   buffered-write helpers. Keep `fulfill_requests` / `request_upstream` /
   `self_update` / `_accept_item` semantics but route them through the buffer.
3. **Scheduler.** Drive a global subtick counter; each subtick runs the active
   set in their current phase over a frozen snapshot, then commits and toggles
   FSMs; manage activation (seed on first item arrival).
4. **Cycle handling without edge-cutting.** Drop the placement-first→last edge
   cut in `graph._build_order` for the new engine; loops resolve via snapshot
   reads, and **chirality** emerges from subtick ordering + deterministic
   tiebreak (target: reproduce `环的手性`).
5. **Belt-advance cadence.** Conveyor still moves 1 cell per old tick = once per
   8 subticks; pin which subtick performs the shift (initial guess, tuned to
   match observations).
6. **Test migration.** Script the `ticks ×2` rewrite for `integration` cases;
   hand-review `temporal`/`observe` cases; keep `unit`/`hybrid` cases as direct
   API checks.
7. **Validation.** Parallel diff new vs old engine on the 52 passing cases;
   add a **subtick-level observation harness** to verify the "4n 卡 0.5" drift;
   then run `uv run mypy .` + `uv run pytest`.

## 7. Current component behaviour reference (authoritative)

This section is the behavioural contract the new engine must reproduce. It
documents the **current on-disk implementation** as the source of truth.

### 7.1 Core protocol (`Base`, `units/base.py`)

- **Adjacency**: `add_link` populates `upstreams` / `downstreams` and
  `in_degree` / `out_degree` by `LinkType`.
- **Pull queue / priority**: `add_pull(requester)` inserts at the **front**
  (index 0) of `pull_requests`; consumers `pull_requests.pop(0)`. Net effect:
  **the most recently registered requester is served first (LIFO priority)**.
- **`finalize()`** (after topo sort): snapshots `_original_downstreams`; sorts
  `downstreams` by `topo_index`; builds `_downstream_groups` (index ranges of
  equal `topo_index`) with parallel `_downstream_rr`; then `_build_distance_groups`.
- **`_build_distance_groups()`**: buckets `_original_downstreams` by `topo_index`
  and orders buckets **ascending** (`_distance_groups`). Lower `topo_index` =
  **nearer a sink = higher routing priority**. Connection order is preserved
  within a bucket; `_distance_rr` starts at 0 per group.
- **`topo_index`**: layer = distance to sink (sinks = 0), computed in
  `graph._build_order`.
- **`_owner_downstreams`**: downstreams this component connected during graph
  pass 2; downstreams connected later by *other* components are "foreign".
- **Tick hooks (current)**: `phase1` = `fulfill_requests` + `self_update` +
  `request_upstream`; `phase2` = no-op by default. `can_pull` default `False`;
  `self_update` default no-op; `_accept_item` abstract.

### 7.2 Conveyor (`belt/conveyor.py`) — 1-in / 1-out, fixed-length FIFO

- Slot array: `slots[0]` = tail/exit, `slots[length-1]` = head/entry; `_count`.
- **At most one downstream** (asserted on `OUTPUT` link).
- `can_pull`: tail (`slots[0]`) occupied.
- `fulfill_requests`: if tail occupied **and** a request exists, pop the tail and
  give it to `pull_requests.pop(0)`; **restore** the tail slot if rejected.
- `self_update`: shift items one slot toward the tail (scan `i=1..length-1`: if
  `slots[i-1]` empty and `slots[i]` full, move it down). **One slot per tick**,
  relative order preserved, compaction toward exit. Resets `_accept_pos`.
- `request_upstream`: if head empty and `upstreams[0].can_pull()`, `add_pull(self)`.
- `_accept_item`: rejects if full; otherwise writes at `_accept_pos` working
  backward from the head, so **multiple accepts per tick** are supported.

### 7.3 Splitter (`belt/splitter.py`) — 1-to-N, single-slot buffer

- `can_pull`: buffer occupied.
- `fulfill_requests` (grants **one** item):
  1. If buffer empty → clear `pull_requests`, return. If no requests → return.
  2. **Foreign downstreams first**: the first requester not in
     `_owner_downstreams` is served, then return.
  3. Otherwise iterate `_distance_groups` (**nearest sink first**); within a
     group use round-robin with **increment-before-select**
     (`rr=(rr+1)%n`, then pick `group[rr]`); serve the matching requester, return.
  4. If nothing matched → clear `pull_requests`.
- `request_upstream`: if buffer empty and `upstreams[0].can_pull()`, `add_pull(self)`.
- `_accept_item`: accept iff buffer empty.
- **Note / doc gap**: `AGENTS.md` "Converger Priority" claims Splitter overrides
  `_build_distance_groups` to force Convergers highest. **No such override exists
  in code** — converger priority arises only from generic `topo_index` distance
  grouping. Reproduce the code, not the stale doc.

### 7.4 Converger (`belt/converger.py`) — N-to-1, single-slot buffer

- `can_pull`: buffer occupied.
- `fulfill_requests`: give buffer to `pull_requests.pop(0)`; restore on reject.
- `request_upstream`: if buffer occupied → skip. First **remove `self` from every
  upstream's `pull_requests`**. Then:
  - if any **shared** upstream (`out_degree > 1`) can pull → broadcast
    `add_pull(self)` to **all** upstreams that can pull (insert-order/LIFO
    priority decides who actually delivers);
  - else (all dedicated) → `add_pull(self)` to the **first** upstream that can
    pull, and return.
- `_accept_item`: accept iff buffer empty.

### 7.5 ProtocolStash (`depot_access/protocol_stash.py`) — buffer + Inventory(6×50), zero-tick

- `can_pull`: buffer occupied **or** inventory non-empty.
- `fulfill_requests`: saves `_saved_pull_requests`; computes
  `available = (buffer?1:0) + inv.count`; distributes across `_distance_groups`
  (nearest sink first) with per-group RR, only to requesters in the saved set;
  draws from buffer first then inventory; restores on reject; leftover returns to
  buffer (or inventory).
- `request_upstream`: skip iff buffer occupied **and** inventory full; otherwise
  `add_pull(self)` to **every** upstream that can pull.
- `_accept_item`: into buffer if empty, else into inventory if not full, else reject.
- `phase2` (**zero-tick passthrough**): if the buffer holds an item, route it to
  downstreams in distance-priority RR (honouring saved pull requests); if none
  accept, push to inventory (or keep in buffer if inventory full). This is the
  "skip the buffer when a downstream can take it immediately" behaviour.

### 7.6 DepotLoader (`depot_access/depot_loader.py`) — source, fixed item type

- `can_pull`: `inv.count(item_type) > 0`.
- `fulfill_requests`: if a request exists, pop one `item_type` from the inventory
  and give to `pull_requests.pop(0)`; push back on reject.
- `request_upstream`: no-op (it is a source).
- `_accept_item`: always `False` (never accepts).

### 7.7 DepotUnloader (`depot_access/depot_unloader.py`) — sink

- `can_pull`: `False`.
- `fulfill_requests`: no-op.
- `request_upstream`: if `upstreams[0].can_pull()`, `add_pull(self)`.
- `_accept_item`: `inv.push(item)` (succeeds unless inventory full).

### 7.8 Item model (`items/`)

- **Item**: unique `id` + hashable `type`; hashes on `(id, type)`.
- **ItemStack**: single `type`, `capacity` (default 50), `count`. `pop` mints a
  **new** `Item` with a fresh id; `push` rejects on type mismatch or when full.
- **Inventory**: fixed slot list. `push` → first compatible (same type, not full)
  or empty slot (new stack capacity 50). `pop(type)` → first matching slot,
  clearing emptied slots. `count(type)` totals across slots. `is_full` → every
  slot present **and** at capacity. Factory global inventory = 50 slots;
  ProtocolStash inventory = 6 slots.

### 7.9 Stubs (raise `NotImplementedError`)

`BeltBridge`, `ItemControlPort`, and all pipe / power / production / conduit /
fluid-tank units are stubs. The new engine need not implement them but must not
regress their stub status.

## 8. Open questions

1. **Exact P1/P2 operation split at subtick granularity** — confirm the precise
   per-subtick semantics against observations (§3.1 is the working model).
2. **Belt-advance subtick** — which of the 8 subticks performs the 1-cell shift
   (§6.5).
3. **Chirality** — does snapshot + subtick ordering alone reproduce `环的手性`,
   or is an explicit tiebreak rule needed (§6.4)?
4. **Deactivation predicate** — exact idle condition for re-parking (§4).
5. **`temporal`/`observe` re-timing** — per-case decisions for the non-mechanical
   migrations (§5).
