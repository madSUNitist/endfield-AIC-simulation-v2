import type { PaletteItem, Placement, Rotation } from "./types.js";

// ── State ──────────────────────────────────────────────────────────

let items: PaletteItem[] = [];
let selectedType: string | null = null;
let selectedItemType: string = "ore";

let onSelect: ((type: string | null) => void) | null = null;

// DOM refs
let container: HTMLElement;

/** Initialise the palette sidebar UI. */
export function init(el: HTMLElement, cb: (type: string | null) => void): void {
    container = el;
    onSelect = cb;
}

/** Set palette items and re-render. */
export function setPaletteItems(list: PaletteItem[]): void {
    items = list;
    render();
}

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

    container.innerHTML = html;

    // Bind clicks
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
}

/** Return the currently selected component type. */
export function getSelectedType(): string | null {
    return selectedType;
}

/** Rotation → (direction_in, direction_out) for single-cell conveyors.
 *
 * Conveyors default to direction_in="up", direction_out="down" at ROT_0.
 * Each 90° clockwise rotation shifts both ports clockwise.
 */
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
