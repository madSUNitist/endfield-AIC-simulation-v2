import type {
    LayoutResponse, TickState, PaletteItem, Placement, ComponentState,
} from "./types.js";

const BASE = "";

// ── REST wrappers ──────────────────────────────────────────────────

/** List available test case filenames. */
export async function fetchCases(): Promise<string[]> {
    const r = await fetch(`${BASE}/api/cases`);
    return r.json();
}

/** List component types for the palette. */
export async function fetchComponentTypes(): Promise<PaletteItem[]> {
    const r = await fetch(`${BASE}/api/component_types`);
    return r.json();
}

/** Load a test case and return full layout + initial state. */
export async function loadCase(name: string): Promise<LayoutResponse> {
    const r = await fetch(`${BASE}/api/load`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case: name }),
    });
    return r.json();
}

/** Submit a custom layout and reset to tick 0. */
export async function sendLayout(placements: Placement[], inventory: Record<string, number> = {}): Promise<LayoutResponse> {
    const r = await fetch(`${BASE}/api/layout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ components: placements, inventory }),
    });
    return r.json();
}

/** Advance N ticks and return component states. */
export async function tick(n: number = 1): Promise<{ ok: boolean; error?: string; tick: number; components: ComponentState[] }> {
    const r = await fetch(`${BASE}/api/tick`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ n }),
    });
    return r.json();
}

/** Reset simulation to tick 0. */
export async function resetSim(): Promise<{ ok: boolean; tick: number; components: ComponentState[] }> {
    const r = await fetch(`${BASE}/api/reset`, { method: "POST" });
    return r.json();
}
