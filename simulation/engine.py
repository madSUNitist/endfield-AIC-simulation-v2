"""Subtick-sum scheduler engine replacing the old graph-traversal tick.

Drives a deterministic 4-subtick pipeline per tick.  Each component runs a
phase state machine (P1 / P2) toggling every subtick; activation propagates
along item-flow edges so only the reached sub-graph executes.

Per-subtick cycle:

1. Activate any pending components.
2. Step every active component in placement order, dispatching to the
   component's current phase.  Components read their own pre-subtick live
   state (the implicit snapshot) and accumulate *cross-component* writes
   into a per-component :class:`Outbox`.
3. Commit: the engine delivers pull requests and removals from every outbox
   to their targets.  Activation propagates from active components to their
   downstreams.

Because no component ever writes directly into another component's state
during a subtick the execution order is deterministic (placement order)
but correctness does not depend on it — the only coupling that remains
intra-subtick is a provider calling ``target._accept_item(item)``, which
is bounded by the placement-order tiebreak.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.units.base import Base


class Outbox:
    """Per-component buffer for cross-component writes during one subtick.

    Instead of mutating a neighbour's ``pull_requests`` directly, a component
    writes into its own *outbox*.  The engine merges all outboxes at commit
    time in a deterministic order (removals first, then additions).
    """

    __slots__ = ("pull_adds", "pull_removes")

    def __init__(self) -> None:
        self.pull_adds: list[Base] = []
        self.pull_removes: list[Base] = []

    def add_pull(self, upstream: Base) -> None:
        """Request that *upstream* receive a pull from this component."""
        self.pull_adds.append(upstream)

    def remove_pull(self, upstream: Base) -> None:
        """Request that this component be removed from *upstream*'s pull queue."""
        self.pull_removes.append(upstream)


class Engine:
    """Subtick-pipeline scheduler for the 4-stage tick.

    Owns the active set, the global subtick counter, and the commit cycle.
    """

    __slots__ = ("components", "_active", "_pending", "_subtick", "_outboxes")

    def __init__(self, components: list[Base]) -> None:
        self.components = components
        self._active: set[int] = set()
        self._pending: set[int] = set()
        self._subtick: int = 0
        self._outboxes: dict[int, Outbox] = {c.id: Outbox() for c in components}

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------

    def tick(self) -> None:
        """Advance one new tick (4 subticks)."""
        for _ in range(4):
            self._subtick_advance()

    # ------------------------------------------------------------------
    # activation
    # ------------------------------------------------------------------

    def seed_active(self, *comp_ids: int) -> None:
        """Mark sources / pre-filled components as active from the start.

        Should be called once after construction, before the first subtick.
        """
        for cid in comp_ids:
            self._active.add(cid)
            self._ensure_component(cid)._active = True
            self._ensure_component(cid)._phase = 0  # parked P1

    # ------------------------------------------------------------------
    # subtick cycle
    # ------------------------------------------------------------------

    def _subtick_advance(self) -> None:
        # --- activate pending components ---
        if self._pending:
            for cid in self._pending:
                comp = self._ensure_component(cid)
                comp._active = True
                comp._phase = 0  # always start at P1
            self._active |= self._pending
            self._pending.clear()

        # --- step: P1 first, then P2 (matching old phase1→phase2 order) ---
        p1_ids = sorted(cid for cid in self._active if self._ensure_component(cid)._phase == 0)
        p2_ids = sorted(cid for cid in self._active if self._ensure_component(cid)._phase == 1)
        for cid in p1_ids + p2_ids:
            comp = self._ensure_component(cid)
            if not comp._active:
                continue
            outbox = self._outboxes[cid]
            comp.step(self._subtick, outbox)

        # --- commit ---
        self._commit()

        # --- advance clock ---
        self._subtick += 1

    def _commit(self) -> None:
        for cid in list(self._active):
            comp = self._ensure_component(cid)
            if not comp._active:
                continue
            outbox = self._outboxes[cid]

            # 1.  removals  (Converger clearing itself from upstream queues)
            for up in outbox.pull_removes:
                up.pull_requests = [r for r in up.pull_requests if r is not comp]

            # 2.  additions  (pull requests delivered to upstreams, LIFO)
            for up in outbox.pull_adds:
                up.pull_requests.insert(0, comp)

            # 3.  activation propagation
            for down in comp.downstreams:
                if not down._active:
                    self._pending.add(down.id)

            # 4.  clear outbox for next subtick
            outbox.pull_adds.clear()
            outbox.pull_removes.clear()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _ensure_component(self, cid: int) -> Base:
        """Index-safe component lookup (id is placement index)."""
        return self.components[cid]
