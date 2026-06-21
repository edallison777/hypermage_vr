#!/usr/bin/env python3
"""
Assert a conditioned asset meets the Quest budget (F9 §4c.7 — off-headless verifiable).

Reads a *.manifest.json emitted by condition_asset.py and fails (exit 1) if the asset
is over the triangle or texture budget, or is missing its lightmap UV2. Run in CI / the
test pass so a regression in the conditioning stage (or a hand-dropped over-budget asset)
is caught without a headset.

  python tools/check_asset_budget.py assets/models/treasure_chest/treasure_chest.manifest.json
  python tools/check_asset_budget.py assets/models            # check every manifest under a dir
"""

import json
import sys
from pathlib import Path


def _check(manifest_path: Path) -> list[str]:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    errs: list[str] = []
    name = m.get("name", manifest_path.stem)
    tb = m.get("tri_budget", 0)
    if m.get("conditioned_tris", 1 << 30) > tb:
        errs.append(f"{name}: {m.get('conditioned_tris')} tris > budget {tb}")
    if not m.get("has_uv2", False):
        errs.append(f"{name}: missing UV2 (lightmap unwrap)")
    cap = m.get("tex_size_budget", 0)
    for t in m.get("textures", []):
        if max(t.get("w", 0), t.get("h", 0)) > cap:
            errs.append(f"{name}: texture {t.get('name')} {t.get('w')}x{t.get('h')} > {cap}")
    return errs


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_asset_budget.py <manifest.json | dir>", file=sys.stderr)
        return 2
    target = Path(sys.argv[1])
    manifests = (
        sorted(target.rglob("*.manifest.json")) if target.is_dir() else [target]
    )
    if not manifests:
        print(f"check_asset_budget: no manifests under {target}", file=sys.stderr)
        return 2

    all_errs: list[str] = []
    for mp in manifests:
        errs = _check(mp)
        status = "FAIL" if errs else "PASS"
        print(f"[{status}] {mp}")
        all_errs.extend(errs)

    for e in all_errs:
        print("  -", e, file=sys.stderr)
    return 1 if all_errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
