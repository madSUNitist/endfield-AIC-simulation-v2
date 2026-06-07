import type { PaletteItem, Placement, Rotation, ComponentState, InventorySlot } from "./types.js";

interface PaletteConfig {
    container: HTMLElement;
    onSelect: (type: string | null) => void;
    onInventoryChange: (data: Record<string, number>) => void;
    onCompItemChange: (compId: number, itemType: string) => void;
    onCompInvChange: (slots: (InventorySlot)[]) => void;
}

// ── State ──────────────────────────────────────────────────────────

let items: PaletteItem[] = [];
let selectedType: string | null = null;
let selectedItemType: string = "ore";
/** Shared inventory snapshot (ordered slots from backend). */
let inventoryData: (InventorySlot)[] = [];
/** State of the currently-selected existing component (canvas selection). */
let selectedCompState: { id: number; type: string; count?: number; inventory?: number; item_type?: string; inventory_slots?: (InventorySlot)[] } | null = null;

const CATEGORY_ORDER = ["depot_access", "logistics_units"];
const CATEGORY_LABELS: Record<string, string> = {
    "depot_access": "Depot Access",
    "logistics_units": "Logistics Units",
};

let onSelect: ((type: string | null) => void) | null = null;
let onInventoryChange: ((data: Record<string, number>) => void) | null = null;
let onCompItemChange: ((compId: number, itemType: string) => void) | null = null;
let onCompInvChange: ((slots: (InventorySlot)[]) => void) | null = null;

// DOM refs
let container: HTMLElement;

/**
 * Initialise the palette sidebar UI.
 * @param config - Configuration object with container element and callbacks.
 */
export function init(config: PaletteConfig): void {
    container = config.container;
    onSelect = config.onSelect;
    onInventoryChange = config.onInventoryChange;
    onCompItemChange = config.onCompItemChange;
    onCompInvChange = config.onCompInvChange;
}

/**
 * Set palette items and re-render.
 * @param list - Array of PaletteItem metadata from the backend.
 */
export function setPaletteItems(list: PaletteItem[]): void {
    console.log("palette loaded:", list.length, "items");
    items = list;
    render();
}

/**
 * Set inventory data from external source (slot list from backend) and re-render.
 * @param data - Ordered array of InventorySlot entries.
 */
export function setInventoryData(data: (InventorySlot)[]): void {
    console.log("palette inventory set,", data.length, "slots");
    inventoryData = data;
    render();
}

/**
 * Set the selected existing component's live state (for per-unit inventory panel).
 * @param state - ComponentState with inventory fields, or null to clear.
 */
export function setSelectedCompState(state: { id: number; type: string; count?: number; inventory?: number; item_type?: string; inventory_slots?: (InventorySlot)[] } | null): void {
    selectedCompState = state;
    render();
}

// ── HTML builders ─────────────────────────────────────────────────

/** Re-render the entire palette sidebar DOM. */
function render(): void {
    container.innerHTML = buildHtml();
    bindEvents();
}

function buildHtml(): string {
    return buildPaletteListHtml()
         + buildConfigHtml()
         + buildUnitPanelHtml()
         + buildInventoryPanelHtml();
}

function buildPaletteListHtml(): string {
    let html = `<div class="palette-header">Components</div>`;
    html += `<div class="palette-list">`;
    const grouped = new Map<string, PaletteItem[]>();
    for (const item of items) {
        const cat = item.category || "other";
        if (!grouped.has(cat)) grouped.set(cat, []);
        grouped.get(cat)!.push(item);
    }
    for (const cat of CATEGORY_ORDER) {
        const catItems = grouped.get(cat);
        if (!catItems || catItems.length === 0) continue;
        html += `<div class="palette-category">${CATEGORY_LABELS[cat] ?? cat}</div>`;
        for (const item of catItems) {
            const active = item.type === selectedType ? " active" : "";
            html += `<div class="palette-item${active}" data-type="${item.type}" style="border-left:4px solid ${item.color}">`;
            html += `<span class="palette-label">${escapeHtml(item.label)}</span>`;
            html += `<span class="palette-meta">${item.coverage[0]}×${item.coverage[1]}</span>`;
            html += `</div>`;
        }
    }
    for (const [cat, catItems] of grouped) {
        if (cat === "other") {
            for (const item of catItems) {
                const active = item.type === selectedType ? " active" : "";
                html += `<div class="palette-item${active}" data-type="${item.type}" style="border-left:4px solid ${item.color}">`;
                html += `<span class="palette-label">${escapeHtml(item.label)}</span>`;
                html += `<span class="palette-meta">${item.coverage[0]}×${item.coverage[1]}</span>`;
                html += `</div>`;
            }
        }
    }
    html += `</div>`;
    return html;
}

