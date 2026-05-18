import { fetchComponentTypes, sendLayout, tick, resetSim, fetchBlank, saveBlueprint, loadBlueprint as loadBlueprintApi, } from "./api.js";
import * as Renderer from "./renderer.js";
import * as Palette from "./palette.js";
import * as PlacementController from "./placement.js";
// ── State ──────────────────────────────────────────────────────────
let autoPlaying = false;
let tickInterval = 2000;
let nextTickTime = 0;
let pendingInterval = null;
let inventory = { ore: 9999 };
let selectedCompId = null;
let wasDragged = false;
let pointerDownPos = { x: 0, y: 0 };
// DOM refs
let speedSlider;
let speedLabel;
let infoEl;
let blueprintInput;
// ── Init ───────────────────────────────────────────────────────────
async function init() {
    const canvas = document.getElementById("canvas");
    const tooltipEl = document.getElementById("tooltip");
    infoEl = document.getElementById("info");
    speedSlider = document.getElementById("speed-slider");
    speedLabel = document.getElementById("speed-label");
    blueprintInput = document.getElementById("blueprint-input");
    Renderer.init(canvas, tooltipEl);
    PlacementController.init(onPlacementsChanged);
    Palette.init(document.getElementById("palette"), (type) => {
        if (type) {
            stopAutoPlay();
            selectedCompId = null;
            Renderer.setSelected(null);
            PlacementController.selectType(type);
        }
        else {
            PlacementController.cancel();
        }
    }, onInventoryChanged);
    // Load palette metadata for ghost rendering
    const types = await fetchComponentTypes();
    Palette.setPaletteItems(types);
    const colorMap = {};
    const metaMap = {};
    for (const t of types) {
        colorMap[t.type] = t.color;
        metaMap[t.type] = { coverage: t.coverage, ports: t.ports };
    }
    PlacementController.setTypeColors(colorMap);
    PlacementController.setTypeMeta(metaMap);
    // Start with blank map
    const blank = await fetchBlank();
    await applyLoadResponse(blank);
    speedSlider.addEventListener("input", () => {
        const val = parseInt(speedSlider.value);
        const newInterval = 2000 / val;
        speedLabel.textContent = `${val}x`;
        // Adust the pending interval and rescale the next-tick timer
        pendingInterval = newInterval;
        if (autoPlaying && nextTickTime > 0) {
            const now = performance.now();
            const remaining = Math.max(0, nextTickTime - now);
            nextTickTime = now + remaining * tickInterval / newInterval;
        }
    });
    speedSlider.addEventListener("change", () => {
        if (pendingInterval !== null) {
            tickInterval = pendingInterval;
            pendingInterval = null;
        }
    });
    document.addEventListener("keydown", onKey);
    // Mouse events
    canvas.addEventListener("mousedown", (e) => {
        pointerDownPos = { x: e.clientX, y: e.clientY };
        wasDragged = false;
    });
    canvas.addEventListener("mousemove", (e) => {
        if (e.buttons === 1) {
            const dx = e.clientX - pointerDownPos.x;
            const dy = e.clientY - pointerDownPos.y;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
                wasDragged = true;
                Renderer.pan(dx, dy);
                pointerDownPos = { x: e.clientX, y: e.clientY };
                return;
            }
        }
        onCanvasHover(e, canvas, tooltipEl);
    });
    canvas.addEventListener("click", async (e) => {
        if (wasDragged) {
            wasDragged = false;
            return;
        }
        await onCanvasClick(e, canvas, 0);
    });
    canvas.addEventListener("contextmenu", async (e) => {
        e.preventDefault();
        if (wasDragged) {
            wasDragged = false;
            return;
        }
        await onCanvasClick(e, canvas, 2);
    });
    canvas.addEventListener("wheel", (e) => {
        e.preventDefault();
        const rect = canvas.getBoundingClientRect();
        const cx = (e.clientX - rect.left) * (canvas.width / rect.width);
        const cy = (e.clientY - rect.top) * (canvas.height / rect.height);
        Renderer.handleWheel(e.deltaY, cx, cy);
    }, { passive: false });
    canvas.addEventListener("mouseleave", () => {
        tooltipEl.style.display = "none";
        PlacementController.onHover(null);
    });
    document.getElementById("btn-step").addEventListener("click", () => stepTick());
    document.getElementById("btn-play").addEventListener("click", () => toggleAutoPlay());
    document.getElementById("btn-reset").addEventListener("click", () => resetAndRender());
    document.getElementById("btn-save").addEventListener("click", () => onSave());
    document.getElementById("btn-load").addEventListener("click", () => blueprintInput.click());
    blueprintInput.addEventListener("change", async () => {
        const file = blueprintInput.files?.[0];
        if (!file)
            return;
        try {
            const text = await file.text();
            const data = JSON.parse(text);
            if (Array.isArray(data)) {
                const res = await loadBlueprintApi(data);
                if (res.ok) {
                    blueprintInput.value = "";
                    PlacementController.cancel();
                    Palette.clearSelection();
                    await applyLoadResponse(res);
                }
                else {
                    console.error("blueprint load failed:", res.error);
                }
            }
        }
        catch (err) {
            console.error("blueprint parse error:", err);
        }
    });
    window.addEventListener("resize", () => Renderer.resize());
    Renderer.resize();
}
// ── Load / state ───────────────────────────────────────────────────
async function loadBlank() {
    const res = await fetchBlank();
    if (!res.ok) {
        console.error("blank map failed", res.error);
        return;
    }
    await applyLoadResponse(res);
}
async function applyLoadResponse(res) {
    const placements = placementsFromResponse(res);
    PlacementController.setPlacements(placements);
    selectedCompId = null;
    Renderer.resetView();
    applyLayoutResponse(res);
}
function cellsToWaypoints(cells) {
    if (cells.length <= 1)
        return [...cells];
    const waypoints = [cells[0]];
    let prevDx = cells[1][0] - cells[0][0];
    let prevDy = cells[1][1] - cells[0][1];
    for (let i = 1; i < cells.length - 1; i++) {
        const dx = cells[i + 1][0] - cells[i][0];
        const dy = cells[i + 1][1] - cells[i][1];
        if (dx !== prevDx || dy !== prevDy) {
            waypoints.push(cells[i]);
            prevDx = dx;
            prevDy = dy;
        }
    }
    waypoints.push(cells[cells.length - 1]);
    return waypoints;
}
function placementsFromResponse(res) {
    return res.components.map(c => {
        const p = { type: c.type };
        if (c.type === "conveyor") {
            p.path = cellsToWaypoints(c.cells);
            p.direction_in = c.direction_in ?? "up";
            p.direction_out = c.direction_out ?? "down";
        }
        else {
            p.pos = c.pos;
            p.rot = c.rot;
        }
        if (c.item)
            p.item = c.item;
        return p;
    });
}
function applyLayoutResponse(res) {
    Renderer.setData(res.components, res.edges, res.viewport);
    Renderer.setSelected(null);
    const cs = res.components_state ?? [];
    Renderer.setAnimDuration(0);
    Renderer.setState(cs);
    if (res.inventory) {
        inventory = { ...res.inventory };
        Palette.setInventoryData(inventory);
    }
    updateInfo(res.tick, cs);
}
async function onPlacementsChanged(placements) {
    stopAutoPlay();
    const res = await sendLayout(placements, inventory);
    if (!res.ok) {
        console.error("layout rejected:", res.error);
        return;
    }
    applyLayoutResponse(res);
}
function onInventoryChanged(data) {
    inventory = data;
    onPlacementsChanged(PlacementController.getPlacements());
}
async function stepTick() {
    const res = await tick(1);
    if (res.ok) {
        Renderer.setAnimDuration(autoPlaying ? tickInterval : 400);
        Renderer.setState(res.components);
        updateInfo(res.tick, res.components);
    }
}
async function resetAndRender() {
    stopAutoPlay();
    const res = await resetSim();
    if (res.ok) {
        Renderer.setAnimDuration(0);
        Renderer.setState(res.components);
        updateInfo(res.tick, res.components);
    }
}
// ── Auto-play ──────────────────────────────────────────────────────
function toggleAutoPlay() {
    if (autoPlaying) {
        stopAutoPlay();
    }
    else {
        autoPlaying = true;
        document.getElementById("btn-play").textContent = "⏸";
        keepAutoPlaying();
    }
}
function stopAutoPlay() {
    autoPlaying = false;
    document.getElementById("btn-play").textContent = "▶";
}
async function keepAutoPlaying() {
    while (autoPlaying) {
        const now = performance.now();
        const interval = pendingInterval ?? tickInterval;
        nextTickTime = now + interval;
        const res = await tick(1);
        if (res.ok) {
            Renderer.setAnimDuration(interval);
            Renderer.setState(res.components);
            updateInfo(res.tick, res.components);
        }
        const wait = Math.max(0, nextTickTime - performance.now());
        if (wait > 0)
            await new Promise(r => setTimeout(r, wait));
    }
}
// ── Canvas interaction ─────────────────────────────────────────────
async function onCanvasClick(e, canvas, btn) {
    const rect = canvas.getBoundingClientRect();
    const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
    const cell = Renderer.screenToCell(sx, sy);
    if (!cell)
        return;
    // If in a placement mode, delegate to placement controller
    const pMode = PlacementController.getMode();
    if (pMode.mode !== "idle") {
        await PlacementController.onClick(cell, btn);
        return;
    }
    // Otherwise: select existing component on LMB
    if (btn === 0) {
        const existing = Renderer.findComponentAt(cell);
        if (existing) {
            stopAutoPlay();
            selectedCompId = existing.id;
            Renderer.setSelected(existing.id);
            Renderer.draw();
            return;
        }
    }
    // RMB when idle → clear palette
    if (btn === 2) {
        PlacementController.cancel();
        Palette.clearSelection();
    }
}
function onCanvasHover(e, canvas, tip) {
    const rect = canvas.getBoundingClientRect();
    const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
    const cell = Renderer.screenToCell(sx, sy);
    // Always update placement ghost
    PlacementController.onHover(cell);
    // Show tooltip for existing components
    if (!cell || !Renderer.findComponentAt(cell)) {
        tip.style.display = "none";
        return;
    }
    const comp = Renderer.findComponentAt(cell);
    tip.style.display = "block";
    tip.style.left = `${e.clientX - rect.left + 12}px`;
    tip.style.top = `${e.clientY - rect.top - 10}px`;
    tip.textContent = `${comp.label}  @(${comp.pos[0]},${comp.pos[1]})  ${comp.rot}`;
}
// ── Keyboard ───────────────────────────────────────────────────────
function onKey(e) {
    if (e.target instanceof HTMLInputElement)
        return;
    // Ctrl+S → save blueprint
    if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")) {
        e.preventDefault();
        onSave();
        return;
    }
    switch (e.key) {
        case " ":
            e.preventDefault();
            toggleAutoPlay();
            break;
        case "ArrowRight":
        case "n":
        case "N":
            e.preventDefault();
            stopAutoPlay();
            stepTick();
            break;
        case "r":
        case "R":
            e.preventDefault();
            stopAutoPlay();
            onRotate();
            break;
        case "Delete":
        case "Backspace":
            e.preventDefault();
            stopAutoPlay();
            deleteSelected();
            break;
        case "Tab":
            e.preventDefault();
            PlacementController.onToggleCorner();
            break;
        case "Escape":
            e.preventDefault();
            if (PlacementController.hasWaypoints()) {
                // Conveyor with waypoints: commit like RMB
                PlacementController.handleCommit();
            }
            else {
                PlacementController.cancel();
                Palette.clearSelection();
            }
            break;
    }
}
function onRotate() {
    // If in placement mode, rotate the pending placement
    const pMode = PlacementController.getMode();
    if (pMode.mode !== "idle") {
        PlacementController.onRotate();
        return;
    }
    // Otherwise, rotate selected component
    rotateSelectedExisting();
}
async function rotateSelectedExisting() {
    if (selectedCompId == null)
        return;
    const comp = Renderer.findComponentById(selectedCompId);
    if (!comp)
        return;
    const placements = PlacementController.getPlacements();
    if (comp.type === "conveyor") {
        const dirSeq = [
            ["up", "down"],
            ["right", "left"],
            ["down", "up"],
            ["left", "right"],
        ];
        for (const p of placements) {
            if (p.path && p.path[0][0] === comp.pos[0] && p.path[0][1] === comp.pos[1]) {
                const idx = dirSeq.findIndex(d => d[0] === p.direction_in && d[1] === p.direction_out);
                const [di, dout] = dirSeq[(idx + 1) % 4];
                p.direction_in = di;
                p.direction_out = dout;
                break;
            }
        }
    }
    else {
        const rotOrder = ["ROT_0", "ROT_1", "ROT_2", "ROT_3"];
        const idx = rotOrder.indexOf(comp.rot);
        const newRot = rotOrder[(idx + 1) % 4];
        for (const p of placements) {
            if (p.pos && p.pos[0] === comp.pos[0] && p.pos[1] === comp.pos[1]) {
                p.rot = newRot;
                break;
            }
        }
    }
    PlacementController.setPlacements(placements);
    await onPlacementsChanged(placements);
}
async function deleteSelected() {
    if (selectedCompId == null)
        return;
    const comp = Renderer.findComponentById(selectedCompId);
    if (!comp)
        return;
    let placements = PlacementController.getPlacements();
    placements = placements.filter(p => comp.type === "conveyor"
        ? !(p.path && p.path[0][0] === comp.pos[0] && p.path[0][1] === comp.pos[1])
        : !(p.pos && p.pos[0] === comp.pos[0] && p.pos[1] === comp.pos[1]));
    selectedCompId = null;
    Renderer.setSelected(null);
    PlacementController.setPlacements(placements);
    await onPlacementsChanged(placements);
}
// ── Blueprint save ──────────────────────────────────────────────────
async function onSave() {
    const data = await saveBlueprint();
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "blueprint.blueprint";
    a.click();
    URL.revokeObjectURL(url);
}
// ── Info bar ───────────────────────────────────────────────────────
function updateInfo(tick, comps) {
    const totalItems = comps.reduce((s, c) => s + (c.count ?? c.inventory ?? 0), 0);
    infoEl.textContent = `Tick: ${tick}  |  Components: ${comps.length}  |  Items: ${totalItems}`;
}
// ── Boot ───────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", init);
//# sourceMappingURL=main.js.map