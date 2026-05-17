import {
    fetchCases, fetchComponentTypes, loadCase, sendLayout, tick, resetSim,
} from "./api.js";
import type { LayoutResponse, ComponentState, Placement, Rotation } from "./types.js";
import * as Renderer from "./renderer.js";
import * as Palette from "./palette.js";

// ── State ──────────────────────────────────────────────────────────

let autoPlaying = false;
let tickInterval = 2000;
let placements: Placement[] = [];
let inventory: Record<string, number> = { ore: 9999 };
let selectedCompId: number | null = null;
let wasDragged = false;
let pointerDownPos = { x: 0, y: 0 };

// DOM refs
let caseSelect: HTMLSelectElement;
let speedSlider: HTMLInputElement;
let speedLabel: HTMLElement;
let infoEl: HTMLElement;

// ── Init ───────────────────────────────────────────────────────────

async function init(): Promise<void> {
    const canvas = document.getElementById("canvas") as HTMLCanvasElement;
    const tooltipEl = document.getElementById("tooltip") as HTMLElement;
    infoEl = document.getElementById("info") as HTMLElement;
    caseSelect = document.getElementById("case-select") as HTMLSelectElement;
    speedSlider = document.getElementById("speed-slider") as HTMLInputElement;
    speedLabel = document.getElementById("speed-label") as HTMLElement;

    Renderer.init(canvas, tooltipEl);
    Palette.init(
        document.getElementById("palette") as HTMLElement,
        () => {},
    );

    const cases = await fetchCases();
    for (const c of cases) {
        const opt = document.createElement("option");
        opt.value = c;
        opt.textContent = c;
        caseSelect.appendChild(opt);
    }

    const types = await fetchComponentTypes();
    Palette.setPaletteItems(types);

    if (cases.length > 0) {
        caseSelect.value = cases[0];
        await loadAndRender(cases[0]);
    }

    caseSelect.addEventListener("change", async () => {
        stopAutoPlay();
        await loadAndRender(caseSelect.value);
    });

    speedSlider.addEventListener("input", () => {
        const val = parseInt(speedSlider.value);
        tickInterval = 2000 / val;
        speedLabel.textContent = `${val}x`;
    });

    document.addEventListener("keydown", onKey);

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
        await onCanvasClick(e, canvas);
    });

    canvas.addEventListener("wheel", (e) => {
        e.preventDefault();
        const rect = canvas.getBoundingClientRect();
        const cx = (e.clientX - rect.left) * (canvas.width / rect.width);
        const cy = (e.clientY - rect.top) * (canvas.height / rect.height);
        Renderer.handleWheel(e.deltaY, cx, cy);
    }, { passive: false });

    canvas.addEventListener("mouseleave", () => { tooltipEl.style.display = "none"; });

    document.getElementById("btn-step")!.addEventListener("click", () => stepTick());
    document.getElementById("btn-play")!.addEventListener("click", () => toggleAutoPlay());
    document.getElementById("btn-reset")!.addEventListener("click", () => resetAndRender());

    window.addEventListener("resize", () => Renderer.resize());
    Renderer.resize();
}

// ── Load / state ───────────────────────────────────────────────────

async function loadAndRender(name: string): Promise<void> {
    const res = await loadCase(name);
    if (!res.ok) { console.error("load failed", res.error); return; }
    placements = placementsFromResponse(res);
    selectedCompId = null;
    Renderer.resetView();
    applyLayoutResponse(res);
}

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

function applyLayoutResponse(res: LayoutResponse): void {
    Renderer.setData(res.components, res.edges, res.viewport);
    Renderer.setSelected(null);
    const cs = res.components_state ?? [];
    Renderer.setAnimDuration(0);
    Renderer.setState(cs);
    updateInfo(res.tick, cs);
}

async function stepTick(): Promise<void> {
    const res = await tick(1);
    if (res.ok) {
        Renderer.setAnimDuration(autoPlaying ? tickInterval : 400);
        Renderer.setState(res.components);
        updateInfo(res.tick, res.components);
    }
}

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

function toggleAutoPlay(): void {
    if (autoPlaying) {
        stopAutoPlay();
    } else {
        autoPlaying = true;
        document.getElementById("btn-play")!.textContent = "⏸";
        keepAutoPlaying();
    }
}

