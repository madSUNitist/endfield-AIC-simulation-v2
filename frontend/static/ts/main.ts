import {
    fetchComponentTypes, sendLayout, tick, resetSim,
    fetchBlank, saveBlueprint, loadBlueprint as loadBlueprintApi,
} from "./api.js";
import type { LayoutResponse, ComponentState, Placement, Rotation } from "./types.js";
import * as Renderer from "./renderer.js";
import * as Palette from "./palette.js";
import * as PlacementController from "./placement.js";

// ── State ──────────────────────────────────────────────────────────

let autoPlaying = false;
let tickInterval = 2000;
let nextTickTime = 0;
let pendingInterval: number | null = null;
let inventory: Record<string, number> = { ore: 9999 };
let selectedCompId: number | null = null;
let wasDragged = false;
let pointerDownPos = { x: 0, y: 0 };

// DOM refs
let speedSlider: HTMLInputElement;
let speedLabel: HTMLElement;
let infoEl: HTMLElement;
let blueprintInput: HTMLInputElement;

// ── Init ───────────────────────────────────────────────────────────

/** Initialise the application: canvas, palette, event handlers, load blank map. */
async function init(): Promise<void> {
    const canvas = document.getElementById("canvas") as HTMLCanvasElement;
    const tooltipEl = document.getElementById("tooltip") as HTMLElement;
    infoEl = document.getElementById("info") as HTMLElement;
    speedSlider = document.getElementById("speed-slider") as HTMLInputElement;
    speedLabel = document.getElementById("speed-label") as HTMLElement;
    blueprintInput = document.getElementById("blueprint-input") as HTMLInputElement;

    Renderer.init(canvas, tooltipEl);
    PlacementController.init(onPlacementsChanged);

    Palette.init(
        document.getElementById("palette") as HTMLElement,
        (type: string | null) => {
            if (type) {
                stopAutoPlay();
                selectedCompId = null;
                Renderer.setSelected(null);
                PlacementController.selectType(type);
            } else {
                PlacementController.cancel();
            }
        },
        onInventoryChanged,
    );

    // Load palette metadata for ghost rendering
    const types = await fetchComponentTypes();
    Palette.setPaletteItems(types);
    const colorMap: Record<string, string> = {};
    const metaMap: Record<string, { coverage: [number, number]; ports: typeof types[0]["ports"] }> = {};
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
        if (wasDragged) { wasDragged = false; return; }
        await onCanvasClick(e, canvas, 0);
    });

    canvas.addEventListener("contextmenu", async (e) => {
        e.preventDefault();
        if (wasDragged) { wasDragged = false; return; }
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

    document.getElementById("btn-step")!.addEventListener("click", () => stepTick());
    document.getElementById("btn-play")!.addEventListener("click", () => toggleAutoPlay());
    document.getElementById("btn-reset")!.addEventListener("click", () => resetAndRender());
    document.getElementById("btn-save")!.addEventListener("click", () => onSave());
    document.getElementById("btn-load")!.addEventListener("click", () => blueprintInput.click());

    blueprintInput.addEventListener("change", async () => {
        const file = blueprintInput.files?.[0];
        if (!file) return;
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
                } else {
                    console.error("blueprint load failed:", res.error);
                }
            }
        } catch (err) {
            console.error("blueprint parse error:", err);
        }
    });

    window.addEventListener("resize", () => Renderer.resize());
    Renderer.resize();
}

// ── Load / state ───────────────────────────────────────────────────

/** Load a blank map and apply the response. */
async function loadBlank(): Promise<void> {
    const res = await fetchBlank();
    if (!res.ok) { console.error("blank map failed", res.error); return; }
    await applyLoadResponse(res);
}

/**
 * Apply a layout response: reset placements, view, and render.
 * @param res - The layout response from the backend.
 */
async function applyLoadResponse(res: LayoutResponse): Promise<void> {
    const placements = placementsFromResponse(res);
    PlacementController.setPlacements(placements);
    selectedCompId = null;
    Renderer.resetView();
    applyLayoutResponse(res);
}

/**
 * Convert a flat cell list back to minimal waypoints (compression).
 * @param cells - Occupied cells in order.
 * @returns Waypoints (only points where direction changes).
 */
