# Surface textures — provenance

All **CC0** (public domain) from **Poly Haven** (https://polyhaven.com), 1k JPG, full PBR
set (diffuse + nor_gl[OpenGL normal] + arm[occlusion/roughness/metallic]) — the ARM pack maps
straight onto the converter's `materials` block ORM support (occlusion=R/roughness=G/metallic=B).

| folder | asset | use |
|---|---|---|
| `cobblestone_floor_08/` | https://polyhaven.com/a/cobblestone_floor_08 | vault floor |
| `medieval_blocks_05/`   | https://polyhaven.com/a/medieval_blocks_05   | vault walls |
| `cliff_side/`           | https://polyhaven.com/a/cliff_side           | waterfall cliff face |
| `forrest_ground_01/`    | https://polyhaven.com/a/forrest_ground_01    | rural ground / riverbank |
| `pebbles/`              | https://polyhaven.com/a/pebbles              | riverbed / pool bottom |
| `leafy_grass/`          | https://polyhaven.com/a/leafy_grass          | grass variation / billboards |
| `rock_face_03/`         | https://polyhaven.com/a/rock_face_03         | scattered boulders |

Wired via the ScenePlan zone `materials` block (see `tools/graphics_test.json`): `albedo` +
`normal` + `orm` paths + `tiling`. Committed directly (1k is within the Quest texture budget).
The `*.import` files ARE version-controlled (`!assets/**/*.import` in `.gitignore`) so the
Quest conditioning sticks: `compress/mode=2` (VRAM ETC2/ASTC), `mipmaps/generate=true`, and
`compress/normal_map=1` on the `nor_gl` maps (standalone normals import gamma-wrong otherwise —
glTF sets this automatically, standalone material textures do not). Larger source (2k/4k) would
be downscaled by `tools/condition_asset.py`'s texture-budget step first.
