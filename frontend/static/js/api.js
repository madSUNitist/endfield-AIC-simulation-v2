const BASE = "";
// ── REST wrappers ──────────────────────────────────────────────────
/** List available test case filenames. */
export async function fetchCases() {
    const r = await fetch(`${BASE}/api/cases`);
    return r.json();
}
/** List component types for the palette. */
export async function fetchComponentTypes() {
    const r = await fetch(`${BASE}/api/component_types`);
    return r.json();
}
/** Load a test case and return full layout + initial state. */
export async function loadCase(name) {
    const r = await fetch(`${BASE}/api/load`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case: name }),
    });
    return r.json();
}
/** Create a blank (empty) map. */
export async function fetchBlank() {
    const r = await fetch(`${BASE}/api/blank`, { method: "POST" });
    return r.json();
}
/** Submit a custom layout and reset to tick 0. */
export async function sendLayout(placements, inventory = {}) {
    const r = await fetch(`${BASE}/api/layout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ components: placements, inventory }),
    });
    return r.json();
}
/** Save current layout as blueprint array. */
export async function saveBlueprint() {
    const r = await fetch(`${BASE}/api/save`);
    return r.json();
}
/** Load a blueprint (array of component entries). */
export async function loadBlueprint(data) {
    const r = await fetch(`${BASE}/api/load-blueprint`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return r.json();
}
/** Advance N ticks and return component states. */
export async function tick(n = 1) {
    const r = await fetch(`${BASE}/api/tick`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ n }),
    });
    return r.json();
}
/** Reset simulation to tick 0. */
export async function resetSim() {
    const r = await fetch(`${BASE}/api/reset`, { method: "POST" });
    return r.json();
}
//# sourceMappingURL=api.js.map