# Surface textures — provenance

All **CC0** (public domain) from **Poly Haven** (https://polyhaven.com), 1k JPG, full PBR
set (diffuse + nor_gl[OpenGL normal] + arm[occlusion/roughness/metallic]) — the ARM pack maps
straight onto the converter's `materials` block ORM support (occlusion=R/roughness=G/metallic=B).

| folder | asset | use |
|---|---|---|
| `cobblestone_floor_08/` | https://polyhaven.com/a/cobblestone_floor_08 | vault floor |
| `medieval_blocks_05/`   | https://polyhaven.com/a/medieval_blocks_05   | vault walls |

Wired via the ScenePlan zone `materials` block (see `tools/graphics_test.json`): `albedo` +
`normal` + `orm` paths + `tiling`. Committed directly (1k is within the Quest texture budget,
no conditioning needed); `*.import` regenerates on Godot import (gitignored). Larger source
(2k/4k) would be downscaled by `tools/condition_asset.py`'s texture-budget step first.
