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


# ── Room geometry ──────────────────────────────────────────────────────────────

def _static_box(
    b: TscnBuilder,
    name: str,
    parent: str,
    sx: float, sy: float, sz: float,
    lx: float, ly: float, lz: float,
    mat_rid: str,
) -> None:
    """StaticBody3D + MeshInstance3D + CollisionShape3D for one wall/floor/ceiling."""
    mesh_rid  = b.box_mesh(sx, sy, sz)
    shape_rid = b.box_shape(sx, sy, sz)
    b.node(name, "StaticBody3D", parent, {"transform": t3d(lx, ly, lz)})
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


def add_zone(b: TscnBuilder, zone: dict, doors: list[tuple[str, float]] | None = None) -> None:
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

    # floor / ceiling
    _static_box(b, f"Floor_{zid}",   zone_node, sx, t,  sz,  0,  -sy/2 + t/2,  0, floor_mat)
    _static_box(b, f"Ceiling_{zid}", zone_node, sx, t,  sz,  0,   sy/2 - t/2,  0, ceil_mat)
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

    r, g, b_c = _INTERACTABLE_RGB.get(otype, (0.5, 0.5, 0.5))
    mat = b.material(r, g, b_c)

    if otype == "artefact":
        mesh  = b.sphere_mesh(0.15)
        shape = b.sphere_shape(0.15)
        node_name = f"Artefact_{oid}"
        b.node(node_name, "RigidBody3D", zone_node, {
            "transform": t3d(lx, ly + 0.15, lz),
            "mass": "1.0",
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

    # Zones (with doorways cut where zones are adjacent)
    zones = scene_plan.get("zones", [])
    doors = _compute_doors(zones)
    for zone in zones:
        add_zone(b, zone, doors.get(zone["id"]))

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
