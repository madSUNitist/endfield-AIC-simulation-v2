import type { Placement, PlacementMode, GhostData, Rotation } from "./types.js";
import * as Renderer from "./renderer.js";
import { getSelectedItemType } from "./palette.js";

// ── Types ──────────────────────────────────────────────────────────

interface TypeMeta {
    coverage: [number, number];
    ports: { type: string; offset: [number, number]; direction: string }[];
}

// ── Direction helpers ──────────────────────────────────────────────

const DIR_VEC: Record<string, [number, number]> = {
    up:    [0, -1],
    down:  [0,  1],
    left:  [-1, 0],
    right: [ 1, 0],
};

const VEC_DIR: Record<string, string> = {
    "0,-1": "up",
    "0,1":  "down",
    "-1,0": "left",
    "1,0":  "right",
};

const DIR_IN_SEQ: string[] = ["up", "right", "down", "left"];
const DIR_OUT_SEQ: string[] = ["down", "left", "up", "right"];

const ROT_SEQ: Rotation[] = ["ROT_0", "ROT_1", "ROT_2", "ROT_3"];

// ── Vec rotation (port offsets & direction vectors) ─────────────────

function rotateVec(x: number, y: number, rot: Rotation): [number, number] {
    switch (rot) {
        case "ROT_0": return [x, y];
        case "ROT_1": return [-y, x];
        case "ROT_2": return [-x, -y];
        case "ROT_3": return [y, -x];
    }
}

function rotateDir(dir: string, rot: Rotation): string {
    const v = DIR_VEC[dir] ?? [0, 0];
    const [rx, ry] = rotateVec(v[0], v[1], rot);
    return VEC_DIR[`${rx},${ry}`] ?? dir;
}

/**
 * Direction from A to B (must be axis-aligned).
 * @returns Direction string or null if not axis-aligned.
 */
function segmentDir(A: [number, number], B: [number, number]): string | null {
    const dx = B[0] - A[0];
    const dy = B[1] - A[1];
    if (dx === 0 && dy < 0) return "up";
    if (dx === 0 && dy > 0) return "down";
    if (dx < 0 && dy === 0) return "left";
    if (dx > 0 && dy === 0) return "right";
    return null;
}

/**
 * Return directions that would form a forbidden extension for
 * direction_in / direction_out based on the existing waypoints.
 */
function forbiddenDirs(waypoints: [number, number][]):
    { inExcluded: string | null; outExcluded: string | null } {
    if (waypoints.length < 2) return { inExcluded: null, outExcluded: null };

    const firstSeg = segmentDir(waypoints[0], waypoints[1]);
    const lastSeg = segmentDir(waypoints[waypoints.length - 2],
                               waypoints[waypoints.length - 1]);
    const lastOpp = lastSeg
        ? DIR_VEC[lastSeg]
            ? VEC_DIR[`${-DIR_VEC[lastSeg][0]},${-DIR_VEC[lastSeg][1]}`]
            : null
        : null;
    return { inExcluded: firstSeg, outExcluded: lastOpp };
}

/**
 * Check whether placing `next` as the first waypoint (second click) is
 * allowed given direction_in. The segment direction must not equal
 * direction_in (would extend into the entry direction).
 */
function firstSegAllowed(start: [number, number], next: [number, number],
                         dirIn: string): boolean {
    const d = segmentDir(start, next);
    return d !== dirIn;
}

/**
 * Step forward once in a cyclic direction sequence.
 * @param current - Current direction.
 * @param seq - Cyclic array of directions.
 * @returns The next direction in the cycle.
 */
function nextInSeq(current: string, seq: string[]): string {
    const idx = seq.indexOf(current);
    return seq[(idx + 1) % 4];
}

/**
 * Find the next allowed direction in a cyclic sequence, skipping one.
 * @param current - Current direction.
 * @param excluded - Direction to skip, or null.
 * @param seq - Cyclic array of directions.
 * @returns The first non-excluded direction found.
 */
function nextValidDir(current: string, excluded: string | null,
                      seq: string[]): string {
    if (!excluded) return current;
    const idx = seq.indexOf(current);
    for (let i = 1; i <= 4; i++) {
        const candidate = seq[(idx + i) % 4];
        if (candidate !== excluded) return candidate;
    }
    return current; // all four blocked (shouldn't happen)
}

// ── Metadata ────────────────────────────────────────────────────────

let typeColors: Record<string, string> = {};
let typeMeta: Record<string, TypeMeta> = {};

/**
 * Set per-type colour map for ghost rendering.
 * @param colors - Type string → hex colour.
 */
