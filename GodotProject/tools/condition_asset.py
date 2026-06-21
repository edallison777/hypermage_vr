#!/usr/bin/env python3
"""
Headless asset-conditioning stage (F9 §4c.4) — Blender background script.

Takes a source glTF/glb (curated Poly Haven CC0, or the in-house Meshy→Blender output)
and produces a *Quest-ready* asset the converter can reference:

  • DECIMATE the mesh to a triangle budget (the standalone Quest is a mobile tile GPU —
    photoscan/CAD source meshes are far over budget).
  • UV2 unwrap (a second UV set) so the asset is lightmap-ready for the optional hero bake.
  • TEXTURE budget: downscale any map larger than the texture budget (≤1–2K on Quest).
    Poly Haven already ships an ARM pack (occlusion=R / roughness=G / metallic=B) + normal,
    which maps straight onto our StandardMaterial3D ORM support — we keep that packing.
  • Export a single `.glb` (textures embedded) + a manifest JSON with the before/after
    numbers and a budget PASS/FAIL (asserted off-headless by tools/check_asset_budget.py).

Runtime LODs are left to Godot's glTF importer (it builds mesh LODs with meshoptimizer
on import — `generate_lods` on by default), so this stage owns the things Godot can NOT
do headlessly (quadric decimation, UV unwrap, texture resize) and Godot owns the rest.
This is build-time only; Blender never runs at game/convert time.

Run (Blender batch mode — NO GUI, headless-safe):
  blender --background --python tools/condition_asset.py -- \
      --input asset_src/treasure_chest/treasure_chest_1k.gltf \
      --output-dir assets/models/treasure_chest \
      --name treasure_chest --tri-budget 4000 --tex-size 1024
"""

import argparse
import json
import os
import sys

import bpy


def _argv_after_ddash() -> list[str]:
    """Blender passes script args after a bare '--'."""
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def _reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _import(path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".gltf", ".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise SystemExit(f"condition_asset: unsupported input format {ext!r}")


def _mesh_objects() -> list:
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def _tri_count(obj) -> int:
    """Evaluated triangle count (after modifiers), via the dependency graph."""
    deps = bpy.context.evaluated_depsgraph_get()
    me = obj.evaluated_get(deps).to_mesh()
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    obj.evaluated_get(deps).to_mesh_clear()
    return n


def _join_meshes(meshes: list):
    """Join all meshes into one object so the prop is a single draw + a single decimate
    target. Returns the surviving object."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def _decimate(obj, tri_budget: int) -> None:
    cur = _tri_count(obj)
    if cur <= tri_budget:
        return
    mod = obj.modifiers.new("condition_decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = max(0.01, tri_budget / float(cur))
    mod.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)


def _add_uv2(obj) -> None:
    """Add a lightmap UV set (UV2) via Smart UV Project, leaving UV0 (the texture UVs)
    untouched. Godot reads the *second* UV layer as UV2 for lightmapping."""
    me = obj.data
    if len(me.uv_layers) >= 2:
        return
    uv2 = me.uv_layers.new(name="UV2")
    me.uv_layers.active = uv2
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.03)
    bpy.ops.object.mode_set(mode="OBJECT")
    # Restore UV0 as the render-active set so the albedo/normal/ORM maps still sample right.
    me.uv_layers.active_index = 0


def _condition_textures(tex_size: int) -> list[dict]:
    """Downscale any image larger than the texture budget (square cap). Returns the
    final per-image sizes for the manifest."""
    out = []
    for img in bpy.data.images:
        if img.size[0] == 0 or img.size[1] == 0:
            continue
        w, h = img.size[0], img.size[1]
        if max(w, h) > tex_size:
            nw = min(w, tex_size)
            nh = min(h, tex_size)
            img.scale(nw, nh)
        out.append({"name": img.name, "w": img.size[0], "h": img.size[1]})
    return out


def _export_glb(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,          # apply modifiers
        export_yup=True,            # Godot/glTF +Y up
        export_texcoords=True,
        export_normals=True,
        export_tangents=True,       # ship tangents so the normal map is correct without recompute
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--tri-budget", type=int, default=4000)
    p.add_argument("--tex-size", type=int, default=1024)
    args = p.parse_args(_argv_after_ddash())

    _reset_scene()
    _import(args.input)
    meshes = _mesh_objects()
    if not meshes:
        raise SystemExit("condition_asset: no mesh found in input")

    src_tris = sum(_tri_count(o) for o in meshes)
    obj = _join_meshes(meshes)
    _decimate(obj, args.tri_budget)
    out_tris = _tri_count(obj)
    _add_uv2(obj)
    uv2 = len(obj.data.uv_layers) >= 2

    out_glb = os.path.join(args.output_dir, f"{args.name}.glb")
    textures = _condition_textures(args.tex_size)
    _export_glb(out_glb)

    # GLB embeds its textures (self-contained), but the exporter can drop redundant
    # external image copies beside it — remove them so the committed artefact set is just
    # the .glb + manifest (+ any hand-authored CREDITS.md).
    keep = {f"{args.name}.glb", f"{args.name}.manifest.json", "credits.md"}
    for fn in os.listdir(args.output_dir):
        if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bin")) and fn not in keep:
            os.remove(os.path.join(args.output_dir, fn))

    over_tex = [t for t in textures if max(t["w"], t["h"]) > args.tex_size]
    manifest = {
        "name": args.name,
        "source": os.path.basename(args.input),
        "glb": os.path.basename(out_glb),
        "tri_budget": args.tri_budget,
        "tex_size_budget": args.tex_size,
        "source_tris": src_tris,
        "conditioned_tris": out_tris,
        "has_uv2": uv2,
        "textures": textures,
        "pass": bool(out_tris <= args.tri_budget and uv2 and not over_tex),
    }
    mpath = os.path.join(args.output_dir, f"{args.name}.manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("condition_asset: wrote", out_glb)
    print("condition_asset: tris %d -> %d (budget %d), uv2=%s, textures=%d, PASS=%s" % (
        src_tris, out_tris, args.tri_budget, uv2, len(textures), manifest["pass"]))


if __name__ == "__main__":
    main()
