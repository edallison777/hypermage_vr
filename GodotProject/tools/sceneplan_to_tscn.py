#!/usr/bin/env python3
"""
ScenePlan JSON  →  Godot 4 .tscn converter

Coordinate conventions
  ScenePlan : Unreal Engine (X-forward, Y-right, Z-up, centimetres)
  Godot     : (X-right, Y-up, Z-back, metres)
  Mapping   : ue_pos(x, y, z)  →  godot(x/100,  z/100, -y/100)
              ue_extents(ex,ey,ez) →  godot_size(ex*2/100, ez*2/100, ey*2/100)

Usage
  python sceneplan_to_tscn.py dungeon_cell.json
  python sceneplan_to_tscn.py dungeon_cell.json -o scenes/generated/room.tscn
  python sceneplan_to_tscn.py dungeon_cell.json --vr        # include XR rig for Quest 3
  cat scene.json | python sceneplan_to_tscn.py -
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import uuid
from pathlib import Path

# ── Coordinate helpers ────────────────────────────────────────────────────────

def ue_pos(x: float, y: float, z: float) -> tuple[float, float, float]:
    """UE position (cm, Z-up) → Godot position (m, Y-up)."""
    return x / 100.0, z / 100.0, -y / 100.0


def ue_ext(ex: float, ey: float, ez: float) -> tuple[float, float, float]:
    """UE half-extents (cm) → Godot full size (m)."""
    return ex * 2 / 100.0, ez * 2 / 100.0, ey * 2 / 100.0


def t3d(tx: float = 0, ty: float = 0, tz: float = 0) -> str:
    """Identity Transform3D with translation."""
    return f"Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {tx:.4f}, {ty:.4f}, {tz:.4f})"


def t3d_axes(
    xa: tuple[float, float, float],
    ya: tuple[float, float, float],
    za: tuple[float, float, float],
    o:  tuple[float, float, float],
) -> str:
    """Transform3D from explicit basis columns (local X/Y/Z axes) + origin.

    Godot serialises a Transform3D row-major: the first three numbers are the
    X-components of the three basis vectors, etc. Used for the tilted stair ramp.
    """
    return (
        f"Transform3D({xa[0]:.5f}, {ya[0]:.5f}, {za[0]:.5f}, "
        f"{xa[1]:.5f}, {ya[1]:.5f}, {za[1]:.5f}, "
        f"{xa[2]:.5f}, {ya[2]:.5f}, {za[2]:.5f}, "
        f"{o[0]:.4f}, {o[1]:.4f}, {o[2]:.4f})"
    )


def v3(x: float, y: float, z: float) -> str:
    return f"Vector3({x:.4f}, {y:.4f}, {z:.4f})"


def col(r: float, g: float, b: float, a: float = 1.0) -> str:
    return f"Color({r:.3f}, {g:.3f}, {b:.3f}, {a:.3f})"


# ── Zone-type colour palette ──────────────────────────────────────────────────

_ZONE_RGB: dict[str, tuple[float, float, float]] = {
    "exploration": (0.50, 0.50, 0.60),
    "ritual":      (0.30, 0.20, 0.50),
    "social":      (0.40, 0.60, 0.40),
    "sanctuary":   (0.60, 0.60, 0.50),
    "cyberspace":  (0.10, 0.30, 0.60),
    "narrative":   (0.50, 0.40, 0.30),
    "combat":      (0.60, 0.20, 0.20),
    "objective":   (0.60, 0.55, 0.20),
    "spawn":       (0.30, 0.55, 0.30),
    "transition":  (0.40, 0.40, 0.40),
}

_INTERACTABLE_RGB: dict[str, tuple[float, float, float]] = {
    "artefact":     (0.90, 0.80, 0.10),  # gold
    "machinery":    (0.40, 0.50, 0.60),  # steel blue
    "creature":     (0.70, 0.20, 0.20),  # red
    "environmental":(0.30, 0.60, 0.50),  # teal
}

WALL_DIM  = 0.30  # wall/floor/ceiling thickness in metres
DOOR_W    = 1.60  # doorway opening width in metres
DOOR_H    = 2.20  # doorway opening height in metres (from floor)
ADJ_TOL   = 0.60  # max gap between zone faces to treat them as adjacent (metres)

# Walkable surfaces (floors + stair ramps) carry collision bit 1 (default block) AND
# bit 3, so locomotion's downward floor-probe (mask = bit 3 only) finds them while
# ignoring walls, the player's own body, and grabbables. Must match WALKABLE_MASK in
# scripts/locomotion.gd (1 << 2 == 4).
WALKABLE_LAYER = 1 | (1 << 2)   # = 5

STEP_RISE  = 0.18  # height gained per visible step (m)
STEP_GOING = 0.30  # horizontal depth per step (m); rise:going sets the incline


# ── .tscn builder ─────────────────────────────────────────────────────────────

class TscnBuilder:
    """Accumulates sub-resources and nodes, emits a .tscn string."""

    def __init__(self) -> None:
        self._ext: list[str] = []
        self._sub: list[str] = []
        self._nodes: list[str] = []
        self._counter = 0
        self._ext_by_path: dict[str, str] = {}

    # ── external resource factories ───────────────────────────────────────────

    def ext_resource(self, rtype: str, path: str, rid: str) -> str:
        self._ext.append(f'[ext_resource type="{rtype}" path="{path}" id="{rid}"]\n')
        self._ext_by_path[path] = rid
        return rid

    def script_resource(self, path: str) -> str:
        """Get-or-create an ext_resource for a script, returning its id."""
        if path in self._ext_by_path:
            return self._ext_by_path[path]
        rid = f"ExtScript_{len(self._ext_by_path) + 1}"
        return self.ext_resource("Script", path, rid)

    # ── sub-resource factories ────────────────────────────────────────────────

    def _id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def box_mesh(self, sx: float, sy: float, sz: float) -> str:
        rid = self._id("BoxMesh")
        self._sub.append(
            f'[sub_resource type="BoxMesh" id="{rid}"]\n'
            f'size = {v3(sx, sy, sz)}\n'
        )
        return rid

    def sphere_mesh(self, radius: float) -> str:
        rid = self._id("SphereMesh")
        self._sub.append(
            f'[sub_resource type="SphereMesh" id="{rid}"]\n'
            f'radius = {radius:.4f}\n'
            f'height = {radius * 2:.4f}\n'
        )
        return rid

    def cylinder_mesh(self, radius: float, height: float) -> str:
        rid = self._id("CylinderMesh")
        self._sub.append(
            f'[sub_resource type="CylinderMesh" id="{rid}"]\n'
            f'top_radius = {radius:.4f}\n'
            f'bottom_radius = {radius:.4f}\n'
            f'height = {height:.4f}\n'
        )
        return rid

    def material(self, r: float, g: float, b: float) -> str:
        rid = self._id("StandardMaterial3D")
        self._sub.append(
            f'[sub_resource type="StandardMaterial3D" id="{rid}"]\n'
            f'albedo_color = {col(r, g, b)}\n'
        )
        return rid

    def material_rgba(self, r: float, g: float, b: float, a: float) -> str:
        """Translucent, unshaded material — used for hazard volumes so the danger
        zone reads as a coloured glow you can see (and walk into) through."""
        rid = self._id("StandardMaterial3D")
        self._sub.append(
            f'[sub_resource type="StandardMaterial3D" id="{rid}"]\n'
            f'transparency = 1\n'
            f'shading_mode = 0\n'
            f'albedo_color = {col(r, g, b, a)}\n'
        )
        return rid

    def box_shape(self, sx: float, sy: float, sz: float) -> str:
        rid = self._id("BoxShape3D")
        self._sub.append(
            f'[sub_resource type="BoxShape3D" id="{rid}"]\n'
            f'size = {v3(sx, sy, sz)}\n'
        )
        return rid

    def sphere_shape(self, radius: float) -> str:
        rid = self._id("SphereShape3D")
        self._sub.append(
            f'[sub_resource type="SphereShape3D" id="{rid}"]\n'
            f'radius = {radius:.4f}\n'
        )
        return rid

    # ── node factories ────────────────────────────────────────────────────────

    def node(
        self,
        name: str,
        ntype: str,
        parent: str | None,
        props: dict[str, str] | None = None,
        groups: list[str] | None = None,
    ) -> None:
        parent_attr = "" if parent is None else f' parent="{parent}"'
        groups_attr = ""
        if groups:
            groups_str = ", ".join(f'"{g}"' for g in groups)
            groups_attr = f' groups=[{groups_str}]'
        lines = [f'[node name="{name}" type="{ntype}"{parent_attr}{groups_attr}]']
        for k, v in (props or {}).items():
            lines.append(f'{k} = {v}')
        lines.append("")
        self._nodes.append("\n".join(lines))

    # ── output ────────────────────────────────────────────────────────────────

    def build(self) -> str:
        header = "[gd_scene format=3]\n\n"
        ext_part = "\n".join(self._ext) + "\n" if self._ext else ""
        return header + ext_part + "\n".join(self._sub) + "\n" + "\n".join(self._nodes)


# ── Zone adjacency / doorways ───────────────────────────────────────────────────

def _zone_aabb(zone: dict) -> dict:
    """Godot-space axis-aligned bounding box for a zone: centre + full size + min/max."""
    cx, cy, cz = ue_pos(
        zone["bounds"]["center"]["x"],
        zone["bounds"]["center"]["y"],
        zone["bounds"]["center"]["z"],
    )
    sx, sy, sz = ue_ext(
        zone["bounds"]["extents"]["x"],
        zone["bounds"]["extents"]["y"],
        zone["bounds"]["extents"]["z"],
    )
    c = (cx, cy, cz)
    s = (sx, sy, sz)
    mn = (cx - sx / 2, cy - sy / 2, cz - sz / 2)
    mx = (cx + sx / 2, cy + sy / 2, cz + sz / 2)
    return {"id": zone["id"], "c": c, "s": s, "min": mn, "max": mx}


def _overlap(a: dict, b: dict, axis: int) -> tuple[float, float] | None:
    """1-D overlap interval of two AABBs along an axis (0=X,1=Y,2=Z), or None."""
    lo = max(a["min"][axis], b["min"][axis])
    hi = min(a["max"][axis], b["max"][axis])
    return (lo, hi) if hi > lo else None


def _compute_doors(zones: list[dict]) -> dict[str, list[tuple[str, float]]]:
    """Find adjacent zone pairs and return per-zone doorways.

    A doorway is cut where two zones touch on a horizontal axis (X or Z) and
    overlap enough on the other horizontal axis and on Y to fit a door. Result
    maps zone id -> list of (wall_side, offset_along_wall) where wall_side is
    one of N/S/E/W and the offset is along that wall's span axis from the zone
    centre.
    """
    boxes = [_zone_aabb(z) for z in zones]
    doors: dict[str, list[tuple[str, float]]] = {z["id"]: [] for z in zones}

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            for axis in (0, 2):              # X -> E/W walls, Z -> N/S walls
                _try_doorway(boxes[i], boxes[j], axis, doors)

    # Exterior doorways: an opening in a wall that leads outside (no adjacent zone).
    # ScenePlan zone may set "exterior_door": "N"  (or a list) using Godot wall sides
    # N=-Z, S=+Z, E=+X, W=-X. Centred on the wall.
    for z in zones:
        ext = z.get("exterior_door")
        if not ext:
            continue
        sides = [ext] if isinstance(ext, str) else list(ext)
        for side in sides:
            side = str(side).upper()
            if side in ("N", "S", "E", "W"):
                doors[z["id"]].append((side, 0.0))
    return doors


def _try_doorway(a: dict, b: dict, axis: int, doors: dict) -> None:
    perp = 2 if axis == 0 else 0             # the other horizontal axis

    # Which zone sits on the negative side of `axis`? Faces must nearly touch.
    if abs(a["max"][axis] - b["min"][axis]) <= ADJ_TOL:
        lower, upper = a, b
    elif abs(b["max"][axis] - a["min"][axis]) <= ADJ_TOL:
        lower, upper = b, a
    else:
        return

    ov_perp = _overlap(a, b, perp)
    ov_y    = _overlap(a, b, 1)
    if ov_perp is None or ov_y is None:
        return
    if (ov_perp[1] - ov_perp[0]) < DOOR_W * 0.9 or (ov_y[1] - ov_y[0]) < DOOR_H * 0.9:
        return                               # not enough shared opening to fit a door

    door_world = (ov_perp[0] + ov_perp[1]) / 2.0
    if axis == 0:   # adjacency along X -> doors in the E/W walls, offset along Z
        doors[lower["id"]].append(("E", door_world - lower["c"][perp]))
        doors[upper["id"]].append(("W", door_world - upper["c"][perp]))
    else:           # adjacency along Z -> doors in the N/S walls, offset along X
        doors[lower["id"]].append(("S", door_world - lower["c"][perp]))
        doors[upper["id"]].append(("N", door_world - upper["c"][perp]))


def _doorway_geoms(zones: list[dict]) -> list[dict]:
    """Geometry of every auto-cut doorway, in Godot world coords.

    Each entry: axis (0=X,2=Z adjacency), plane (shared-wall coordinate on that
    axis), perp_c (doorway centre on the perpendicular horizontal axis), floor_top
    (Y of the floor surface), and the two zone ids it joins. Mirrors the adjacency
    test in _try_doorway so a secret-door slab can be placed exactly over an opening.
    """
    boxes = [_zone_aabb(z) for z in zones]
    geoms: list[dict] = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            for axis in (0, 2):
                g = _doorway_geom(boxes[i], boxes[j], axis)
                if g:
                    geoms.append(g)
    return geoms


def _doorway_geom(a: dict, b: dict, axis: int) -> dict | None:
    perp = 2 if axis == 0 else 0
    if abs(a["max"][axis] - b["min"][axis]) <= ADJ_TOL:
        lower, upper = a, b
    elif abs(b["max"][axis] - a["min"][axis]) <= ADJ_TOL:
        lower, upper = b, a
    else:
        return None
    ov_perp = _overlap(a, b, perp)
    ov_y    = _overlap(a, b, 1)
    if ov_perp is None or ov_y is None:
        return None
    if (ov_perp[1] - ov_perp[0]) < DOOR_W * 0.9 or (ov_y[1] - ov_y[0]) < DOOR_H * 0.9:
        return None
    return {
        "a_id":      a["id"],
        "b_id":      b["id"],
        "axis":      axis,
        "perp":      perp,
        "plane":     (lower["max"][axis] + upper["min"][axis]) / 2.0,
        "perp_c":    (ov_perp[0] + ov_perp[1]) / 2.0,
        "floor_top": max(a["min"][1], b["min"][1]) + WALL_DIM,
    }


# ── Room geometry ──────────────────────────────────────────────────────────────

def _static_box(
    b: TscnBuilder,
    name: str,
    parent: str,
    sx: float, sy: float, sz: float,
    lx: float, ly: float, lz: float,
    mat_rid: str,
    layer: int | None = None,
) -> None:
    """StaticBody3D + MeshInstance3D + CollisionShape3D for one wall/floor/ceiling.

    `layer` overrides the StaticBody's collision_layer (used to flag walkable
    surfaces so locomotion's downward floor-probe can find them — see WALKABLE_LAYER).
    """
    mesh_rid  = b.box_mesh(sx, sy, sz)
    shape_rid = b.box_shape(sx, sy, sz)
    body_props: dict[str, str] = {"transform": t3d(lx, ly, lz)}
    if layer is not None:
        body_props["collision_layer"] = str(layer)
    b.node(name, "StaticBody3D", parent, body_props)
    sub = f"{parent}/{name}"
    b.node("Mesh", "MeshInstance3D", sub, {
        "mesh": f'SubResource("{mesh_rid}")',
        "surface_material_override/0": f'SubResource("{mat_rid}")',
    })
    b.node("Collision", "CollisionShape3D", sub, {
        "shape": f'SubResource("{shape_rid}")',
    })


def _build_wall(
    b: TscnBuilder,
    name: str,
    parent: str,
    mat_rid: str,
    *,
    span_axis: str,          # "x" (N/S walls) or "z" (E/W walls)
    span_len: float,         # wall length along its span axis
    height: float,           # wall height (Y)
    thickness: float,        # wall thickness along the perpendicular horizontal axis
    lx: float, ly: float, lz: float,   # wall centre in zone-local coords
    door_offset: float | None,         # door centre along span axis, or None for a solid wall
) -> None:
    """A wall, optionally with a rectangular doorway (two side panels + a lintel)."""

    def emit(suffix: str, seg_len: float, seg_h: float, span_c: float, y_c: float) -> None:
        if seg_len <= 0.01 or seg_h <= 0.01:
            return
        if span_axis == "x":
            _static_box(b, name + suffix, parent, seg_len, seg_h, thickness, lx + span_c, y_c, lz, mat_rid)
        else:
            _static_box(b, name + suffix, parent, thickness, seg_h, seg_len, lx, y_c, lz + span_c, mat_rid)

    if door_offset is None:
        emit("", span_len, height, 0.0, ly)
        return

    half = span_len / 2.0
    dl = max(door_offset - DOOR_W / 2.0, -half)
    dr = min(door_offset + DOOR_W / 2.0,  half)
    emit("_a", dl - (-half), height, (-half + dl) / 2.0, ly)   # panel left of door
    emit("_b", half - dr,    height, (dr + half) / 2.0,  ly)   # panel right of door
    lintel_h = height - DOOR_H
    if lintel_h > 0.01:                                        # lintel above the opening
        emit("_lintel", dr - dl, lintel_h, (dl + dr) / 2.0, (ly - height / 2.0) + DOOR_H + lintel_h / 2.0)


def _build_slab_with_hole(
    b: TscnBuilder,
    name: str,
    parent: str,
    sx: float, sz: float,            # slab footprint (X by Z)
    lx: float, ly: float, lz: float, # slab centre in parent-local coords
    mat_rid: str,
    hole_cx: float, hole_cz: float,  # hole centre, offset from slab centre
    hole_x: float,  hole_z: float,   # hole size (X by Z)
    layer: int | None = None,
) -> None:
    """A horizontal floor/ceiling slab with a rectangular opening, emitted as up to
    four border panels — the horizontal-plane analogue of _build_wall's doorway. Lets
    a staircase emerge through a floor (and pass up through the ceiling below)."""
    t = WALL_DIM
    hx0, hx1 = hole_cx - hole_x / 2.0, hole_cx + hole_x / 2.0
    hz0, hz1 = hole_cz - hole_z / 2.0, hole_cz + hole_z / 2.0

    def panel(suffix: str, px0: float, px1: float, pz0: float, pz1: float) -> None:
        w, d = px1 - px0, pz1 - pz0
        if w <= 0.01 or d <= 0.01:
            return
        _static_box(b, name + suffix, parent, w, t, d,
                    lx + (px0 + px1) / 2.0, ly, lz + (pz0 + pz1) / 2.0, mat_rid, layer)

    panel("_n", -sx / 2.0,  sx / 2.0, -sz / 2.0, hz0)          # full-width strip, -Z side
    panel("_s", -sx / 2.0,  sx / 2.0,  hz1,  sz / 2.0)         # full-width strip, +Z side
    panel("_w", -sx / 2.0,  hx0,       hz0,  hz1)              # filler, -X side of hole
    panel("_e",  hx1,       sx / 2.0,  hz0,  hz1)              # filler, +X side of hole


def _staircase_geoms(zones: list[dict]) -> list[dict]:
    """Resolve each zone's optional "staircase" config into concrete geometry.

    Schema (on the UPPER zone being reached):
      "staircase": { "from_zone": "<lower id>", "base": {"x":..,"y":..},
                     "run_axis": "N|S|E|W", "width": <UE cm, optional> }
    base = UE horizontal position of the stair BOTTOM centre; run_axis = Godot wall
    side it ascends toward (N=-Z, S=+Z, E=+X, W=-X). Heights derive from the two
    zones' floor levels, so no manual Y plumbing.
    """
    by_id = {z["id"]: _zone_aabb(z) for z in zones}
    out: list[dict] = []
    for z in zones:
        sc = z.get("staircase")
        if not sc:
            continue
        upper = _zone_aabb(z)
        lower = by_id.get(sc.get("from_zone"))
        if lower is None:
            continue
        bottom_y = lower["min"][1] + WALL_DIM
        top_y    = upper["min"][1] + WALL_DIM
        rise = top_y - bottom_y
        if rise <= 0.01:
            continue
        base = sc.get("base", {"x": 0, "y": 0})
        bx, _by, bz = ue_pos(base.get("x", 0), base.get("y", 0), 0)
        run = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}.get(
            str(sc.get("run_axis", "N")).upper(), (0, -1))
        width = sc.get("width")
        width = (width / 100.0) if width else 1.40

        n = max(1, round(rise / STEP_RISE))
        step_rise = rise / n
        going_total = n * STEP_GOING
        top_x = bx + run[0] * going_total
        top_z = bz + run[1] * going_total

        # Stairwell opening. It must span every run-position where the ramp passes
        # UNDER the upper floor / lower ceiling while the player's head is at or above
        # those slabs — otherwise the head-height body snags on the slab underside and
        # the downward floor-probe snaps to the slab instead of the ramp. Low end: where
        # the head (feet + HEAD_CLEAR) first reaches the lowest slab (the lower ceiling's
        # underside). High end: just past the top landing. (HEAD_CLEAR must exceed a tall
        # player's eye height; it pairs with HEAD_DROP/probe in locomotion.gd.)
        HEAD_CLEAR = 1.70
        slab_lo = lower["max"][1] - WALL_DIM
        frac_lo = max(0.0, min(1.0, ((slab_lo - HEAD_CLEAR) - bottom_y) / rise))
        p_lo = frac_lo * going_total - 0.30      # start a touch earlier (body radius margin)
        # End the hole exactly at the ramp top so the solid upper floor abuts the ramp
        # there (both at top_y). Extending past it would leave a walkable gap where the
        # probe sees through to the floor far below and drops the player.
        p_hi = going_total
        lo_x, lo_z = bx + run[0] * p_lo, bz + run[1] * p_lo
        hi_x, hi_z = bx + run[0] * p_hi, bz + run[1] * p_hi
        hcx, hcz = (lo_x + hi_x) / 2.0, (lo_z + hi_z) / 2.0
        along = abs(p_hi - p_lo)
        perp  = width + 0.6
        if run[1] == 0:        # ascends along X -> long axis of the hole is X
            hole_x, hole_z = along, perp
        else:                  # ascends along Z
            hole_x, hole_z = perp, along

        out.append({
            "lower_id": lower["id"], "upper_id": upper["id"],
            "bx": bx, "bz": bz, "bottom_y": bottom_y,
            "top_x": top_x, "top_z": top_z, "top_y": top_y,
            "run": run, "width": width, "n": n,
            "step_rise": step_rise, "step_going": STEP_GOING, "going_total": going_total,
            "lower_c": lower["c"], "upper_c": upper["c"],
            "hcx": hcx, "hcz": hcz, "hole_x": hole_x, "hole_z": hole_z,
        })
    return out


def _stair_holes(geoms: list[dict]) -> dict[str, dict]:
    """Map zone id -> hole spec (in that zone's local coords) for floors/ceilings the
    staircases must pierce: the upper zone's floor and the lower zone's ceiling."""
    holes: dict[str, dict] = {}
    for g in geoms:
        holes[g["upper_id"]] = {  # cut the upper zone's FLOOR
            "where": "floor",
            "cx": g["hcx"] - g["upper_c"][0], "cz": g["hcz"] - g["upper_c"][2],
            "hx": g["hole_x"], "hz": g["hole_z"],
        }
        holes[g["lower_id"]] = {  # cut the lower zone's CEILING
            "where": "ceiling",
            "cx": g["hcx"] - g["lower_c"][0], "cz": g["hcz"] - g["lower_c"][2],
            "hx": g["hole_x"], "hz": g["hole_z"],
        }
    return holes


def _add_staircase(b: TscnBuilder, g: dict) -> None:
    """Emit a staircase in Godot world coords (parented to the scene root): SOLID step
    boxes (collision on the default layer so the body + thrown objects are blocked and
    can't pass through the stairs) plus one tilted ramp collider on the WALKABLE layer
    so the floor-probe rides a smooth slope (the steps are off the walkable layer so they
    don't make the probe steppy)."""
    run = g["run"]
    bx, bz, bottom_y = g["bx"], g["bz"], g["bottom_y"]
    w = g["width"]
    parent = f"Staircase_{g['lower_id']}_{g['upper_id']}".replace("-", "_")
    b.node(parent, "Node3D", ".", {"transform": t3d(0, 0, 0)})
    mat = b.material(0.55, 0.55, 0.60)

    # Solid steps: each runs from below the floor up to its tread top (which sits on the
    # ramp/walking surface). Stacked side-by-side along the run they form a solid mass
    # whose tall upper steps block the chest-height body from walking through the stairs.
    base = bottom_y - WALL_DIM
    for i in range(g["n"]):
        cx = bx + run[0] * g["step_going"] * (i + 0.5)
        cz = bz + run[1] * g["step_going"] * (i + 0.5)
        top_i = bottom_y + g["step_rise"] * (i + 0.5)   # tread top on the slope line
        h = top_i - base
        cy = (base + top_i) / 2.0
        if run[1] == 0:
            sx, sz = g["step_going"], w
        else:
            sx, sz = w, g["step_going"]
        _static_box(b, f"Step_{i}", parent, sx, h, sz, cx, cy, cz, mat)  # default layer 1

    # Smooth ramp collider (walkable layer) under the treads.
    going_total, rise = g["going_total"], g["top_y"] - bottom_y
    length = math.sqrt(going_total * going_total + rise * rise)
    xa = (run[0] * going_total / length, rise / length, run[1] * going_total / length)
    za = (0.0, 0.0, 1.0) if run[1] == 0 else (1.0, 0.0, 0.0)
    # ya = za x xa  (thin axis of the slab; here it points DOWN-slope, so physical
    # "up" out of the ramp is -ya). Offset the centre by +ya*thick/2 so the TOP face
    # lands exactly on the slope line joining the two floor tops -> flush, no lurch
    # stepping on/off the ramp.
    ya = (
        za[1] * xa[2] - za[2] * xa[1],
        za[2] * xa[0] - za[0] * xa[2],
        za[0] * xa[1] - za[1] * xa[0],
    )
    thick = 0.20
    mid = ((bx + g["top_x"]) / 2.0, (bottom_y + g["top_y"]) / 2.0, (bz + g["top_z"]) / 2.0)
    origin = (mid[0] + ya[0] * thick / 2.0,
              mid[1] + ya[1] * thick / 2.0,
              mid[2] + ya[2] * thick / 2.0)
    shape = b.box_shape(length, thick, w)
    b.node("Ramp", "StaticBody3D", parent, {
        "transform": t3d_axes(xa, ya, za, origin),
        "collision_layer": str(WALKABLE_LAYER),
    })
    b.node("Collision", "CollisionShape3D", f"{parent}/Ramp", {
        "shape": f'SubResource("{shape}")',
    })


def add_zone(b: TscnBuilder, zone: dict, doors: list[tuple[str, float]] | None = None,
             hole: dict | None = None) -> None:
    zid    = zone["id"].replace("-", "_")
    ztype  = zone.get("type", "exploration")
    bounds = zone["bounds"]

    cx, cy, cz = ue_pos(
        bounds["center"]["x"],
        bounds["center"]["y"],
        bounds["center"]["z"],
    )
    sx, sy, sz = ue_ext(
        bounds["extents"]["x"],
        bounds["extents"]["y"],
        bounds["extents"]["z"],
    )

    base_r, base_g, base_b = _ZONE_RGB.get(ztype, (0.5, 0.5, 0.5))
    floor_mat = b.material(base_r,                  base_g,                  base_b)
    wall_mat  = b.material(base_r * 0.85,           base_g * 0.85,           base_b * 0.85)
    ceil_mat  = b.material(base_r * 0.70,           base_g * 0.70,           base_b * 0.70)

    t = WALL_DIM
    zone_node = f"Zone_{zid}"
    b.node(zone_node, "Node3D", ".", {"transform": t3d(cx, cy, cz)})

    # doorway offsets per wall side (None = solid wall)
    door = {side: off for side, off in (doors or [])}

    # floor / ceiling — floors are flagged walkable so locomotion's floor-probe finds
    # them; a staircase that pierces this zone cuts a hole in the floor (or ceiling).
    floor_ly = -sy/2 + t/2
    ceil_ly  =  sy/2 - t/2
    if hole and hole["where"] == "floor":
        _build_slab_with_hole(b, f"Floor_{zid}", zone_node, sx, sz, 0, floor_ly, 0,
                              floor_mat, hole["cx"], hole["cz"], hole["hx"], hole["hz"],
                              WALKABLE_LAYER)
    else:
        _static_box(b, f"Floor_{zid}", zone_node, sx, t, sz, 0, floor_ly, 0, floor_mat,
                    WALKABLE_LAYER)
    if hole and hole["where"] == "ceiling":
        _build_slab_with_hole(b, f"Ceiling_{zid}", zone_node, sx, sz, 0, ceil_ly, 0,
                              ceil_mat, hole["cx"], hole["cz"], hole["hx"], hole["hz"])
    else:
        _static_box(b, f"Ceiling_{zid}", zone_node, sx, t, sz, 0, ceil_ly, 0, ceil_mat)
    # north / south walls  (Z faces in Godot) — span along X
    _build_wall(b, f"WallN_{zid}", zone_node, wall_mat, span_axis="x", span_len=sx, height=sy, thickness=t, lx=0, ly=0, lz=-sz/2 + t/2, door_offset=door.get("N"))
    _build_wall(b, f"WallS_{zid}", zone_node, wall_mat, span_axis="x", span_len=sx, height=sy, thickness=t, lx=0, ly=0, lz= sz/2 - t/2, door_offset=door.get("S"))
    # east / west walls  (X faces in Godot) — span along Z
    _build_wall(b, f"WallE_{zid}", zone_node, wall_mat, span_axis="z", span_len=sz, height=sy, thickness=t, lx= sx/2 - t/2, ly=0, lz=0, door_offset=door.get("E"))
    _build_wall(b, f"WallW_{zid}", zone_node, wall_mat, span_axis="z", span_len=sz, height=sy, thickness=t, lx=-sx/2 + t/2, ly=0, lz=0, door_offset=door.get("W"))

    # zone fill-light
    light_range = max(sx, sz) * 0.9
    b.node(f"Light_{zid}", "OmniLight3D", zone_node, {
        "transform": t3d(0, sy * 0.35, 0),
        "omni_range": f"{light_range:.3f}",
        "light_energy": "1.2",
    })

    # interactables
    for obj in zone.get("interactables", []):
        _add_interactable(b, obj, zone_node, bounds)


def _add_interactable(b: TscnBuilder, obj: dict, zone_node: str, bounds: dict) -> None:
    oid   = obj["id"].replace("-", "_")
    otype = obj.get("type", "artefact")

    # zone centre in Godot coords — so we can express position relative to zone node
    zx, zy, zz = ue_pos(
        bounds["center"]["x"],
        bounds["center"]["y"],
        bounds["center"]["z"],
    )
    pos = obj.get("position", {"x": 0, "y": 0, "z": 0})
    gx, gy, gz = ue_pos(pos["x"], pos["y"], pos["z"])
    lx, ly, lz = gx - zx, gy - zy, gz - zz

    if otype in ("lever", "wheel"):
        _add_mechanism(b, oid, otype, zone_node, lx, ly, lz)
        return

    if otype == "button":
        _add_button(b, oid, zone_node, lx, ly, lz)
        return
    if otype == "switch":
        _add_switch(b, oid, zone_node, lx, ly, lz)
        return
    if otype == "pressure_plate":
        _add_pressure_plate(b, obj, oid, zone_node, lx, ly, lz)
        return
    if otype == "proximity":
        _add_proximity(b, obj, oid, zone_node, lx, ly, lz)
        return
    if otype == "lamp":
        _add_lamp(b, obj, oid, zone_node, lx, ly, lz)
        return
    if otype == "platform":
        _add_platform(b, obj, oid, zone_node, lx, ly, lz)
        return
    if otype == "sequence":
        _add_sequence(b, obj, oid, zone_node, lx, ly, lz)
        return
    if otype == "hazard":
        _add_hazard(b, obj, oid, zone_node, lx, ly, lz)
        return
    if otype == "objective":
        _add_objective(b, obj, oid, zone_node, lx, ly, lz)
        return
    if otype == "scoreboard":
        _add_scoreboard(b, obj, oid, zone_node, lx, ly, lz)
        return
    if otype == "gun":
        _add_gun(b, obj, oid, zone_node, lx, ly, lz)
        return
    if otype == "target":
        _add_target(b, obj, oid, zone_node, lx, ly, lz)
        return
    if otype == "ammo":
        _add_ammo(b, obj, oid, zone_node, lx, ly, lz)
        return

    r, g, b_c = _INTERACTABLE_RGB.get(otype, (0.5, 0.5, 0.5))
    mat = b.material(r, g, b_c)

    if otype == "artefact":
        mesh  = b.sphere_mesh(0.15)
        shape = b.sphere_shape(0.15)
        node_name = f"Artefact_{oid}"
        b.node(node_name, "RigidBody3D", zone_node, {
            "transform": t3d(lx, ly + 0.15, lz),
            "mass": "1.0",
            # Continuous collision detection so a hard bat/throw can't tunnel the
            # orb through the thin (0.3 m) walls and out of the level.
            "continuous_cd": "true",
        }, groups=["grabbable"])
        sub = f"{zone_node}/{node_name}"
        b.node("Mesh",      "MeshInstance3D",   sub, {"mesh": f'SubResource("{mesh}")', "surface_material_override/0": f'SubResource("{mat}")'})
        b.node("Collision", "CollisionShape3D", sub, {"shape": f'SubResource("{shape}")'})

    elif otype == "machinery":
        mesh  = b.cylinder_mesh(0.30, 1.80)
        shape = b.box_shape(0.60, 1.80, 0.60)
        node_name = f"Machine_{oid}"
        b.node(node_name, "StaticBody3D", zone_node, {"transform": t3d(lx, ly + 0.90, lz)})
        sub = f"{zone_node}/{node_name}"
        b.node("Mesh",      "MeshInstance3D",   sub, {"mesh": f'SubResource("{mesh}")', "surface_material_override/0": f'SubResource("{mat}")'})
        b.node("Collision", "CollisionShape3D", sub, {"shape": f'SubResource("{shape}")'})

    elif otype == "creature":
        mesh  = b.box_mesh(0.80, 1.80, 0.50)
        shape = b.box_shape(0.80, 1.80, 0.50)
        node_name = f"Creature_{oid}"
        b.node(node_name, "CharacterBody3D", zone_node, {"transform": t3d(lx, ly + 0.90, lz)})
        sub = f"{zone_node}/{node_name}"
        b.node("Mesh",      "MeshInstance3D",   sub, {"mesh": f'SubResource("{mesh}")', "surface_material_override/0": f'SubResource("{mat}")'})
        b.node("Collision", "CollisionShape3D", sub, {"shape": f'SubResource("{shape}")'})

    else:  # environmental
        mesh  = b.box_mesh(1.00, 1.00, 1.00)
        shape = b.box_shape(1.00, 1.00, 1.00)
        node_name = f"Env_{oid}"
        b.node(node_name, "StaticBody3D", zone_node, {"transform": t3d(lx, ly + 0.50, lz)})
        sub = f"{zone_node}/{node_name}"
        b.node("Mesh",      "MeshInstance3D",   sub, {"mesh": f'SubResource("{mesh}")', "surface_material_override/0": f'SubResource("{mat}")'})
        b.node("Collision", "CollisionShape3D", sub, {"shape": f'SubResource("{shape}")'})


def _add_mechanism(
    b: TscnBuilder,
    oid: str,
    kind: str,
    zone_node: str,
    lx: float, ly: float, lz: float,
) -> None:
    """Emit a lever or wheel: a fixed Base post + a rotating Pivot carrying a steel
    arm/disc and a bright recolouring Indicator (the grab handle). Driven at runtime
    by mechanism.gd / MechanismManager. lx/ly/lz = floor position in zone-local space.
    """
    script_rid = b.script_resource("res://scripts/mechanism.gd")

    if kind == "lever":
        ph        = 1.00            # pivot height above floor (m)
        arm_len   = 0.50
        handle    = arm_len
        knob_r    = 0.09
        axis_str  = v3(1, 0, 0)     # swings fore/aft about local X
        min_a, max_a = -0.785, 0.785
    else:  # wheel
        ph        = 1.20
        rim_r     = 0.32
        handle    = rim_r
        knob_r    = 0.08
        axis_str  = v3(0, 0, 1)     # turns about its facing axis (local Z)
        min_a, max_a = -3.1416, 3.1416

    mech = f"Mechanism_{oid}"
    mech_path = f"{zone_node}/{mech}"   # full path from scene root for child nodes
    b.node(mech, "Node3D", zone_node, {
        "transform":    t3d(lx, ly + ph, lz),
        "script":       f'ExtResource("{script_rid}")',
        "kind":         f'"{kind}"',
        "axis":         axis_str,
        "min_angle":    f"{min_a:.4f}",
        "max_angle":    f"{max_a:.4f}",
        "handle_local": v3(0, handle, 0),
    }, groups=["mechanism"])

    # Fixed mounting post from floor up to the pivot.
    base_mat   = b.material(0.25, 0.25, 0.28)
    base_mesh  = b.box_mesh(0.12, ph, 0.12)
    base_shape = b.box_shape(0.12, ph, 0.12)
    b.node("Base", "StaticBody3D", mech_path, {"transform": t3d(0, -ph / 2, 0)})
    b.node("Mesh", "MeshInstance3D", f"{mech_path}/Base", {
        "mesh": f'SubResource("{base_mesh}")',
        "surface_material_override/0": f'SubResource("{base_mat}")',
    })
    b.node("Collision", "CollisionShape3D", f"{mech_path}/Base", {
        "shape": f'SubResource("{base_shape}")',
    })

    # Rotating part.
    b.node("Pivot", "Node3D", mech_path)
    pivot = f"{mech_path}/Pivot"
    arm_mat = b.material(0.45, 0.48, 0.55)   # steel
    if kind == "lever":
        arm_mesh = b.box_mesh(0.05, arm_len, 0.05)
        b.node("Arm", "MeshInstance3D", pivot, {
            "transform": t3d(0, arm_len / 2, 0),
            "mesh": f'SubResource("{arm_mesh}")',
            "surface_material_override/0": f'SubResource("{arm_mat}")',
        })
    else:
        disc_mesh = b.cylinder_mesh(rim_r, 0.07)
        # Lay the disc into the X/Y plane (cylinder axis Y -> Z) so it spins like a valve.
        b.node("Arm", "MeshInstance3D", pivot, {
            "transform": "Transform3D(1, 0, 0, 0, 0, -1, 0, 1, 0, 0, 0, 0)",
            "mesh": f'SubResource("{disc_mesh}")',
            "surface_material_override/0": f'SubResource("{arm_mat}")',
        })

    # Bright recolouring grab handle (red->green across travel) at the grip point.
    knob_mat  = b.material(1.0, 0.0, 0.0)
    knob_mesh = b.sphere_mesh(knob_r)
    b.node("Indicator", "MeshInstance3D", pivot, {
        "transform": t3d(0, handle, 0),
        "mesh": f'SubResource("{knob_mesh}")',
        "surface_material_override/0": f'SubResource("{knob_mat}")',
    })

    # Live value readout, billboarded so it always faces the player.
    b.node("ValueLabel", "Label3D", mech_path, {
        "transform": t3d(0, handle + 0.35, 0),
        "text": f'"{kind} 0.50"',
        "billboard": "1",
        "font_size": "48",
        "pixel_size": "0.0015",
        "modulate": col(1, 1, 1),
        "outline_size": "4",
    })


# ── F2 simple interactables (buttons / switches / plates / proximity) ───────────
# Each emits a node tree whose script (extending interactable.gd) fires a discrete
# "interact:<verb>" event on the GameEvents bus. lx/ly/lz = zone-local position; the
# author places them at the intended height (no implicit offset).

def _add_button(b: TscnBuilder, oid: str, zone_node: str,
                lx: float, ly: float, lz: float) -> None:
    script = b.script_resource("res://scripts/interactables/push_button.gd")
    name = f"Button_{oid}"
    path = f"{zone_node}/{name}"
    b.node(name, "Node3D", zone_node, {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "interactable_id": f'"{oid}"',
    }, groups=["interactable", "hand_touch"])
    base_mat = b.material(0.18, 0.18, 0.20)
    base_mesh = b.cylinder_mesh(0.08, 0.04)
    b.node("Base", "MeshInstance3D", path, {
        "transform": t3d(0, 0.02, 0),
        "mesh": f'SubResource("{base_mesh}")',
        "surface_material_override/0": f'SubResource("{base_mat}")',
    })
    cap_mat = b.material(0.85, 0.16, 0.12)
    cap_mesh = b.cylinder_mesh(0.06, 0.03)
    b.node("Cap", "MeshInstance3D", path, {
        "transform": t3d(0, 0.055, 0),
        "mesh": f'SubResource("{cap_mesh}")',
        "surface_material_override/0": f'SubResource("{cap_mat}")',
    })


def _add_switch(b: TscnBuilder, oid: str, zone_node: str,
                lx: float, ly: float, lz: float) -> None:
    script = b.script_resource("res://scripts/interactables/toggle_switch.gd")
    name = f"Switch_{oid}"
    path = f"{zone_node}/{name}"
    b.node(name, "Node3D", zone_node, {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "interactable_id": f'"{oid}"',
    }, groups=["interactable", "hand_touch"])
    base_mat = b.material(0.18, 0.18, 0.20)
    base_mesh = b.box_mesh(0.12, 0.18, 0.05)
    b.node("Base", "MeshInstance3D", path, {
        "mesh": f'SubResource("{base_mesh}")',
        "surface_material_override/0": f'SubResource("{base_mat}")',
    })
    # Lever node pivots about local X; the bar is offset up so the tilt reads clearly.
    b.node("Lever", "Node3D", path, {"transform": t3d(0, 0, 0.035)})
    bar_mat = b.material(0.85, 0.80, 0.20)
    bar_mesh = b.box_mesh(0.04, 0.12, 0.04)
    b.node("Bar", "MeshInstance3D", f"{path}/Lever", {
        "transform": t3d(0, 0.05, 0),
        "mesh": f'SubResource("{bar_mesh}")',
        "surface_material_override/0": f'SubResource("{bar_mat}")',
    })


def _add_pressure_plate(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
                        lx: float, ly: float, lz: float) -> None:
    script = b.script_resource("res://scripts/interactables/pressure_plate.gd")
    name = f"Plate_{oid}"
    path = f"{zone_node}/{name}"
    size = float(obj.get("size", 0.8))          # square plate side (m)
    b.node(name, "Node3D", zone_node, {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "interactable_id": f'"{oid}"',
    }, groups=["interactable"])
    plate_mat = b.material(0.35, 0.30, 0.15)
    plate_mesh = b.box_mesh(size, 0.06, size)
    b.node("Plate", "MeshInstance3D", path, {
        "transform": t3d(0, 0.03, 0),
        "mesh": f'SubResource("{plate_mesh}")',
        "surface_material_override/0": f'SubResource("{plate_mat}")',
    })
    # Detection box just above the plate (default Area3D mask = layer 1 -> player body
    # + grabbables). Sized a touch inside the plate footprint.
    shape = b.box_shape(size * 0.9, 0.30, size * 0.9)
    b.node("Area", "Area3D", path, {"transform": t3d(0, 0.20, 0)})
    b.node("Shape", "CollisionShape3D", f"{path}/Area", {
        "shape": f'SubResource("{shape}")',
    })


def _add_proximity(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
                   lx: float, ly: float, lz: float) -> None:
    script = b.script_resource("res://scripts/interactables/proximity_volume.gd")
    name = f"Proximity_{oid}"
    path = f"{zone_node}/{name}"
    size = float(obj.get("size", 2.0))          # cube side (m), sitting on the floor
    b.node(name, "Node3D", zone_node, {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "interactable_id": f'"{oid}"',
    }, groups=["interactable"])
    shape = b.box_shape(size, size, size)
    b.node("Area", "Area3D", path, {"transform": t3d(0, size / 2.0, 0)})
    b.node("Shape", "CollisionShape3D", f"{path}/Area", {
        "shape": f'SubResource("{shape}")',
    })


def _add_sequence(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
                  lx: float, ly: float, lz: float) -> None:
    """An invisible ordered-interaction puzzle. ScenePlan fields: order (list of
    interactable ids), watch_event (default interact:button), solved_event (default
    sequence:solved), reset_on_wrong (default true). Wire a reactor (lamp/platform/
    door) to solved_event with source_id == this puzzle's id."""
    script = b.script_resource("res://scripts/sequence_puzzle.gd")
    name = f"Sequence_{oid}"
    order = obj.get("order", [])
    order_str = "[" + ", ".join(f'"{str(x)}"' for x in order) + "]"
    props: dict[str, str] = {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "puzzle_id": f'"{oid}"',
        "order": order_str,
    }
    if "watch_event" in obj:
        props["watch_event"] = f'"{obj["watch_event"]}"'
    if "solved_event" in obj:
        props["solved_event"] = f'"{obj["solved_event"]}"'
    if "reset_on_wrong" in obj:
        props["reset_on_wrong"] = "true" if obj["reset_on_wrong"] else "false"
    b.node(name, "Node3D", zone_node, props, groups=["sequence_puzzle"])


def _add_gun(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
             lx: float, ly: float, lz: float) -> None:
    """An equippable hitscan weapon (F7). Group "weapon"; grip-to-equip, trigger-to-fire
    via weapon_manager. Barrel points along -Z (controller forward). ScenePlan fields:
    max_ammo, damage, fire_range, fire_cooldown."""
    script = b.script_resource("res://scripts/weapon.gd")
    name = f"Gun_{oid}"
    path = f"{zone_node}/{name}"
    props: dict[str, str] = {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "weapon_id": f'"{oid}"',
        "max_ammo": str(int(obj.get("max_ammo", 12))),
        "damage": str(int(obj.get("damage", 25))),
        "fire_range": f'{float(obj.get("fire_range", 50.0)):.4f}',
        "fire_cooldown": f'{float(obj.get("fire_cooldown", 0.25)):.4f}',
    }
    b.node(name, "Node3D", zone_node, props, groups=["weapon"])
    body_mat = b.material(0.14, 0.14, 0.17)
    body_mesh = b.box_mesh(0.05, 0.12, 0.20)
    b.node("Body", "MeshInstance3D", path, {
        "mesh": f'SubResource("{body_mesh}")',
        "surface_material_override/0": f'SubResource("{body_mat}")',
    })
    barrel_mesh = b.box_mesh(0.035, 0.035, 0.24)
    b.node("Barrel", "MeshInstance3D", path, {
        "transform": t3d(0, 0.045, -0.16),
        "mesh": f'SubResource("{barrel_mesh}")',
        "surface_material_override/0": f'SubResource("{body_mat}")',
    })
    b.node("Muzzle", "Node3D", path, {"transform": t3d(0, 0.045, -0.30)})
    b.node("AmmoLabel", "Label3D", path, {
        "transform": t3d(0, 0.13, 0),
        "text": '"12/12"',
        "billboard": "1",
        "font_size": "30",
        "pixel_size": "0.0015",
        "modulate": col(0.8, 1.0, 0.8),
        "outline_size": "4",
    })


def _add_target(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
                lx: float, ly: float, lz: float) -> None:
    """A destructible target (F7). StaticBody3D (so the combat raycast hits it directly),
    group "target". ScenePlan fields: size (m, default 0.5), max_hp (default 50)."""
    script = b.script_resource("res://scripts/target.gd")
    name = f"Target_{oid}"
    path = f"{zone_node}/{name}"
    size = float(obj.get("size", 0.5))
    b.node(name, "StaticBody3D", zone_node, {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "target_id": f'"{oid}"',
        "max_hp": str(int(obj.get("max_hp", 50))),
    }, groups=["target"])
    mat = b.material(0.80, 0.30, 0.20)
    mesh = b.box_mesh(size, size, size)
    shape = b.box_shape(size, size, size)
    b.node("Mesh", "MeshInstance3D", path, {
        "mesh": f'SubResource("{mesh}")',
        "surface_material_override/0": f'SubResource("{mat}")',
    })
    b.node("Collision", "CollisionShape3D", path, {"shape": f'SubResource("{shape}")'})


def _add_ammo(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
              lx: float, ly: float, lz: float) -> None:
    """An ammo pickup (F7). Walk into it to reload the equipped weapon; consumes itself.
    ScenePlan fields: size (detection cube side, m, default 0.8)."""
    script = b.script_resource("res://scripts/ammo_pickup.gd")
    name = f"Ammo_{oid}"
    path = f"{zone_node}/{name}"
    size = float(obj.get("size", 0.8))
    b.node(name, "Node3D", zone_node, {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "pickup_id": f'"{oid}"',
    }, groups=["ammo_pickup"])
    mat = b.material(0.20, 0.80, 0.35)
    mesh = b.box_mesh(0.22, 0.22, 0.22)
    b.node("Icon", "MeshInstance3D", path, {
        "transform": t3d(0, 0.20, 0),
        "mesh": f'SubResource("{mesh}")',
        "surface_material_override/0": f'SubResource("{mat}")',
    })
    shape = b.box_shape(size, size, size)
    b.node("Area", "Area3D", path, {"transform": t3d(0, size / 2.0, 0)})
    b.node("Shape", "CollisionShape3D", f"{path}/Area", {"shape": f'SubResource("{shape}")'})


def _add_hazard(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
                lx: float, ly: float, lz: float) -> None:
    """A damaging volume (F5). An Area3D that hurts the local player while they stand
    in it; damage is decided by the server (health_manager.gd). ScenePlan fields:
      size / size_x / size_y / size_z: box extents (m, default 2m cube on the floor);
      damage_per_second (default 20); interval (DoT cadence s, default 0.5);
      instant (bool — one bite on entry instead of damage-over-time)."""
    script = b.script_resource("res://scripts/interactables/hazard_volume.gd")
    name = f"Hazard_{oid}"
    path = f"{zone_node}/{name}"
    sx = float(obj.get("size_x", obj.get("size", 2.0)))
    sy = float(obj.get("size_y", obj.get("size", 2.0)))
    sz = float(obj.get("size_z", obj.get("size", 2.0)))
    props: dict[str, str] = {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "interactable_id": f'"{oid}"',
        "damage_per_second": f'{float(obj.get("damage_per_second", 20.0)):.4f}',
        "interval": f'{float(obj.get("interval", 0.5)):.4f}',
        "instant": "true" if obj.get("instant") else "false",
    }
    b.node(name, "Node3D", zone_node, props, groups=["interactable", "hazard"])
    # Translucent red glow so the danger reads visually (placeholder art).
    glow_mat = b.material_rgba(0.90, 0.12, 0.10, 0.30)
    glow_mesh = b.box_mesh(sx, sy, sz)
    b.node("Glow", "MeshInstance3D", path, {
        "transform": t3d(0, sy / 2.0, 0),
        "mesh": f'SubResource("{glow_mesh}")',
        "surface_material_override/0": f'SubResource("{glow_mat}")',
    })
    # Detection box (default Area3D mask = layer 1 -> player CharacterBody). The script
    # filters to group "player", so grabbables/avatars resting in it don't trigger it.
    shape = b.box_shape(sx, sy, sz)
    b.node("Area", "Area3D", path, {"transform": t3d(0, sy / 2.0, 0)})
    b.node("Shape", "CollisionShape3D", f"{path}/Area", {
        "shape": f'SubResource("{shape}")',
    })


def _add_objective(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
                   lx: float, ly: float, lz: float) -> None:
    """An invisible objective marker (F6). GameState scans the "objective" group and
    credits it when `trigger_event` fires (payload.id == match_id, if set). ScenePlan
    fields: trigger_event (default interact:button), match_id, points (default 100),
    optional (bool)."""
    script = b.script_resource("res://scripts/objective.gd")
    name = f"Objective_{oid}"
    props: dict[str, str] = {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "objective_id": f'"{oid}"',
        "trigger_event": f'"{obj.get("trigger_event", "interact:button")}"',
        "match_id": f'"{obj.get("match_id", "")}"',
        "points": str(int(obj.get("points", 100))),
        "optional": "true" if obj.get("optional") else "false",
    }
    b.node(name, "Node3D", zone_node, props, groups=["objective"])


def _add_scoreboard(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
                    lx: float, ly: float, lz: float) -> None:
    """A wall-mounted scoreboard panel (F6) that displays score / objective progress /
    countdown / win-lose, all derived from the GameState bus events. ScenePlan fields:
    title; yaw (degrees, to face the panel into the room)."""
    script = b.script_resource("res://scripts/scoreboard.gd")
    name = f"Scoreboard_{oid}"
    yaw = math.radians(float(obj.get("yaw", 0.0)))
    cy, sy = math.cos(yaw), math.sin(yaw)
    # Rotation about Y by yaw, with translation (lx,ly,lz).
    rot = (
        f"Transform3D({cy:.5f}, 0, {sy:.5f}, 0, 1, 0, {-sy:.5f}, 0, {cy:.5f}, "
        f"{lx:.4f}, {ly:.4f}, {lz:.4f})"
    )
    props: dict[str, str] = {
        "transform": rot,
        "script": f'ExtResource("{script}")',
    }
    if "title" in obj:
        props["board_title"] = f'"{obj["title"]}"'
    b.node(name, "Node3D", zone_node, props)


def _add_platform(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
                  lx: float, ly: float, lz: float) -> None:
    """A rideable rising/lowering platform (AnimatableBody3D on the WALKABLE layer so
    locomotion's floor-probe carries the player). ScenePlan fields:
      mode: "auto"|"toggle"|"mechanism"; height: vertical travel (UE cm, default 250);
      size / size_x / size_z: deck footprint (m); controlled_by: mechanism or button id;
      event: bus event for toggle; speed; auto_period."""
    script = b.script_resource("res://scripts/moving_platform.gd")
    name = f"Platform_{oid}"
    path = f"{zone_node}/{name}"
    sx = float(obj.get("size_x", obj.get("size", 1.6)))
    sz = float(obj.get("size_z", obj.get("size", 1.6)))
    deck = 0.20
    mode = str(obj.get("mode", "auto"))
    height_m = float(obj.get("height", 250)) / 100.0
    props: dict[str, str] = {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "collision_layer": str(WALKABLE_LAYER),
        "mode": f'"{mode}"',
        "travel": v3(0.0, height_m, 0.0),
    }
    if "speed" in obj:
        props["speed"] = f'{float(obj["speed"]):.4f}'
    if "auto_period" in obj:
        props["auto_period"] = f'{float(obj["auto_period"]):.4f}'
    if mode == "mechanism":
        props["mechanism_id"] = f'"{obj.get("controlled_by", "")}"'
    elif mode == "toggle":
        props["source_id"] = f'"{obj.get("controlled_by", "")}"'
        props["trigger_event"] = f'"{obj.get("event", "interact:button")}"'
    b.node(name, "AnimatableBody3D", zone_node, props)
    deck_mat = b.material(0.42, 0.44, 0.52)
    deck_mesh = b.box_mesh(sx, deck, sz)
    deck_shape = b.box_shape(sx, deck, sz)
    b.node("Mesh", "MeshInstance3D", path, {
        "mesh": f'SubResource("{deck_mesh}")',
        "surface_material_override/0": f'SubResource("{deck_mat}")',
    })
    b.node("Collision", "CollisionShape3D", path, {
        "shape": f'SubResource("{deck_shape}")',
    })


def _add_lamp(b: TscnBuilder, obj: dict, oid: str, zone_node: str,
             lx: float, ly: float, lz: float) -> None:
    """An indicator lamp wired to an interactable: toggles its light when the named
    event fires for `controlled_by`. The in-world proof of interactable->bus->reactor."""
    script = b.script_resource("res://scripts/reactors/indicator_lamp.gd")
    name = f"Lamp_{oid}"
    path = f"{zone_node}/{name}"
    src = str(obj.get("controlled_by", ""))
    ev = str(obj.get("event", "interact:button"))
    b.node(name, "Node3D", zone_node, {
        "transform": t3d(lx, ly, lz),
        "script": f'ExtResource("{script}")',
        "trigger_event": f'"{ev}"',
        "source_id": f'"{src}"',
        "light_path": 'NodePath("Lamp")',
    }, groups=["reactor"])
    bulb_mat = b.material(0.90, 0.85, 0.50)
    bulb_mesh = b.sphere_mesh(0.08)
    b.node("Bulb", "MeshInstance3D", path, {
        "mesh": f'SubResource("{bulb_mesh}")',
        "surface_material_override/0": f'SubResource("{bulb_mat}")',
    })
    b.node("Lamp", "OmniLight3D", path, {
        "omni_range": "5.0",
        "light_energy": "4.0",
        "light_color": col(1.0, 0.6, 0.25),
        "visible": "false",
    })


def _add_secret_door(b: TscnBuilder, geom: dict, cfg: dict) -> None:
    """Emit a sliding slab that plugs an auto-cut doorway and looks like wall until a
    mechanism opens it. `cfg` is the zone's "secret_door" object:
      { "controlled_by": "<mechanism id>", "slide_distance": <m, optional> }
    The slab is parented to the scene root and positioned in Godot world coords.
    """
    axis      = geom["axis"]
    plane     = geom["plane"]
    perp_c    = geom["perp_c"]
    floor_top = geom["floor_top"]

    w     = DOOR_W + 0.10            # cover the jambs a touch
    h     = DOOR_H + 0.05
    thick = WALL_DIM * 2 + 0.06      # span both zones' walls at the shared plane
    cy    = floor_top + h / 2.0

    if axis == 0:                    # zones meet along X -> slab thin on X, wide on Z
        sx, sy, sz = thick, h, w
        px, py, pz = plane, cy, perp_c
    else:                            # zones meet along Z -> slab thin on Z, wide on X
        sx, sy, sz = w, h, thick
        px, py, pz = perp_c, cy, plane

    mech_id = str(cfg.get("controlled_by", "")).replace("-", "_")
    slide   = float(cfg.get("slide_distance", h + 0.20))   # default: drop into floor

    script_rid = b.script_resource("res://scripts/secret_door.gd")
    mesh_rid   = b.box_mesh(sx, sy, sz)
    shape_rid  = b.box_shape(sx, sy, sz)
    mat_rid    = b.material(0.34, 0.34, 0.38)              # stone — reads as wall

    name = f"SecretDoor_{mech_id}"
    b.node(name, "AnimatableBody3D", ".", {
        "transform":    t3d(px, py, pz),
        "script":       f'ExtResource("{script_rid}")',
        "mechanism_id": f'"{mech_id}"',
        "open_offset":  v3(0, -slide, 0),
    })
    b.node("Mesh", "MeshInstance3D", name, {
        "mesh": f'SubResource("{mesh_rid}")',
        "surface_material_override/0": f'SubResource("{mat_rid}")',
    })
    b.node("Collision", "CollisionShape3D", name, {
        "shape": f'SubResource("{shape_rid}")',
    })


# ── Main converter ─────────────────────────────────────────────────────────────

def convert(scene_plan: dict, vr: bool = False) -> str:
    b = TscnBuilder()
    name = scene_plan.get("name", "GeneratedScene").replace(" ", "_")

    # VR init script ext_resource
    if vr:
        script_rid = b.ext_resource("Script", "res://scripts/vr_main.gd", "Script_1")

    # Root node (with script attached in VR mode)
    root_props: dict[str, str] = {}
    if vr:
        root_props["script"] = f'ExtResource("{script_rid}")'
    b.node(name, "Node3D", None, root_props or None)

    # Global fill light
    b.node("SunLight", "DirectionalLight3D", ".", {
        "transform": "Transform3D(0.866, -0.5, 0, 0, 0, -1, 0.5, 0.866, 0, 0, 20, 0)",
        "light_energy": "0.5",
        "shadow_enabled": "true",
    })

    # Editor preview camera — skipped in VR mode (XRCamera3D takes its place)
    if not vr:
        b.node("PreviewCamera", "Camera3D", ".", {
            "transform": "Transform3D(1, 0, 0, 0, 0.707, 0.707, 0, -0.707, 0.707, 0, 4, 8)",
            "current": "true",
        })

    # Zones (with doorways cut where zones are adjacent, and stairwell holes cut where
    # a staircase pierces a floor/ceiling)
    zones = scene_plan.get("zones", [])
    doors = _compute_doors(zones)
    stair_geoms = _staircase_geoms(zones)
    holes = _stair_holes(stair_geoms)
    for zone in zones:
        add_zone(b, zone, doors.get(zone["id"]), holes.get(zone["id"]))

    # Staircases connecting stacked zones (cosmetic treads + walkable ramp at root).
    for g in stair_geoms:
        _add_staircase(b, g)

    # Secret doors: a zone may declare {"secret_door": {"controlled_by": "<mech id>"}}.
    # For each auto-cut doorway that touches such a zone, drop in a sliding slab that
    # seals the opening until the linked mechanism is operated.
    secret_by_zone = {z["id"]: z["secret_door"] for z in zones if z.get("secret_door")}
    if secret_by_zone:
        for geom in _doorway_geoms(zones):
            cfg = secret_by_zone.get(geom["a_id"]) or secret_by_zone.get(geom["b_id"])
            if cfg:
                _add_secret_door(b, geom, cfg)

    # Game rules (F6): optional lose conditions for the round. Emitted as an invisible
    # node GameState scans from the "game_rules" group.
    rules = scene_plan.get("game_rules")
    if rules:
        rules_script = b.script_resource("res://scripts/game_rules.gd")
        b.node("GameRules", "Node3D", ".", {
            "script": f'ExtResource("{rules_script}")',
            "time_limit": f'{float(rules.get("time_limit", 0.0)):.4f}',
            "max_team_deaths": str(int(rules.get("max_team_deaths", -1))),
        })

    # Spawns / VR rig
    spawns = scene_plan.get("participant_spawns", [])
    if vr:
        # Position the XR rig at the first player spawn point
        spawn_pos = (0.0, 0.0, 0.0)
        if spawns:
            pos = spawns[0].get("position", {"x": 0, "y": 0, "z": 0})
            spawn_pos = ue_pos(pos["x"], pos["y"], pos["z"])
        sx, sy, sz = spawn_pos
        b.node("XROrigin3D", "XROrigin3D", ".", {"transform": t3d(sx, sy, sz)})
        b.node("XRCamera3D", "XRCamera3D", "XROrigin3D")
        b.node("LeftController",  "XRController3D", "XROrigin3D", {"tracker": '"left_hand"'})
        b.node("RightController", "XRController3D", "XROrigin3D", {"tracker": '"right_hand"'})
    else:
        for i, spawn in enumerate(spawns):
            pos  = spawn.get("position", {"x": 0, "y": 0, "z": 0})
            role = spawn.get("role", "player")
            gx, gy, gz = ue_pos(pos["x"], pos["y"], pos["z"])
            b.node(f"SpawnPoint_{i}_{role}", "Node3D", ".", {"transform": t3d(gx, gy, gz)})

    return b.build()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a HyperMage ScenePlan JSON to a Godot 4 .tscn file."
    )
    parser.add_argument("input", help="Path to ScenePlan JSON, or '-' to read stdin")
    parser.add_argument(
        "-o", "--output",
        help="Output .tscn path  (default: scenes/generated/<scene_id>.tscn)",
    )
    parser.add_argument(
        "--vr", action="store_true",
        help="Include XR rig (XROrigin3D + XRCamera3D) for Quest 3 deployment",
    )
    args = parser.parse_args()

    if args.input == "-":
        scene_plan = json.load(sys.stdin)
    else:
        scene_plan = json.loads(Path(args.input).read_text(encoding="utf-8"))

    tscn = convert(scene_plan, vr=args.vr)

    scene_id  = scene_plan.get("id", str(uuid.uuid4()))
    out_path  = Path(args.output) if args.output else Path("scenes/generated") / f"{scene_id}.tscn"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tscn, encoding="utf-8")

    zone_count  = len(scene_plan.get("zones", []))
    spawn_count = len(scene_plan.get("participant_spawns", []))
    obj_count   = sum(len(z.get("interactables", [])) for z in scene_plan.get("zones", []))
    print(f"Written : {out_path}  {'[VR rig included]' if args.vr else ''}")
    print(f"  zones         : {zone_count}")
    print(f"  spawns        : {spawn_count}")
    print(f"  interactables : {obj_count}")


if __name__ == "__main__":
    main()