function cellsToWaypoints(cells: [number, number][]): [number, number][] {
    if (cells.length <= 1) return [...cells];
    const waypoints: [number, number][] = [cells[0]];
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

/**
 * Convert a layout response into the frontend's Placement format.
 * @param res - The layout response.
 * @returns Array of Placements.
 */
function placementsFromResponse(res: LayoutResponse): Placement[] {
    return res.components.map(c => {
        const p: Placement = { type: c.type };
        if (c.type === "conveyor") {
            p.path = cellsToWaypoints(c.cells);
            p.direction_in = c.direction_in ?? "up";
            p.direction_out = c.direction_out ?? "down";
        } else {
            p.pos = c.pos;
            p.rot = c.rot;
        }
        if (c.item) p.item = c.item;
        return p;
    });
}

/**
 * Push layout data into the renderer and update inventory / info bar.
 * @param res - The layout response.
 */
function applyLayoutResponse(res: LayoutResponse): void {
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

/**
 * Callback when placements change: stop auto-play, re-submit layout.
 * @param placements - Updated placements.
 */
async function onPlacementsChanged(placements: Placement[]): Promise<void> {
    stopAutoPlay();
    const res = await sendLayout(placements, inventory);
    if (!res.ok) {
        console.error("layout rejected:", res.error);
        return;
    }
    applyLayoutResponse(res);
}

/**
 * Callback from palette when inventory data is edited.
 * @param data - Updated inventory map.
 */
function onInventoryChanged(data: Record<string, number>): void {
    inventory = data;
    onPlacementsChanged(PlacementController.getPlacements());
}

/** Advance one tick and update the renderer. */
async function stepTick(): Promise<void> {
    const res = await tick(1);
    if (res.ok) {
        Renderer.setAnimDuration(autoPlaying ? tickInterval : 400);
        Renderer.setState(res.components);
        updateInfo(res.tick, res.components);
    }
}

/** Reset simulation to tick 0. */
async function resetAndRender(): Promise<void> {
    stopAutoPlay();
    const res = await resetSim();
    if (res.ok) {
        Renderer.setAnimDuration(0);
        Renderer.setState(res.components);
        updateInfo(res.tick, res.components);
    }
}

// ── Auto-play ──────────────────────────────────────────────────────

/** Toggle auto-play on/off. */
function toggleAutoPlay(): void {
    if (autoPlaying) {
        stopAutoPlay();
    } else {
        autoPlaying = true;
        document.getElementById("btn-play")!.textContent = "⏸";
        keepAutoPlaying();
    }
}

/** Stop auto-play and update the play button label. */
function stopAutoPlay(): void {
    autoPlaying = false;
    document.getElementById("btn-play")!.textContent = "▶";
}

/** Repeatedly tick while auto-play is active. */
async function keepAutoPlaying(): Promise<void> {
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
        if (wait > 0) await new Promise(r => setTimeout(r, wait));
    }
}

// ── Canvas interaction ─────────────────────────────────────────────

/**
 * Handle canvas click: placement mode, component selection, or RMB cancel.
 * @param e - Mouse event.
 * @param canvas - The canvas element.
 * @param btn - 0 = left, 2 = right.
 */
async function onCanvasClick(e: MouseEvent, canvas: HTMLCanvasElement,
                              btn: number): Promise<void> {
    const rect = canvas.getBoundingClientRect();
    const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
    const cell = Renderer.screenToCell(sx, sy);
    if (!cell) return;

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

/**
 * Handle canvas hover: update ghost preview and tooltip.
 * @param e - Mouse event.
 * @param canvas - The canvas element.
 * @param tip - Tooltip DOM element.
 */
function onCanvasHover(e: MouseEvent, canvas: HTMLCanvasElement,
                       tip: HTMLElement): void {
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
    const comp = Renderer.findComponentAt(cell)!;
    tip.style.display = "block";
    tip.style.left = `${e.clientX - rect.left + 12}px`;
    tip.style.top = `${e.clientY - rect.top - 10}px`;
    tip.textContent = `${comp.label}  @(${comp.pos[0]},${comp.pos[1]})  ${comp.rot}`;
}

// ── Keyboard ───────────────────────────────────────────────────────

/** Handle keyboard shortcuts. */
function onKey(e: KeyboardEvent): void {
    if (e.target instanceof HTMLInputElement) return;

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
            } else {
                PlacementController.cancel();
                Palette.clearSelection();
            }
            break;
    }
}

/** Rotate the pending placement, or the selected existing component. */
function onRotate(): void {
    // If in placement mode, rotate the pending placement
    const pMode = PlacementController.getMode();
    if (pMode.mode !== "idle") {
        PlacementController.onRotate();
        return;
    }
    // Otherwise, rotate selected component
    rotateSelectedExisting();
}

/** Rotate the currently selected existing component and re-submit. */
async function rotateSelectedExisting(): Promise<void> {
    if (selectedCompId == null) return;
    const comp = Renderer.findComponentById(selectedCompId);
    if (!comp) return;

    const placements = PlacementController.getPlacements();
    if (comp.type === "conveyor") {
        const dirSeq: [string, string][] = [
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
    } else {
        const rotOrder: Rotation[] = ["ROT_0", "ROT_1", "ROT_2", "ROT_3"];
        const idx = rotOrder.indexOf(comp.rot as Rotation);
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

/** Delete the currently selected component and re-submit. */
async function deleteSelected(): Promise<void> {
    if (selectedCompId == null) return;
    const comp = Renderer.findComponentById(selectedCompId);
    if (!comp) return;

    let placements = PlacementController.getPlacements();
    placements = placements.filter(p =>
        comp.type === "conveyor"
            ? !(p.path && p.path[0][0] === comp.pos[0] && p.path[0][1] === comp.pos[1])
            : !(p.pos && p.pos[0] === comp.pos[0] && p.pos[1] === comp.pos[1])
    );
    selectedCompId = null;
    Renderer.setSelected(null);

    PlacementController.setPlacements(placements);
    await onPlacementsChanged(placements);
}

// ── Blueprint save ──────────────────────────────────────────────────

/** Download current layout as a .blueprint JSON file. */
async function onSave(): Promise<void> {
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

/** Update the info bar with tick number, component count, and total items. */
function updateInfo(tick: number, comps: ComponentState[]): void {
    const totalItems = comps.reduce((s, c) => s + (c.count ?? c.inventory ?? 0), 0);
    infoEl.textContent = `Tick: ${tick}  |  Components: ${comps.length}  |  Items: ${totalItems}`;
}

// ── Boot ───────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", init);