function buildConfigHtml(): string {
    if (selectedType !== "depot_loader") return "";
    return `<div class="palette-config">`
         + `<label>Item: <input type="text" id="cfg-item-type" value="${escapeHtml(selectedItemType)}" size="6"></label>`
         + `</div>`;
}

function buildUnitPanelHtml(): string {
    if (!selectedCompState) return "";
    const cs = selectedCompState;
    const label = cs.type.replace(/_/g, " ");
    let html = `<div class="palette-header" style="margin-top:8px">Unit: ${escapeHtml(label)}</div>`;
    html += `<div class="comp-inv-panel">`;
    if (cs.type === "depot_loader") {
        html += `<div class="comp-inv-row">`;
        html += `<label>Item: <input class="comp-item-type" value="${escapeHtml(cs.item_type ?? "ore")}" size="6"></label>`;
        html += `</div>`;
        html += `<div class="comp-inv-row">`;
        html += `<span class="comp-inv-label">Loaded:</span>`;
        html += `<span class="comp-inv-val">${cs.count ?? 0}</span>`;
        html += `</div>`;
    } else if (cs.type === "depot_unloader") {
        html += `<div class="comp-inv-row">`;
        html += `<span class="comp-inv-label">Collected:</span>`;
        html += `<span class="comp-inv-val">${cs.count ?? 0}</span>`;
        html += `</div>`;
    } else if (cs.type === "protocol_stash") {
        if (cs.inventory_slots) {
            for (let i = 0; i < cs.inventory_slots.length; i++) {
                const slot = cs.inventory_slots[i];
                html += `<div class="inv-row" data-stash-slot="${i}">`;
                html += `<span class="inv-slot-idx">[${i}]</span>`;
                html += `<input class="inv-name" value="${slot ? escapeHtml(slot.type) : ''}" placeholder="item">`;
                html += `<input class="inv-count" value="${slot ? slot.count : 0}" placeholder="0">`;
                html += `<button class="inv-del">×</button>`;
                html += `</div>`;
            }
        } else {
            html += `<div class="comp-inv-row">`;
            html += `<span class="comp-inv-label">Stored:</span>`;
            html += `<span class="comp-inv-val">${cs.inventory ?? 0}</span>`;
            html += `</div>`;
        }
    } else if (cs.count !== undefined || cs.inventory !== undefined) {
        html += `<div class="comp-inv-row">`;
        html += `<span class="comp-inv-label">Count:</span>`;
        html += `<span class="comp-inv-val">${cs.count ?? cs.inventory ?? 0}</span>`;
        html += `</div>`;
    }
    html += `</div>`;
    return html;
}

function buildInventoryPanelHtml(): string {
    let html = `<div class="palette-header" style="margin-top:8px">Inventory</div>`;
    html += `<div class="inventory-panel">`;
    let visibleCount = 0;
    for (let i = 0; i < inventoryData.length; i++) {
        const slot = inventoryData[i];
        if (!slot) continue;
        visibleCount++;
        html += `<div class="inv-row" data-slot-index="${i}">`;
        html += `<span class="inv-slot-idx">[${i}]</span>`;
        html += `<input class="inv-name" value="${escapeHtml(slot.type)}" placeholder="item">`;
        html += `<input class="inv-count" value="${slot.count}" placeholder="0">`;
        html += `<button class="inv-del">×</button>`;
        html += `</div>`;
    }
    if (visibleCount === 0) {
        html += `<div class="inv-empty">(no items)</div>`;
    }
    html += `<button class="inv-add">+ Fill Slot</button>`;
    html += `</div>`;
    return html;
}

