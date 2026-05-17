// ── World coordinate types ─────────────────────────────────────────

export interface Vec2 {
    x: number;
    y: number;
}

export type Rotation = "ROT_0" | "ROT_1" | "ROT_2" | "ROT_3";

// ── Layout (from backend) ──────────────────────────────────────────

export interface PortInfo {
    type: "input" | "output";
    cell: [number, number];
    dir: [number, number];   // direction vector in sim coords
}

export interface LayoutComponent {
    id: number;
    type: string;
    label: string;
    pos: [number, number];
    rot: Rotation;
    cells: [number, number][];
    ports: PortInfo[];
    color: string;
    item?: string;
    direction_in?: string;
    direction_out?: string;
}

export interface Edge {
    from: [number, number];
    to: [number, number];
}

export interface Viewport {
    x0: number;
    y0: number;
    w: number;
    h: number;
}

// ── Per-tick state (from backend) ──────────────────────────────────

export interface ItemRef {
    type: string;
    id: number;
}

export interface ComponentState {
    id: number;
    type: string;
    can_pull: boolean;
    slot_map?: Record<string, ItemRef | null>;
    buffer?: ItemRef | null;
    inventory?: number;
    count?: number;
    item_type?: string;
}

export interface TickState {
    tick: number;
    components: ComponentState[];
}

// ── Full layout response (layout + state at tick 0) ────────────────

export interface LayoutResponse {
    ok: boolean;
    error?: string;
    components: LayoutComponent[];
    edges: Edge[];
    viewport: Viewport;
    tick: number;
    components_state?: ComponentState[];
}

// ── Palette item (from /api/component_types) ───────────────────────

export interface PaletteItem {
    type: string;
    label: string;
    color: string;
    coverage: [number, number];
    ports: { type: string; offset: [number, number]; direction: string }[];
}

// ── Placement (frontend editing state) ─────────────────────────────

export interface Placement {
    pos?: [number, number];
    type: string;
    rot?: Rotation;
    item?: string;
    path?: [number, number][];
    direction_in?: string;
    direction_out?: string;
}
