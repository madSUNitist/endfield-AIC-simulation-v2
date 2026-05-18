/** Integer 2-D grid coordinate. */
export interface Vec2 {
    x: number;
    y: number;
}

/** Clockwise rotation in 90-degree increments. */
export type Rotation = "ROT_0" | "ROT_1" | "ROT_2" | "ROT_3";

/** A single port on a layout component. */
export interface PortInfo {
    /** "input" or "output". */
    type: "input" | "output";
    /** Grid cell of the port. */
    cell: [number, number];
    /** Direction vector the port faces. */
    dir: [number, number];
}

/** A component as returned by the layout API. */
export interface LayoutComponent {
    id: number;
    type: string;
    label: string;
    pos: [number, number];
    rot: Rotation;
    /** All grid cells this component occupies. */
    cells: [number, number][];
    ports: PortInfo[];
    color: string;
    item?: string;
    direction_in?: string;
    direction_out?: string;
}

/** A directed edge between two components. */
export interface Edge {
    from: [number, number];
    to: [number, number];
}

/** Visible canvas viewport bounds. */
export interface Viewport {
    x0: number;
    y0: number;
    w: number;
    h: number;
}

/** A reference to a single item instance in a slot or buffer. */
export interface ItemRef {
    type: string;
    id: number;
}

/** Per-component dynamic state at a given tick. */
export interface ComponentState {
    id: number;
    type: string;
    can_pull: boolean;
    /** Slot contents for conveyors (index → ItemRef). */
    slot_map?: Record<string, ItemRef | null>;
    /** Single-slot buffer content (splitter, converger, stash). */
    buffer?: ItemRef | null;
    /** Remaining item count in depot loader / unloader. */
    inventory?: number;
    count?: number;
    item_type?: string;
}

/** Full simulation state at a given tick (from /api/tick). */
export interface TickState {
    tick: number;
    components: ComponentState[];
}

/** Combined layout + initial state response from /api/load or /api/layout. */
export interface LayoutResponse {
    ok: boolean;
    error?: string;
    components: LayoutComponent[];
    edges: Edge[];
    viewport: Viewport;
    tick: number;
    inventory?: Record<string, number>;
    components_state?: ComponentState[];
}

/** A component type available in the palette sidebar. */
export interface PaletteItem {
    type: string;
    label: string;
    color: string;
    /** (width, height) coverage in cells. */
    coverage: [number, number];
    ports: { type: string; offset: [number, number]; direction: string }[];
}

/** A single component placement being edited by the user. */
export interface Placement {
    pos?: [number, number];
    type: string;
    rot?: Rotation;
    item?: string;
    path?: [number, number][];
    direction_in?: string;
    direction_out?: string;
}

/** Placement state-machine mode. */
export type PlacementMode =
    /** Nothing is being placed. */
    | { mode: "idle" }
    /** Placing a non-conveyor (single-cell) component. */
    | { mode: "simple"; type: string; rot: Rotation; item?: string }
    /** Actively placing a conveyor belt path. */
    | {
          mode: "conveyor";
          waypoints: [number, number][];
          direction_in: string;
          direction_out: string;
          cornerChoice: 0 | 1;
          cornerA: [number, number][];
          cornerB: [number, number][];
          hoverCell: [number, number] | null;
      };

/** Ghost / preview data used by the renderer during placement. */
export interface GhostData {
    /** Occupied cells to highlight. */
    cells: [number, number][];
    color: string;
    /** Main ghost path polyline. */
    pathLine?: [number, number][];
    /** Alternate path polyline (corner preview). */
    altPathLine?: [number, number][];
    /** Number of confirmed (placed) cells along the path. */
    confirmedPathLength?: number;
    directionIn?: string;
    directionOut?: string;
    startCell?: [number, number];
    /** Port arrows rendered on ghost cells. */
    ghostPorts?: { cell: [number, number]; dir: string; type: "input" | "output" }[];
}
