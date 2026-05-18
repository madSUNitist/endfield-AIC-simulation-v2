import type {
    LayoutResponse, TickState, PaletteItem, Placement, ComponentState,
} from "./types.js";

const BASE = "";

// ── REST wrappers ──────────────────────────────────────────────────

/**
 * List available test case filenames.
 * @returns Array of case name strings.
 */
export async function fetchCases(): Promise<string[]> {
    const r = await fetch(`${BASE}/api/cases`);
    return r.json();
}

/**
 * List component types for the palette sidebar.
 * @returns Array of PaletteItem metadata.
 */
export async function fetchComponentTypes(): Promise<PaletteItem[]> {
    const r = await fetch(`${BASE}/api/component_types`);
    return r.json();
}

/**
 * Load a test case by name and return full layout + initial state.
 * @param name - Test case stem (without .json extension).
 * @returns Full LayoutResponse including viewport, edges, and initial state.
 */
export async function loadCase(name: string): Promise<LayoutResponse> {
    const r = await fetch(`${BASE}/api/load`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case: name }),
    });
    return r.json();
}

/**
 * Create a blank (empty) map.
 * @returns LayoutResponse with zero components.
 */
export async function fetchBlank(): Promise<LayoutResponse> {
    const r = await fetch(`${BASE}/api/blank`, { method: "POST" });
    return r.json();
}

/**
 * Submit a custom layout and reset the simulation to tick 0.
 * @param placements - Array of component placements to submit.
 * @param inventory - Initial inventory counts keyed by item type.
 * @returns LayoutResponse for the newly built simulation.
 */
export async function sendLayout(placements: Placement[], inventory: Record<string, number> = {}): Promise<LayoutResponse> {
    const r = await fetch(`${BASE}/api/layout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ components: placements, inventory }),
    });
    return r.json();
}

/**
 * Save the current layout as a blueprint array.
 * @returns Bare blueprint component-entry array.
 */
export async function saveBlueprint(): Promise<object[]> {
    const r = await fetch(`${BASE}/api/save`);
    return r.json();
}

/**
 * Load a blueprint array and build a simulation from it.
 * @param data - Blueprint array of component entries.
 * @returns LayoutResponse for the loaded blueprint.
 */
export async function loadBlueprint(data: object[]): Promise<LayoutResponse> {
    const r = await fetch(`${BASE}/api/load-blueprint`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return r.json();
}

/**
 * Advance the simulation by N ticks and return component states.
 * @param n - Number of ticks to advance (default 1).
 * @returns Tick response with per-component state array.
 */
export async function tick(n: number = 1): Promise<{ ok: boolean; error?: string; tick: number; components: ComponentState[] }> {
    const r = await fetch(`${BASE}/api/tick`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ n }),
    });
    return r.json();
}

/**
 * Reset simulation to tick 0.
 * @returns Reset response with initial component states.
 */
export async function resetSim(): Promise<{ ok: boolean; tick: number; components: ComponentState[] }> {
    const r = await fetch(`${BASE}/api/reset`, { method: "POST" });
    return r.json();
}