export function setTypeColors(colors: Record<string, string>): void {
    typeColors = colors;
}

/**
 * Set per-type metadata (coverage, ports) for ghost rendering.
 * @param meta - Type string → TypeMeta.
 */
export function setTypeMeta(meta: Record<string, TypeMeta>): void {
    typeMeta = meta;
}

// ── State ──────────────────────────────────────────────────────────

let mode: PlacementMode = { mode: "idle" };
let placements: Placement[] = [];
let lastHoverCell: [number, number] | null = null;
let onCommit: ((p: Placement[]) => Promise<void> | void) | null = null;

/**
 * Initialise the placement state machine.
 * @param cb - Called when placements change (user clicked or committed).
 */
export function init(cb: (p: Placement[]) => Promise<void> | void): void {
    onCommit = cb;
}

/**
 * Replace the current placement list.
 * @param p - New array of placements.
 */
export function setPlacements(p: Placement[]): void {
    placements = [...p];
}

/**
 * Return a copy of the current placements.
 * @returns Current placement array.
 */
export function getPlacements(): Placement[] {
    return placements;
}

/**
 * Return the current placement-mode state.
 * @returns The active PlacementMode.
 */
export function getMode(): PlacementMode {
    return mode;
}

/**
 * True when conveyor placement has at least one waypoint.
 * @returns Whether a conveyor path is partially placed.
 */
export function hasWaypoints(): boolean {
    return mode.mode === "conveyor" && mode.waypoints.length >= 1;
}

/**
 * Commit the current placement or cancel.
 * Called from the Escape key handler.
 */
export async function handleCommit(): Promise<void> {
    if (mode.mode === "conveyor" && mode.waypoints.length >= 1) {
        await commitConveyor();
    } else {
        cancel();
    }
}

// ── expandWaypoints (TS port of Python _expand) ─────────────────────

/**
 * Expand a list of waypoints into every grid cell along the path.
 * @returns Relative offset cells covering the full polyline.
 */
function expandWaypoints(waypoints: [number, number][]): [number, number][] {
    const cells: [number, number][] = [];
    if (waypoints.length === 0) return cells;
    const [ox, oy] = waypoints[0];
    for (let i = 1; i < waypoints.length; i++) {
        const [ax, ay] = waypoints[i - 1];
        const [bx, by] = waypoints[i];
        const dx = Math.max(-1, Math.min(1, bx - ax));
        const dy = Math.max(-1, Math.min(1, by - ay));
        const steps = Math.max(Math.abs(bx - ax), Math.abs(by - ay));
        for (let k = 0; k < steps; k++) {
            const cell: [number, number] = [ax + k * dx - ox, ay + k * dy - oy];
            if (!cells.some(c => c[0] === cell[0] && c[1] === cell[1])) {
                cells.push(cell);
            }
        }
        const end: [number, number] = [bx - ox, by - oy];
        if (!cells.some(c => c[0] === end[0] && c[1] === end[1])) {
            cells.push(end);
        }
    }
    if (waypoints.length === 1) {
        cells.push([0, 0]);
    }
    return cells;
}

// ── Ghost helpers ──────────────────────────────────────────────────

/**
 * Compute occupied cells for a component at a given position and rotation.
 * @param type - Component type string.
 * @param pos - Position to place at.
 * @param rot - Rotation to apply.
 * @returns Array of occupied world-cell coordinates.
 */
function getGhostCells(type: string, pos: [number, number],
                       rot: Rotation): [number, number][] {
    const meta = typeMeta[type];
    if (!meta) return [pos];
    const [w, h] = meta.coverage;
    const cells: [number, number][] = [];
    for (let i = 0; i < w; i++) {
        for (let j = 0; j < h; j++) {
            const [rox, roy] = rotateVec(i, j, rot);
            cells.push([pos[0] + rox, pos[1] + roy]);
        }
    }
    return cells;
}

/**
 * Compute port positions for ghost rendering.
 * @param type - Component type string.
 * @param pos - Position to place at.
 * @param rot - Rotation to apply.
 * @returns Array of port descriptors with world-cell coordinates.
 */
function getGhostPorts(type: string, pos: [number, number], rot: Rotation):
    { cell: [number, number]; dir: string; type: "input" | "output" }[] {
    const meta = typeMeta[type];
    if (!meta) return [];
    return meta.ports.map(p => {
        const [rox, roy] = rotateVec(p.offset[0], p.offset[1], rot);
        const rdir = rotateDir(p.direction, rot);
        return {
            cell: [pos[0] + rox, pos[1] + roy],
            dir: rdir,
            type: p.type as "input" | "output",
        };
    });
}

