# 3D models — provenance

| folder | asset | source | use |
|---|---|---|---|
| `treasure_chest/` | conditioned hero asset | (see condition pipeline) | vault hero prop |
| `boulder_01/` | https://polyhaven.com/a/boulder_01 | Poly Haven (CC0) | waterfall boulder |
| `rock_07/`    | https://polyhaven.com/a/rock_07    | Poly Haven (CC0) | waterfall rock |
| `stone_01/`   | https://polyhaven.com/a/stone_01   | Poly Haven (CC0) | waterfall stone |

The Poly Haven rocks are the **glTF-separate** 1k pack (gltf + .bin + textures) committed
as-is — Godot generates runtime LODs (meshoptimizer) on import. In the watercolour scene their
own PBR materials are overridden at runtime by `scripts/apply_watercolour.gd` (the model gives
the rounded SHAPE; the watercolour shader gives the look), so the bundled textures aren't shown
there but are kept for reuse in non-stylised scenes.
