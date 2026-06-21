# Treasure Chest — asset provenance

- **Asset:** Treasure Chest (`treasure_chest`)
- **Source:** Poly Haven — https://polyhaven.com/a/treasure_chest
- **Author:** Rico Cilliers
- **License:** **CC0** (public domain — no attribution required; credited here as courtesy)
- **Downloaded:** glTF 1k set (diffuse + ARM[occlusion/roughness/metallic] + normal-GL) via
  the Poly Haven API (`api.polyhaven.com/files/treasure_chest`).

## Conditioning (F9 §4c.4)
Raw source (gitignored under `asset_src/treasure_chest/`) was run through
`tools/condition_asset.py` (headless Blender):

| | source | conditioned |
|---|---|---|
| triangles | 103,330 | 4,000 |
| UV2 (lightmap) | — | yes |
| textures | 1024² ARM/diff/nor | 1024² (within Quest budget) |

Reproduce:
```
blender --background --python tools/condition_asset.py -- \
    --input asset_src/treasure_chest/treasure_chest_1k.gltf \
    --output-dir assets/models/treasure_chest --name treasure_chest \
    --tri-budget 4000 --tex-size 1024
python tools/check_asset_budget.py assets/models
```
Committed artefacts: `treasure_chest.glb` (textures embedded) + `treasure_chest.manifest.json`.
`*.import` regenerates on Godot import (gitignored, like the generated scenes).