function stopAutoPlay(): void {
    autoPlaying = false;
    document.getElementById("btn-play")!.textContent = "▶";
}

async function keepAutoPlaying(): Promise<void> {
    while (autoPlaying) {
        const t0 = performance.now();
        const res = await tick(1);
        if (res.ok) {
            Renderer.setAnimDuration(tickInterval);
            Renderer.setState(res.components);
            updateInfo(res.tick, res.components);
        }
        const wait = Math.max(0, tickInterval - (performance.now() - t0));
        if (wait > 0) await new Promise(r => setTimeout(r, wait));
    }
}

// ── Canvas clicks ──────────────────────────────────────────────────

async function onCanvasClick(e: MouseEvent, canvas: HTMLCanvasElement): Promise<void> {
    const rect = canvas.getBoundingClientRect();
    const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
    const cell = Renderer.screenToCell(sx, sy);
    if (!cell) return;

    const existing = Renderer.findComponentAt(cell);
    if (existing) {
        stopAutoPlay();
        selectedCompId = existing.id;
        Renderer.setSelected(existing.id);
        Renderer.draw();
        return;
    }

    const selType = Palette.getSelectedType();
    if (!selType) return;

    stopAutoPlay();
    selectedCompId = null;
    Renderer.setSelected(null);

    const placement = Palette.buildPlacement(cell, "ROT_0");
    if (!placement) return;

    placements.push(placement);
    const res = await sendLayout(placements, inventory);
    if (!res.ok) {
        placements.pop();
        console.error("layout rejected:", res.error);
        return;
    }
    placements = placementsFromResponse(res);
    applyLayoutResponse(res);
}

function onCanvasHover(e: MouseEvent, canvas: HTMLCanvasElement, tip: HTMLElement): void {
    const rect = canvas.getBoundingClientRect();
    const sx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const sy = (e.clientY - rect.top) * (canvas.height / rect.height);
    const cell = Renderer.screenToCell(sx, sy);
    if (!cell) { tip.style.display = "none"; return; }

    const comp = Renderer.findComponentAt(cell);
    if (!comp) { tip.style.display = "none"; return; }

    tip.style.display = "block";
    tip.style.left = `${e.clientX - rect.left + 12}px`;
    tip.style.top = `${e.clientY - rect.top - 10}px`;
    tip.textContent = `${comp.label}  @(${comp.pos[0]},${comp.pos[1]})  ${comp.rot}`;
}

// ── Keyboard ───────────────────────────────────────────────────────

function onKey(e: KeyboardEvent): void {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;

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
            rotateSelected();
            break;
        case "Delete":
        case "Backspace":
            e.preventDefault();
            stopAutoPlay();
            deleteSelected();
            break;
    }
}

async function rotateSelected(): Promise<void> {
    if (selectedCompId == null) return;
    const comp = Renderer.findComponentById(selectedCompId);
    if (!comp) return;

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

    const res = await sendLayout(placements, inventory);
    if (!res.ok) return;
    placements = placementsFromResponse(res);
    applyLayoutResponse(res);
}

async function deleteSelected(): Promise<void> {
    if (selectedCompId == null) return;
    const comp = Renderer.findComponentById(selectedCompId);
    if (!comp) return;

    placements = placements.filter(p =>
        comp.type === "conveyor"
            ? !(p.path && p.path[0][0] === comp.pos[0] && p.path[0][1] === comp.pos[1])
            : !(p.pos && p.pos[0] === comp.pos[0] && p.pos[1] === comp.pos[1])
    );
    selectedCompId = null;
    Renderer.setSelected(null);

    const res = await sendLayout(placements, inventory);
    if (!res.ok) return;
    placements = placementsFromResponse(res);
    applyLayoutResponse(res);
}

// ── Info bar ───────────────────────────────────────────────────────

function updateInfo(tick: number, comps: ComponentState[]): void {
    const totalItems = comps.reduce((s, c) => s + (c.count ?? c.inventory ?? 0), 0);
    infoEl.textContent = `Tick: ${tick}  |  Components: ${comps.length}  |  Items: ${totalItems}`;
}

// ── Boot ───────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", init);