// ── State machine ──────────────────────────────────────────────────

/**
 * Select a component type to place.
 * @param type - Component type string.
 */
export function selectType(type: string): void {
    Renderer.setSelected(null);
    if (type === "conveyor") {
        mode = {
            mode: "conveyor",
            waypoints: [],
            direction_in: "up",
            direction_out: "down",
            cornerChoice: 0,
            cornerA: [],
            cornerB: [],
            hoverCell: null,
        };
    } else {
        mode = { mode: "simple", type, rot: "ROT_0" };
    }
    refreshGhost();
}

/** Cancel the current placement operation and clear ghosts. */
export function cancel(): void {
    mode = { mode: "idle" };
    Renderer.setGhost(null);
    Renderer.setSelected(null);
}

// ── Hover ──────────────────────────────────────────────────────────

/**
 * Handle mouse-hover on a grid cell.
 * @param cell - The cell under the cursor, or null.
 */
export function onHover(cell: [number, number] | null): void {
    lastHoverCell = cell;
    refreshGhost();
}

/** Rebuild ghost/preview data based on current mode and hover cell. */
function refreshGhost(): void {
    const cell = lastHoverCell;

    if (mode.mode === "idle") {
        Renderer.setGhost(null);
        return;
    }

    if (mode.mode === "simple") {
        if (!cell) { Renderer.setGhost(null); return; }
        Renderer.setGhost({
            cells: getGhostCells(mode.type, cell, mode.rot),
            color: typeColors[mode.type] ?? "#888",
            ghostPorts: getGhostPorts(mode.type, cell, mode.rot),
        });
        return;
    }

    if (mode.mode === "conveyor") {
        const m = mode;
        m.hoverCell = cell;
        if (!cell) { Renderer.setGhost(null); return; }

        // Single cell before first click
        if (m.waypoints.length === 0) {
            Renderer.setGhost({
                cells: [cell],
                color: "#9E9E9E",
                directionIn: m.direction_in,
                startCell: cell,
            });
            return;
        }

        const last = m.waypoints[m.waypoints.length - 1];
        const confirmedCount = m.waypoints.length;
        let proposedWaypoints: [number, number][];

        if (last[0] !== cell[0] && last[1] !== cell[1]) {
            const corner1: [number, number] = [last[0], cell[1]];
            const pathA: [number, number][] = [last, corner1, cell];
            const corner2: [number, number] = [cell[0], last[1]];
            const pathB: [number, number][] = [last, corner2, cell];

            // Filter by direction_in constraint on the first segment
            const isFirstSeg = m.waypoints.length === 1;
            const aValid = !isFirstSeg || firstSegAllowed(m.waypoints[0], corner1, m.direction_in);
            const bValid = !isFirstSeg || firstSegAllowed(m.waypoints[0], corner2, m.direction_in);

            // If current choice is invalid, switch to the valid one
            if (m.cornerChoice === 0 && !aValid && bValid) m.cornerChoice = 1;
            if (m.cornerChoice === 1 && !bValid && aValid) m.cornerChoice = 0;

            m.cornerA = pathA;
            m.cornerB = pathB;
            const chosen = m.cornerChoice === 0 ? pathA : pathB;
            proposedWaypoints = [...m.waypoints, ...chosen.slice(1)];

            // If neither is valid, don't render a ghost at all
            if (!aValid && !bValid) {
                Renderer.setGhost(null);
                return;
            }
        } else {
            // Collinear: check first segment validity
            if (m.waypoints.length === 1 && !firstSegAllowed(m.waypoints[0], cell, m.direction_in)) {
                Renderer.setGhost(null);
                return;
            }
            proposedWaypoints = [...m.waypoints, cell];
        }

        const expanded = expandWaypoints(proposedWaypoints);
        const worldCells = expanded.map(
            c => [c[0] + m.waypoints[0][0], c[1] + m.waypoints[0][1]] as [number, number],
        );

        const ghost: GhostData = {
            cells: worldCells,
            color: "#9E9E9E",
            pathLine: proposedWaypoints,
            confirmedPathLength: confirmedCount,
            directionIn: m.direction_in,
            directionOut: m.direction_out,
            startCell: m.waypoints[0],
        };

        if (last[0] !== cell[0] && last[1] !== cell[1]) {
            const alt = m.cornerChoice === 0 ? m.cornerB : m.cornerA;
            ghost.altPathLine = [...m.waypoints, ...alt.slice(1)];
        }

        Renderer.setGhost(ghost);
    }
}

