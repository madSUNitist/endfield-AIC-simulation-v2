// ── Configuration ──────────────────────────────────────────────────
const CELL = 64;
const HALF = CELL / 2;
const ITEM = CELL / 2;
const ITEM_OFS = (CELL - ITEM) / 2;
const GRID_LINE = "#ddd";
const BG = "#fafafa";
// ── Pan / zoom state ───────────────────────────────────────────────
let panX = 0;
let panY = 0;
let zoom = 1;
let baseScale = 1;
// ── State (set by caller each frame) ───────────────────────────────
let layoutComps = [];
let edges = [];
let viewport = { x0: 0, y0: 0, w: 1, h: 1 };
let stateMap = new Map();
let prevStateMap = new Map();
let selectedId = null;
// ── Animation state (timer-based interpolation) ─────────────────────
let animStartTime = 0;
let animDuration = 400;
// DOM refs
let canvas;
let ctx;
let tooltipEl;
/** Initialise the canvas and start the persistent RAF draw loop. */
export function init(cvs, tip) {
    canvas = cvs;
    ctx = cvs.getContext("2d");
    tooltipEl = tip;
    requestAnimationFrame(function frame() {
        draw();
        requestAnimationFrame(frame);
    });
}
/** Update layout data (components, edges, viewport). */
export function setData(comps, es, vp) {
    layoutComps = comps;
    edges = es;
    viewport = vp;
}
/** Update per-tick state and start a new animation segment. */
export function setState(comps) {
    prevStateMap = new Map(stateMap);
    stateMap.clear();
    for (const c of comps) {
        stateMap.set(c.id, c);
    }
    animStartTime = performance.now();
}
/** Set animation duration in ms (0 = snap to final positions). */
export function setAnimDuration(ms) {
    animDuration = ms;
}
/** Highlight a component by ID (null = clear). */
export function setSelected(id) {
    selectedId = id;
}
/** Recompute canvas dimensions to fit the viewport. */
export function resize() {
    const cw = (viewport.w + 2) * CELL;
    const ch = (viewport.h + 2) * CELL;
    const parent = canvas.parentElement;
    baseScale = Math.min(parent.clientWidth / cw, parent.clientHeight / ch, 1);
    canvas.width = cw * baseScale;
    canvas.height = ch * baseScale;
    canvas.style.width = `${cw * baseScale}px`;
    canvas.style.height = `${ch * baseScale}px`;
    draw();
}
// ── Pan / zoom API ─────────────────────────────────────────────────
export function pan(dx, dy) {
    panX += dx;
    panY += dy;
    draw();
}
export function handleWheel(deltaY, cx, cy) {
    const factor = deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.1, Math.min(10, zoom * factor));
    panX = cx + (panX - cx) * newZoom / zoom;
    panY = cy + (panY - cy) * newZoom / zoom;
    zoom = newZoom;
    draw();
}
export function resetView() {
    panX = 0;
    panY = 0;
    zoom = 1;
    draw();
}
// ── Coordinate helpers ─────────────────────────────────────────────
function toCanvas(wx, wy) {
    const mx = viewport.x0 - 1;
    const my = viewport.y0 - 1;
    return [
        (wx - mx) * CELL,
        (wy - my) * CELL,
    ];
}
function lerp(a, b, t) {
    return a + (b - a) * t;
}
// ── Path angle lookup ──────────────────────────────────────────────
// ── Main draw ──────────────────────────────────────────────────────
export function draw() {
    const now = performance.now();
    const progress = animStartTime > 0 && animDuration > 0
        ? Math.min(1, (now - animStartTime) / animDuration)
        : 1;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(baseScale * zoom, 0, 0, baseScale * zoom, panX, panY);
    const w = (viewport.w + 2) * CELL;
    const h = (viewport.h + 2) * CELL;
    drawGrid(w, h);
    drawEdges();
    drawComponents(progress);
}
function drawGrid(w, h) {
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = GRID_LINE;
    ctx.lineWidth = 1;
    const cols = viewport.w + 2;
    const rows = viewport.h + 2;
    for (let i = 0; i <= cols; i++) {
        const x = i * CELL;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
    }
    for (let i = 0; i <= rows; i++) {
        const y = i * CELL;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
    }
}
function drawEdges() {
    ctx.strokeStyle = "#666";
    ctx.lineWidth = 2;
    ctx.fillStyle = "#666";
    for (const e of edges) {
        const [x1, y1] = toCanvas(e.from[0], e.from[1]);
        const [x2, y2] = toCanvas(e.to[0], e.to[1]);
        const cx1 = x1 + HALF;
        const cy1 = y1 + HALF;
        const cx2 = x2 + HALF;
        const cy2 = y2 + HALF;
        const dx = cx2 - cx1;
        const dy = cy2 - cy1;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len < 1)
            continue;
        const nx = dx / len;
        const ny = dy / len;
        const sx = cx1 + nx * HALF;
        const sy = cy1 + ny * HALF;
        const ex = cx2 - nx * HALF;
        const ey = cy2 - ny * HALF;
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(ex, ey);
        ctx.stroke();
        const aLen = 8;
        const aAng = 0.5;
        ctx.beginPath();
        ctx.moveTo(ex, ey);
        ctx.lineTo(ex - nx * aLen - ny * aLen * aAng, ey - ny * aLen + nx * aLen * aAng);
        ctx.lineTo(ex - nx * aLen + ny * aLen * aAng, ey - ny * aLen - nx * aLen * aAng);
        ctx.closePath();
        ctx.fill();
    }
}
function drawComponents(progress) {
    const compById = new Map(layoutComps.map(c => [c.id, c]));
    for (const comp of layoutComps) {
        const st = stateMap.get(comp.id);
        drawComponentCell(comp, st);
        if (st) {
            drawItems(comp, st, compById, progress);
        }
    }
}
function drawComponentCell(comp, st) {
    const { cells, color, label, id } = comp;
    if (cells.length === 0)
        return;
    for (const c of cells) {
        const [cx, cy] = toCanvas(c[0], c[1]);
        ctx.fillStyle = color + "30";
        ctx.fillRect(cx, cy, CELL, CELL);
    }
    const cellSet = new Set(cells.map(c => `${c[0]},${c[1]}`));
    ctx.strokeStyle = id === selectedId ? "#ff0" : "#333";
    ctx.lineWidth = id === selectedId ? 3 : 1.5;
    ctx.beginPath();
    for (const c of cells) {
        const [cx, cy] = toCanvas(c[0], c[1]);
        if (!cellSet.has(`${c[0]},${c[1] - 1}`)) {
            ctx.moveTo(cx, cy);
            ctx.lineTo(cx + CELL, cy);
        }
        if (!cellSet.has(`${c[0]},${c[1] + 1}`)) {
            ctx.moveTo(cx, cy + CELL);
            ctx.lineTo(cx + CELL, cy + CELL);
        }
        if (!cellSet.has(`${c[0] - 1},${c[1]}`)) {
            ctx.moveTo(cx, cy);
            ctx.lineTo(cx, cy + CELL);
        }
        if (!cellSet.has(`${c[0] + 1},${c[1]}`)) {
            ctx.moveTo(cx + CELL, cy);
            ctx.lineTo(cx + CELL, cy + CELL);
        }
    }
    ctx.stroke();
    let sumX = 0, sumY = 0;
    for (const c of cells) {
        sumX += c[0];
        sumY += c[1];
    }
    const [lx, ly] = toCanvas(sumX / cells.length, sumY / cells.length);
    ctx.fillStyle = "#222";
    ctx.font = "bold 12px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, lx + HALF, ly + HALF);
    for (const port of comp.ports) {
        drawPortArrow(port.cell, port.dir);
    }
}
function drawPortArrow(cell, dir) {
    const [cx, cy] = toCanvas(cell[0], cell[1]);
    const px = cx + HALF + dir[0] * HALF * 0.7;
    const py = cy + HALF + dir[1] * HALF * 0.7;
    const al = 8;
    ctx.fillStyle = "#444";
    ctx.beginPath();
    ctx.moveTo(px + dir[0] * al, py + dir[1] * al);
    ctx.lineTo(px - dir[0] * al - dir[1] * al * 0.4, py + dir[1] * al - dir[0] * al * 0.4);
    ctx.lineTo(px - dir[0] * al + dir[1] * al * 0.4, py + dir[1] * al + dir[0] * al * 0.4);
    ctx.closePath();
    ctx.fill();
}
function drawItems(comp, st, compById, progress) {
    if (!st.slot_map) {
        // Non-conveyor (buffer)
        if (st.buffer) {
            const cells = comp.cells;
            const cx = cells.reduce((s, c) => s + c[0], 0) / cells.length;
            const cy = cells.reduce((s, c) => s + c[1], 0) / cells.length;
            const [px, py] = toCanvas(cx, cy);
            drawItemBox(px, py, st.buffer);
        }
        return;
    }
    const prevSt = prevStateMap.get(comp.id);
    const cells = comp.cells;
    if (cells.length === 0)
        return;
    // Entry / exit directions from component metadata
    const DIR_VEC = {
        up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0],
    };
    const inVec = comp.direction_in
        ? DIR_VEC[comp.direction_in] ?? [0, 0] : [0, 0];
    const outVec = comp.direction_out
        ? DIR_VEC[comp.direction_out] ?? [0, 0] : [0, 0];
    // Build set of current item IDs
    const currIds = new Set();
    const currByCell = new Map();
    for (const cell of cells) {
        const key = `${cell[0]},${cell[1]}`;
        const item = st.slot_map[key];
        if (item) {
            currIds.add(item.id);
            currByCell.set(key, item);
        }
    }
    // Clip to conveyor cells
    ctx.save();
    ctx.beginPath();
    for (const c of cells) {
        const [cx, cy] = toCanvas(c[0], c[1]);
        ctx.rect(cx, cy, CELL, CELL);
    }
    ctx.clip();
    // ── Leaving items (in prev, not in curr) ────────────────
    if (prevSt && prevSt.slot_map && progress < 1) {
        for (const [pk, pv] of Object.entries(prevSt.slot_map)) {
            if (!pv || currIds.has(pv.id))
                continue;
            const [px, py] = pk.split(',').map(Number);
            const [fromX, fromY] = toCanvas(px, py);
            const [toX, toY] = toCanvas(px + outVec[0], py + outVec[1]);
            drawItemBox(lerp(fromX, toX, progress), lerp(fromY, toY, progress), pv);
        }
    }
    // ── Entering & moving items (in curr) ───────────────────
    for (const cell of cells) {
        const key = `${cell[0]},${cell[1]}`;
        const item = st.slot_map[key];
        if (!item)
            continue;
        // Match item by ID in prev
        let fromPos = null;
        if (prevSt && prevSt.slot_map) {
            for (const [pk, pv] of Object.entries(prevSt.slot_map)) {
                if (pv && pv.id === item.id) {
                    const [px, py] = pk.split(',').map(Number);
                    fromPos = toCanvas(px, py);
                    break;
                }
            }
        }
        const [toX, toY] = toCanvas(cell[0], cell[1]);
        let drawX, drawY;
        if (fromPos && progress < 1) {
            // Moving item
            drawX = lerp(fromPos[0], toX, progress);
            drawY = lerp(fromPos[1], toY, progress);
        }
        else if (progress < 1 && cell === cells[0] && cells.length >= 2) {
            // Entering item at head: slide from upstream direction
            const [extX, extY] = toCanvas(cell[0] + inVec[0], cell[1] + inVec[1]);
            drawX = lerp(extX, toX, progress);
            drawY = lerp(extY, toY, progress);
        }
        else {
            drawX = toX;
            drawY = toY;
        }
        drawItemBox(drawX, drawY, item);
    }
    ctx.restore();
}
function drawItemBox(cx, cy, item) {
    ctx.save();
    ctx.translate(cx + HALF, cy + HALF);
    ctx.fillStyle = "#222";
    ctx.fillRect(-HALF + ITEM_OFS, -HALF + ITEM_OFS, ITEM, ITEM);
    ctx.fillStyle = "#fff";
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const label = `${item.type.slice(0, 3)}#${item.id}`;
    ctx.fillText(label, 0, 0);
    ctx.restore();
}
// ── Screen → world cell lookup ─────────────────────────────────────
export function screenToCell(sx, sy) {
    const lx = (sx - panX) / (baseScale * zoom);
    const ly = (sy - panY) / (baseScale * zoom);
    const mx = viewport.x0 - 1;
    const my = viewport.y0 - 1;
    const gx = mx + lx / CELL;
    const gy = my + ly / CELL;
    const cx = Math.floor(gx);
    const cy = Math.floor(gy);
    if (gx - cx > 0.99 || gy - cy > 0.99)
        return null;
    return [cx, cy];
}
export function findComponentAt(cell) {
    for (const comp of layoutComps) {
        for (const c of comp.cells) {
            if (c[0] === cell[0] && c[1] === cell[1]) {
                return comp;
            }
        }
    }
    return null;
}
export function findComponentById(id) {
    return layoutComps.find(c => c.id === id) ?? null;
}
export function getCanvasSize() {
    return [(viewport.w + 2) * CELL, (viewport.h + 2) * CELL];
}
//# sourceMappingURL=renderer.js.map