// ── Event binders ─────────────────────────────────────────────────

function bindEvents(): void {
    bindPaletteClicks();
    bindConfigInputs();
    bindUnitPanelEvents();
    bindInventoryEvents();
    bindFillButton();
}

function bindPaletteClicks(): void {
    for (const el of container.querySelectorAll(".palette-item")) {
        el.addEventListener("click", () => {
            const t = (el as HTMLElement).dataset.type!;
            if (selectedType === t) {
                selectedType = null;
            } else {
                selectedType = t;
            }
            if (onSelect) onSelect(selectedType);
            render();
        });
    }
}

function bindConfigInputs(): void {
    const itemInput = document.getElementById("cfg-item-type") as HTMLInputElement;
    if (itemInput) {
        itemInput.addEventListener("change", () => { selectedItemType = itemInput.value; });
    }
}

function bindUnitPanelEvents(): void {
    // Per-unit item type input (depot_loader)
    const compItemInput = container.querySelector(".comp-item-type") as HTMLInputElement;
    if (compItemInput && selectedCompState) {
        const compId = selectedCompState.id;
        compItemInput.addEventListener("change", () => {
            if (onCompItemChange) onCompItemChange(compId, compItemInput.value.trim());
        });
    }

    // Stash slot inputs (protocol_stash editable inventory)
    for (const row of container.querySelectorAll("[data-stash-slot]")) {
        const slotIdx = parseInt((row as HTMLElement).dataset.stashSlot ?? "-1");
        if (slotIdx < 0 || !selectedCompState?.inventory_slots) continue;
        const typeIn = row.querySelector(".inv-name") as HTMLInputElement | null;
        const countIn = row.querySelector(".inv-count") as HTMLInputElement | null;
        const delBtn = row.querySelector(".inv-del") as HTMLButtonElement | null;

        if (typeIn) {
            typeIn.addEventListener("change", () => {
                const slots = selectedCompState!.inventory_slots!;
                const val = typeIn.value.trim();
                if (val) {
                    if (slots[slotIdx]) {
                        slots[slotIdx]!.type = val;
                    } else {
                        slots[slotIdx] = { type: val, count: 1 };
                    }
                } else {
                    slots[slotIdx] = null;
                }
                emitStashSlots();
                render();
            });
        }
        if (countIn) {
            countIn.addEventListener("change", () => {
                const slots = selectedCompState!.inventory_slots!;
                const val = parseInt(countIn.value) || 0;
                if (val <= 0) {
                    slots[slotIdx] = null;
                } else if (slots[slotIdx]) {
                    slots[slotIdx]!.count = val;
                } else {
                    slots[slotIdx] = { type: "item", count: val };
                }
                emitStashSlots();
                render();
            });
        }
        if (delBtn) {
            delBtn.addEventListener("click", () => {
                const slots = selectedCompState!.inventory_slots!;
                slots[slotIdx] = null;
                emitStashSlots();
                render();
            });
        }
    }
}