// ── Click ──────────────────────────────────────────────────────────

/**
 * Handle a click on a grid cell.
 * @param cell - The clicked cell.
 * @param btn - Mouse button (1 = left, 2 = right).
 */
export async function onClick(cell: [number, number], btn: number): Promise<void> {
    if (mode.mode === "idle") return;

    if (btn === 2) {
        if (mode.mode === "conveyor" && mode.waypoints.length >= 1) {
            await commitConveyor();
        } else {
            cancel();
        }
        return;
    }

    if (mode.mode === "simple") {
        const p: Placement = { type: mode.type, pos: cell, rot: mode.rot };
        if (mode.type === "depot_loader") {
            p.item = getSelectedItemType();
        }
        placements.push(p);
        Renderer.setGhost(null);
        if (onCommit) await onCommit(placements);
        return;
    }

    if (mode.mode === "conveyor") {
        const m = mode;

        // First click after start point: enforce direction_in constraint
        if (m.waypoints.length === 1) {
            const start = m.waypoints[0];
            if (start[0] !== cell[0] && start[1] !== cell[1]) {
                // Diagonal — pick the valid corner
                const cornerA: [number, number] = [start[0], cell[1]];
                const cornerB: [number, number] = [cell[0], start[1]];
                const aOk = firstSegAllowed(start, cornerA, m.direction_in);
                const bOk = firstSegAllowed(start, cornerB, m.direction_in);
                if (!aOk && !bOk) return; // both blocked
                const chosenCorner = aOk ? cornerA : cornerB;
                m.waypoints.push(chosenCorner);
                m.waypoints.push(cell);
            } else {
                if (!firstSegAllowed(start, cell, m.direction_in)) return;
                m.waypoints.push(cell);
            }
            refreshGhost();
            return;
        }

        if (m.waypoints.length >= 2) {
            const last = m.waypoints[m.waypoints.length - 1];
            if (last[0] === cell[0] && last[1] === cell[1]) return;
            if (last[0] !== cell[0] && last[1] !== cell[1]) {
                const corner: [number, number] = [last[0], cell[1]];
                m.waypoints.push(corner);
                m.waypoints.push(cell);
            } else {
                m.waypoints.push(cell);
            }
        }

        if (m.waypoints.length === 0) {
            m.waypoints.push(cell);
        }

        refreshGhost();
    }
}

// ── Rotate (R key) ──────────────────────────────────────────────────

/** Rotate the current placement or conveyor direction. */
export function onRotate(): void {
    if (mode.mode === "simple") {
        const idx = ROT_SEQ.indexOf(mode.rot);
        mode.rot = ROT_SEQ[(idx + 1) % 4];
        refreshGhost();
        return;
    }

    if (mode.mode === "conveyor") {
        const m = mode;
        const { inExcluded, outExcluded } = forbiddenDirs(m.waypoints);
        if (m.waypoints.length === 0) {
            const next = nextInSeq(m.direction_in, DIR_IN_SEQ);
            m.direction_in = nextValidDir(next, inExcluded, DIR_IN_SEQ);
        } else {
            const next = nextInSeq(m.direction_out, DIR_OUT_SEQ);
            m.direction_out = nextValidDir(next, outExcluded, DIR_OUT_SEQ);
        }
        refreshGhost();
    }
}

// ── Toggle corner (Tab) ─────────────────────────────────────────────

/** Switch between the two possible corner paths for a conveyor bend. */
export function onToggleCorner(): void {
    if (mode.mode !== "conveyor") return;
    if (mode.waypoints.length < 1) return;
    mode.cornerChoice = mode.cornerChoice === 0 ? 1 : 0;
    refreshGhost();
}

// ── Internal ────────────────────────────────────────────────────────

/** Finalise the current conveyor path and add it to placements. */
async function commitConveyor(): Promise<void> {
    if (mode.mode !== "conveyor" || mode.waypoints.length < 1) return;
    const m = mode;
    const p: Placement = {
        type: "conveyor",
        path: [...m.waypoints],
        direction_in: m.direction_in,
        direction_out: m.direction_out,
    };
    placements.push(p);

    mode = {
        mode: "conveyor",
        waypoints: [],
        direction_in: "up",
        direction_out: "down",
        cornerChoice: 0,
        cornerA: [],
        cornerB: [],
        hoverCell: null,
    };
    Renderer.setGhost(null);
    if (onCommit) await onCommit(placements);
}
