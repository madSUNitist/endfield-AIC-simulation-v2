import type { PaletteItem, Placement, Rotation } from "./types.js";

// ── State ──────────────────────────────────────────────────────────

let items: PaletteItem[] = [];
let selectedType: string | null = null;
let selectedItemType: string = "ore";
let inventoryData: Record<string, string> = {};

let onSelect: ((type: string | null) => void) | null = null;
let onInventoryChange: ((data: Record<string, number>) => void) | null = null;

// DOM refs
let container: HTMLElement;

/**
 * Initialise the palette sidebar UI.
 * @param el - The container DOM element.
 * @param cb - Called when palette selection changes.
 * @param invCb - Called when inventory data changes.
 */
export function init(el: HTMLElement,
                     cb: (type: string | null) => void,
                     invCb: (data: Record<string, number>) => void): void {
    container = el;
    onSelect = cb;
    onInventoryChange = invCb;
}

/**
 * Set palette items and re-render.
 * @param list - Array of PaletteItem metadata from the backend.
 */
export function setPaletteItems(list: PaletteItem[]): void {
    items = list;
    render();
}

/**
 * Set inventory data from external source and re-render.
 * @param data - Inventory counts keyed by item type.
 */
export function setInventoryData(data: Record<string, number>): void {
    const s: Record<string, string> = {};
    for (const [k, v] of Object.entries(data)) {
        s[k] = String(v);
    }
    inventoryData = s;
    render();
}

/** Re-render the entire palette sidebar DOM. */
function render(): void {
    let html = `<div class="palette-header">Components</div>`;
    html += `<div class="palette-list">`;
    for (const item of items) {
        const active = item.type === selectedType ? " active" : "";
        html += `<div class="palette-item${active}" data-type="${item.type}" style="border-left:4px solid ${item.color}">`;
        html += `<span class="palette-label">${item.label}</span>`;
        html += `<span class="palette-meta">${item.coverage[0]}×${item.coverage[1]}</span>`;
        html += `</div>`;
    }
    html += `</div>`;

    // Config fields
    if (selectedType === "depot_loader") {
        html += `<div class="palette-config">`;
        html += `<label>Item: <input type="text" id="cfg-item-type" value="${selectedItemType}" size="6"></label>`;
        html += `</div>`;
    }

    // Inventory panel
    html += `<div class="palette-header" style="margin-top:8px">Inventory</div>`;
    html += `<div class="inventory-panel">`;
    const entries = Object.entries(inventoryData);
    if (entries.length === 0) {
        html += `<div class="inv-empty">(empty)</div>`;
    }
    for (const [name, count] of entries) {
        html += `<div class="inv-row">`;
        html += `<input class="inv-name" value="${escapeHtml(name)}" placeholder="item">`;
        html += `<input class="inv-count" value="${count}" placeholder="0">`;
        html += `<button class="inv-del" data-inv-key="${escapeHtml(name)}">×</button>`;
        html += `</div>`;
    }
    html += `<button class="inv-add">+ Add Row</button>`;
    html += `</div>`;

    container.innerHTML = html;

    // Bind palette clicks
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

    // Bind config inputs
    const itemInput = document.getElementById("cfg-item-type") as HTMLInputElement;
    if (itemInput) {
        itemInput.addEventListener("change", () => { selectedItemType = itemInput.value; });
    }

    // Bind inventory inputs (delegated to avoid stale references)
    for (const row of container.querySelectorAll(".inv-row")) {
        const nameIn = row.querySelector(".inv-name") as HTMLInputElement;
        const countIn = row.querySelector(".inv-count") as HTMLInputElement;
        const delBtn = row.querySelector(".inv-del") as HTMLButtonElement;

        const commit = () => {
            const key = nameIn.value.trim();
            const val = parseInt(countIn.value) || 0;
            if (key) {
                inventoryData[key] = String(val);
            }
            // Remove entry if name was cleared
            for (const k of Object.keys(inventoryData)) {
                if (k !== key && !container.querySelector(`[data-inv-key="${escapeHtml(k)}"]`)) {
                    // already removed via delete
                }
            }
            emitInventory();
        };

        nameIn.addEventListener("change", () => {
            const oldKey = delBtn.dataset.invKey ?? "";
            const newKey = nameIn.value.trim();
            if (newKey && newKey !== oldKey) {
                delete inventoryData[oldKey];
                inventoryData[newKey] = countIn.value;
                delBtn.dataset.invKey = newKey;
            }
            emitInventory();
            render();
        });

        countIn.addEventListener("change", () => {
            inventoryData[delBtn.dataset.invKey ?? ""] = countIn.value;
            emitInventory();
        });

        delBtn.addEventListener("click", () => {
            const key = delBtn.dataset.invKey ?? "";
            delete inventoryData[key];
            emitInventory();
            render();
        });
    }

    // Bind add row
    const addBtn = container.querySelector(".inv-add") as HTMLButtonElement;
    if (addBtn) {
        addBtn.addEventListener("click", () => {
            // Find a unique key
            let n = 1;
            while (inventoryData[`item${n}`]) n++;
            inventoryData[`item${n}`] = "0";
            emitInventory();
            render();
            // Focus the new row's name input
            const rows = container.querySelectorAll(".inv-row");
            const lastRow = rows[rows.length - 1];
            if (lastRow) (lastRow.querySelector(".inv-name") as HTMLInputElement)?.focus();
        });
    }
}

/** Emit current inventory data via the callback. */
function emitInventory(): void {
    const out: Record<string, number> = {};
    for (const [k, v] of Object.entries(inventoryData)) {
        if (k.trim()) out[k.trim()] = parseInt(v) || 0;
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
    selectedType = null;
    if (onSelect) onSelect(null);
    render();
}

/**
 * Explicitly set selection by type name.
 * @param t - Type string to select, or null to clear.
 */
export function setSelectedType(t: string | null): void {
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
