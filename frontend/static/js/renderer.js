// ── Configuration ──────────────────────────────────────────────────
const CELL = 64;
const HALF = CELL / 2;
const ITEM = CELL / 2;
const ITEM_OFS = (CELL - ITEM) / 2;
const GRID_LINE = "#ddd";
const BG = "#fafafa";
const MIN_ZOOM = 0.25;
const MAX_ZOOM = 4;
// ── Pan / zoom state ───────────────────────────────────────────────
let panX = 0;
let panY = 0;
let zoom = 1;
// ── State (set by caller each frame) ───────────────────────────────
let layoutComps = [];
let edges = [];
let stateMap = new Map();
let prevStateMap = new Map();
let selectedId = null;
// ── Ghost (placement preview) ───────────────────────────────────────
let ghostData = null;
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
/** Update layout data (components, edges). */
export function setData(comps, es, _vp) {
    layoutComps = comps;
    edges = es;
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
/** Set ghost (placement preview) data (null = clear). */
export function setGhost(data) {
    ghostData = data;
}
/** Resize canvas to fill its container. */
export function resize() {
    const parent = canvas.parentElement;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight;
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
    const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom * factor));
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
const _HIDDEN = 0; // eslint-disable-line
/** World cell → drawing space (each cell = CELL px at zoom=1). */
function toCanvas(wx, wy) {
    return [wx * CELL, wy * CELL];
}
function lerp(a, b, t) {
    return a + (b - a) * t;
}
/** Canvas pixel → drawing coordinate. */
function pixelToDraw(px, py) {
    return [(px - panX) / zoom, (py - panY) / zoom];
}
// ── Main draw ──────────────────────────────────────────────────────
export function draw() {
    const now = performance.now();
    const progress = animStartTime > 0 && animDuration > 0
        ? Math.min(1, (now - animStartTime) / animDuration)
        : 1;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(zoom, 0, 0, zoom, panX, panY);
    drawGrid();
    drawEdges();
    drawComponents(progress);
    drawGhost();
}
// ── Grid (dynamic visible range) ───────────────────────────────────
function drawGrid() {
    const [dx0, dy0] = pixelToDraw(0, 0);
    const [dx1, dy1] = pixelToDraw(canvas.width, canvas.height);
    ctx.fillStyle = BG;
    ctx.fillRect(dx0, dy0, dx1 - dx0, dy1 - dy0);
    ctx.strokeStyle = GRID_LINE;
    ctx.lineWidth = 1;
    const col0 = Math.floor(dx0 / CELL);
    const col1 = Math.ceil(dx1 / CELL);
    const row0 = Math.floor(dy0 / CELL);
    const row1 = Math.ceil(dy1 / CELL);
    for (let i = col0; i <= col1; i++) {
        const x = i * CELL;
        ctx.beginPath();
        ctx.moveTo(x, dy0);
        ctx.lineTo(x, dy1);
        ctx.stroke();
    }
    for (let i = row0; i <= row1; i++) {
        const y = i * CELL;
        ctx.beginPath();
        ctx.moveTo(dx0, y);
        ctx.lineTo(dx1, y);
        ctx.stroke();
    }
}
// ── Edges ──────────────────────────────────────────────────────────
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
// ── Components ─────────────────────────────────────────────────────
function drawComponents(progress) {
    for (const comp of layoutComps) {
        const st = stateMap.get(comp.id);
        drawComponentCell(comp, st);
        if (st) {
            drawItems(comp, st, progress);
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
        drawPortArrow(port.cell, port.dir, port.type === "input");
    }
}
function drawPortArrow(cell, dir, isInput) {
    const [cx, cy] = toCanvas(cell[0], cell[1]);
    const px = cx + HALF + dir[0] * HALF * 0.7;
    const py = cy + HALF + dir[1] * HALF * 0.7;
    const sd = isInput ? [-dir[0], -dir[1]] : dir;
    const al = 8;
    ctx.fillStyle = "#444";
    ctx.beginPath();
    ctx.moveTo(px + sd[0] * al, py + sd[1] * al);
    ctx.lineTo(px - sd[0] * al - sd[1] * al * 0.4, py - sd[1] * al - sd[0] * al * 0.4);
    ctx.lineTo(px - sd[0] * al + sd[1] * al * 0.4, py - sd[1] * al + sd[0] * al * 0.4);
    ctx.closePath();
    ctx.fill();
}
// ── Items ──────────────────────────────────────────────────────────
function drawItems(comp, st, progress) {
    if (!st.slot_map) {
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
    const DIR_VEC = {
        up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0],
    };
    const inVec = comp.direction_in
        ? DIR_VEC[comp.direction_in] ?? [0, 0] : [0, 0];
    const outVec = comp.direction_out
        ? DIR_VEC[comp.direction_out] ?? [0, 0] : [0, 0];
    const currIds = new Set();
    for (const cell of cells) {
        const key = `${cell[0]},${cell[1]}`;
        const item = st.slot_map[key];
        if (item)
            currIds.add(item.id);
    }
    ctx.save();
    ctx.beginPath();
    for (const c of cells) {
        const [cx, cy] = toCanvas(c[0], c[1]);
        ctx.rect(cx, cy, CELL, CELL);
    }
    ctx.clip();
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
    for (const cell of cells) {
        const key = `${cell[0]},${cell[1]}`;
        const item = st.slot_map[key];
        if (!item)
            continue;
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
            drawX = lerp(fromPos[0], toX, progress);
            drawY = lerp(fromPos[1], toY, progress);
        }
        else if (progress < 1) {
            const idx = cells.indexOf(cell);
            if (idx > 0) {
                const [prevX, prevY] = toCanvas(cells[idx - 1][0], cells[idx - 1][1]);
                drawX = lerp(prevX, toX, progress);
                drawY = lerp(prevY, toY, progress);
            }
            else {
                const [extX, extY] = toCanvas(cell[0] + inVec[0], cell[1] + inVec[1]);
                drawX = lerp(extX, toX, progress);
                drawY = lerp(extY, toY, progress);
            }
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
    const [dx, dy] = pixelToDraw(sx, sy);
    const gx = dx / CELL;
    const gy = dy / CELL;
    return [Math.floor(gx), Math.floor(gy)];
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
// ── Ghost rendering (placement preview) ────────────────────────────
const DIR_VEC_G = {
    up: [0, -1],
    down: [0, 1],
    left: [-1, 0],
    right: [1, 0],
};
function drawGhost() {
    if (!ghostData)
        return;
    ctx.save();
    ctx.globalAlpha = 0.5;
    const { cells, color, pathLine, altPathLine, directionIn, directionOut, startCell, ghostPorts, } = ghostData;
    // Draw ghost cells
    const cellSet = new Set();
    for (const c of cells) {
        const [cx, cy] = toCanvas(c[0], c[1]);
        ctx.fillStyle = color + "60";
        ctx.fillRect(cx, cy, CELL, CELL);
        cellSet.add(`${c[0]},${c[1]}`);
    }
    // Draw cell borders
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
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
    // Draw path polyline (conveyor mode)
    if (pathLine && pathLine.length >= 2) {
        const confirmedLen = ghostData.confirmedPathLength ?? 0;
        if (confirmedLen >= 2) {
            ctx.strokeStyle = color;
            ctx.lineWidth = 3;
            ctx.setLineDash([]);
            ctx.beginPath();
            const [sx, sy] = toCanvas(pathLine[0][0], pathLine[0][1]);
            ctx.moveTo(sx + HALF, sy + HALF);
            for (let i = 1; i < Math.min(confirmedLen, pathLine.length); i++) {
                const [ex, ey] = toCanvas(pathLine[i][0], pathLine[i][1]);
                ctx.lineTo(ex + HALF, ey + HALF);
            }
            ctx.stroke();
        }
        if (confirmedLen < pathLine.length) {
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 4]);
            ctx.beginPath();
            const startIdx = Math.max(0, confirmedLen - 1);
            const [sx, sy] = toCanvas(pathLine[startIdx][0], pathLine[startIdx][1]);
            ctx.moveTo(sx + HALF, sy + HALF);
            for (let i = startIdx + 1; i < pathLine.length; i++) {
                const [ex, ey] = toCanvas(pathLine[i][0], pathLine[i][1]);
                ctx.lineTo(ex + HALF, ey + HALF);
            }
            ctx.stroke();
            ctx.setLineDash([]);
        }
    }
    // Draw alternative corner path (dashed, lighter)
    if (altPathLine && altPathLine.length >= 2) {
        ctx.strokeStyle = "#666";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        const [sx, sy] = toCanvas(altPathLine[0][0], altPathLine[0][1]);
        ctx.moveTo(sx + HALF, sy + HALF);
        for (let i = 1; i < altPathLine.length; i++) {
            const [ex, ey] = toCanvas(altPathLine[i][0], altPathLine[i][1]);
            ctx.lineTo(ex + HALF, ey + HALF);
        }
        ctx.stroke();
        ctx.setLineDash([]);
    }
    // Draw component port arrows (for simple components)
    if (ghostPorts) {
        for (const port of ghostPorts) {
            const dirVec = DIR_VEC_G[port.dir] ?? [0, 0];
            drawGhostArrow(port.cell, dirVec, color, port.type === "input");
        }
    }
    // Draw conveyor direction arrows
    if (directionIn && startCell) {
        const inVec = DIR_VEC_G[directionIn] ?? [0, -1];
        drawGhostArrow(startCell, inVec, color, true);
    }
    if (directionOut) {
        let outCell;
        if (pathLine && pathLine.length >= 2) {
            outCell = pathLine[pathLine.length - 1];
        }
        else if (cells.length >= 1) {
            outCell = cells[cells.length - 1];
        }
        else {
            ctx.restore();
            return;
        }
        const outVec = DIR_VEC_G[directionOut] ?? [0, 1];
        drawGhostArrow(outCell, outVec, color, false);
    }
    ctx.restore();
}
function drawGhostArrow(cell, dir, color, isInput) {
    const [cx, cy] = toCanvas(cell[0], cell[1]);
    const px = cx + HALF + dir[0] * HALF * 0.6;
    const py = cy + HALF + dir[1] * HALF * 0.6;
    const sd = isInput ? [-dir[0], -dir[1]] : dir;
    const al = 10;
    ctx.fillStyle = isInput ? "#4CAF50" : "#f44336";
    ctx.beginPath();
    ctx.moveTo(px + sd[0] * al, py + sd[1] * al);
    ctx.lineTo(px - sd[0] * al - sd[1] * al * 0.5, py - sd[1] * al - sd[0] * al * 0.5);
    ctx.lineTo(px - sd[0] * al + sd[1] * al * 0.5, py - sd[1] * al + sd[0] * al * 0.5);
    ctx.closePath();
    ctx.fill();
}
//# sourceMappingURL=renderer.js.map