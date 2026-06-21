# Design Skeleton — Cache-Based 4-Stage Tick

> Status: **DRAFT / skeleton**. Branch: `feat/4-stage-tick`.
> Blocked on input: the game's authoritative per-stage definition (see §3, §6).
> No implementation yet — this document fixes scope and open questions only.

## 0. Why 4 stages (not 8)

The driving phenomenon is **"4n 卡 0.5"**: over 4 ticks the system drifts by
exactly **0.5 tick** (half a phase). Reading this back:

- A tick contains **8 subticks**.
- Each tick drifts by **1 subtick** (= 1/8 tick); after 4 ticks the drift is
  4 subticks = **1/2 tick**, i.e. exactly half a phase.
- Therefore **one phase = 4 subticks = 1/2 tick**, and a tick is **2 phases**.

So the granular unit we model is the **phase = 4 subticks**, and each subtick is
one **stage**. The engine is a **4-stage** model (4 stages per phase), which maps
cleanly onto the original two-phase tick: each of the old phases (`phase1` /
`phase2`) corresponds to one 1/2-tick phase, now resolved into 4 stages.

## 1. Motivation

The current engine re-traverses the full topological order **twice every tick**
(`Graph.tick`, `simulation/graph.py:139`) — one pass per phase. Correctness
depends on the traversal order coinciding with an implicit request→grant
ordering. Two problems:

1. **Fidelity** — several game phenomena recorded in `AGENTS.md` (TODO list:
   `环的手性`, `4n 卡 1` / `4n 卡 0.5`) and reproduced imperfectly in
   `expr_results/` are *sub-tick / simultaneity-sensitive*; the coarse 2-phase
   model cannot express a half-phase drift. As of the branch point, 20 JSONC
   cases fail (converger RR, stash placement-order priority) — this is the
   trigger for the rewrite, not a regression to fix in the old model.
2. **Cost** — full-graph traversal per tick is wasteful when most of the graph
   is in steady state. A cache-based model recomputes only dirty regions.

Goal: replace full-graph traversal with a **cache-based** update model whose
phase is decomposed into **exactly 4 stages (subticks)** mirroring the game.

## 2. Current model recap (what we are replacing)

`Base.phase1` (`simulation/units/base.py:153`) bundles three sub-steps inside one
sink→source pass: `fulfill_requests()` + `self_update()` + `request_upstream()`.
`Base.phase2` (`base.py:163`) is the source→sink zero-tick forward pass (only
`ProtocolStash` overrides it, `protocol_stash.py:144`). Each phase is 1/2 tick =
4 subticks; we are refining each phase into 4 explicit stages.

### Coupling points that block a clean stage split (must be removed)

- `Converger.request_upstream` directly rewrites an upstream's `pull_requests`
  list (`converger.py:53`) — cross-node, order-sensitive mutation.
- `Splitter.fulfill_requests` mutates `_distance_rr` and pops `pull_requests`
  mid-pass (`splitter.py:58`).
- `Conveyor._accept_pos` supports multiple accepts per tick (`conveyor.py:112`);
  `Base.add_pull` is LIFO insertion (`base.py:133`).

These all rely on "who runs first in the pass". The cache-based model must make
each stage a pure function over the **previous stage's frozen snapshot**
(double buffering), so stage results are independent of iteration order.

## 3. The 4 stages per phase (PLACEHOLDER — awaiting game spec)

A phase = 4 subticks = 4 stages; a tick = 2 phases = 8 subticks. Each stage must
be specified along four axes: **(a)** traversal direction / order-independence,
**(b)** operation, **(c)** reads snapshot vs live state, **(d)** iterates-to-fixpoint?

| Stage (subtick) | Name (TBD) | Operation (TBD) | Reads | Direction | Fixpoint? |
|---|---|---|---|---|---|
| 1 | TBD | TBD | — | — | — |
| 2 | TBD | TBD | — | — | — |
| 3 | TBD | TBD | — | — | — |
| 4 | TBD | TBD | — | — | — |

Open: confirm whether both phases run the **same** 4-stage program or two
different 4-stage programs (forward vs. zero-tick phase). The half-phase drift in
"4n 卡 0.5" suggests the two phases are offset by exactly one phase (4 subticks).

## 4. Cache model draft

- **Dirty set**: a component is dirty when its input/output port state, buffer,
  or a neighbour's availability changed last stage. Only dirty components run the
  per-stage update; clean steady-state regions are skipped.
- **What is cached**: resolved request→grant decisions and propagation closures
  for stable sub-graphs; invalidate on dirty-flag propagation across ports.
- **Snapshot/commit**: each stage reads a frozen snapshot of the prior stage and
  writes into a fresh buffer; commit swaps buffers at stage end. This is what
  makes stages order-independent and lets the 4-stage semantics match the game.
- Open: caching granularity (per-component vs per-region), invalidation
  propagation rules, interaction with cycles (belt loops) — see §6.

## 5. Compatibility constraints

- The JSONC assertion suite (`tests/units/**/*.jsonc`) is the behavioural oracle.
  After the rewrite, run a **per-case end-state diff**; the 52 currently-passing
  cases should stay green, and the 20 currently-failing cases are the targets
  expected to flip to green once the 4-stage semantics are correct.
- If any currently-passing case changes end-state, decide per case: stage
  semantics bug vs. the old test encoding wrong behaviour.
- Public surface to preserve: `Factory.tick()` / `Factory.run()` and the
  `/api/tick` contract used by the frontend.

## 6. Open questions (blockers)

1. **The 4-stage (subtick) definitions** — exact name, operation, ordering, and
   order-dependence of each stage within a phase (fills §3).
2. Do the two phases share one 4-stage program, and what is the exact half-phase
   offset that produces "4n 卡 0.5"?
3. Where does zero-tick forwarding (current `phase2`) live among the stages, and
   does any stage iterate to a fixpoint?
4. Cycle handling: how do belt loops behave under the staged/cached model
   (relates to the unreproduced `环的手性`)?
5. Cache invalidation contract: which state changes mark which neighbours dirty?