function bindInventoryEvents(): void {
    for (const row of container.querySelectorAll(".inv-row")) {
        const slotIdx = parseInt((row as HTMLElement).dataset.slotIndex ?? "-1");
        if (slotIdx < 0) continue;
        const nameIn = row.querySelector(".inv-name") as HTMLInputElement | null;
        const countIn = row.querySelector(".inv-count") as HTMLInputElement | null;
        const delBtn = row.querySelector(".inv-del") as HTMLButtonElement | null;

        if (nameIn) {
            nameIn.addEventListener("change", () => {
                const val = nameIn.value.trim();
                if (val) {
                    const existing = inventoryData[slotIdx];
                    if (existing) {
                        existing.type = val;
                    } else {
                        inventoryData[slotIdx] = { type: val, count: 0 };
                    }
                }
                emitInventory();
                render();
            });
        }

        if (countIn) {
            countIn.addEventListener("change", () => {
                const val = parseInt(countIn.value) || 0;
                const existing = inventoryData[slotIdx];
                if (existing) {
                    existing.count = val;
                    if (val <= 0) inventoryData[slotIdx] = null;
                }
                emitInventory();
                render();
            });
        }

        if (delBtn) {
            delBtn.addEventListener("click", () => {
                inventoryData[slotIdx] = null;
                emitInventory();
                render();
            });
        }
    }
}

function bindFillButton(): void {
    const fillBtn = container.querySelector(".inv-add") as HTMLButtonElement;
    if (!fillBtn) return;
    fillBtn.addEventListener("click", () => {
        const idx = inventoryData.findIndex(s => s === null);
        if (idx >= 0) {
            inventoryData[idx] = { type: "item", count: 0 };
            emitInventory();
            render();
            setTimeout(() => {
                const rows = container.querySelectorAll(".inv-row");
                for (const row of rows) {
                    if (parseInt((row as HTMLElement).dataset.slotIndex ?? "-1") === idx) {
                        (row.querySelector(".inv-name") as HTMLInputElement)?.focus();
                        break;
                    }
                }
            }, 0);
        }
    });
}

/** Emit per-unit stash slot changes via callback. */
function emitStashSlots(): void {
    if (onCompInvChange && selectedCompState?.inventory_slots) {
        onCompInvChange(selectedCompState.inventory_slots);
    }
}

/** Emit current inventory data (slot list → merged type:count dict) via the callback. */
function emitInventory(): void {
    const out: Record<string, number> = {};
    for (const slot of inventoryData) {
        if (slot && slot.type) {
            out[slot.type] = (out[slot.type] || 0) + slot.count;
        }
    }
    if (onInventoryChange) onInventoryChange(out);
}

/** Basic HTML entity escaping for user-provided strings. */
function escapeHtml(s: string): string {
    return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * Return the currently selected component type.
 * @returns Type string or null if nothing selected.
 */
export function getSelectedType(): string | null {
    return selectedType;
}

/**
 * Return the currently configured item type (for depot_loader).
 * @returns Item type string (default "ore").
 */
export function getSelectedItemType(): string {
    return selectedItemType;
}

/**
 * Clear palette selection and re-render.
 */
export function clearSelection(): void {
    console.log("palette selection cleared");
    selectedType = null;
    selectedCompState = null;
    if (onSelect) onSelect(null);
    render();
}

/**
 * Explicitly set selection by type name.
 * @param t - Type string to select, or null to clear.
 */
export function setSelectedType(t: string | null): void {
    console.log("palette selected:", t);
    selectedType = t;
    if (onSelect) onSelect(t);
    render();
}

/** Rotation → (direction_in, direction_out) for single-cell conveyors. */
const DIR_FROM_ROT: Record<string, [string, string]> = {
    "ROT_0": ["up", "down"],
    "ROT_1": ["right", "left"],
    "ROT_2": ["down", "up"],
    "ROT_3": ["left", "right"],
};

/** Build a Placement object for the selected type at the given cell. */
export function buildPlacement(pos: [number, number], rot: Rotation): Placement | null {
    if (!selectedType) return null;
    const p: Placement = { type: selectedType };
    if (selectedType === "conveyor") {
        p.path = [pos];
        const [di, dout] = DIR_FROM_ROT[rot] ?? ["down", "up"];
        p.direction_in = di;
        p.direction_out = dout;
    } else {
        p.pos = pos;
        p.type = selectedType;
        p.rot = rot;
    }
    if (selectedType === "depot_loader") {
        p.item = selectedItemType;
    }
    return p;
}
