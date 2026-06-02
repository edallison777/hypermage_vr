#!/usr/bin/env python3
"""
G4 pipeline: natural language description → ScenePlan → .tscn → APK → Quest 3

Usage
  python build_vr_room.py "a medieval tavern with a fireplace and a suspicious merchant"
  python build_vr_room.py "alien research lab" --install
  python build_vr_room.py "haunted library" --no-build   # generate scene only
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

import anthropic

GODOT_EXE   = r"C:\Tools\Godot\Godot_v4.6.3-stable_win64_console.exe"
TOOLS_DIR   = Path(__file__).parent
PROJECT_DIR = TOOLS_DIR.parent
PROJECT_GODOT = PROJECT_DIR / "project.godot"
CONVERTER   = TOOLS_DIR / "sceneplan_to_tscn.py"
EXPORT_APK  = PROJECT_DIR / "export" / "HyperMageVR.apk"
EXAMPLE_SP  = TOOLS_DIR / "test_sceneplan.json"

SYSTEM_PROMPT = """\
You are a VR level designer for HyperMageVR. Given a natural language description, output a ScenePlan JSON document.

Rules:
- Output ONLY valid JSON — no markdown fences, no explanation
- Use Unreal Engine coordinate system: X-forward, Y-right, Z-up, centimetres
- scene_type must be one of: exploration, ritual, social, sanctuary, cyberspace, narrative, combat, objective
- Zone bounds.extents are HALF-extents in cm (a 4m wide room has extents.x = 200)
- Typical room: extents x:150-300, y:150-300, z:150-350
- Place zones next to each other (advance center.y by ~2× the previous zone's extents.y)
- Player spawns slightly inside the first zone at floor level (z: 0)
- Include 1-3 zones, 1-3 interactables per zone
- interactable type must be one of: artefact, machinery, creature, environmental
- Give each item a unique slug id (snake_case)
- id field: slugified scene name, e.g. "medieval-tavern"

Here is a complete example to follow exactly:

{example}
"""


def generate_sceneplan(description: str) -> dict:
    example = EXAMPLE_SP.read_text(encoding="utf-8")
    client  = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT.format(example=example),
        messages=[{"role": "user", "content": description}],
    )
    text = response.content[0].text.strip()
    # Strip accidental markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def update_main_scene(tscn_path: Path) -> None:
    rel = tscn_path.relative_to(PROJECT_DIR)
    res_path = "res://" + str(rel).replace("\\", "/")
    content  = PROJECT_GODOT.read_text(encoding="utf-8")
    content  = re.sub(r'run/main_scene="[^"]*"', f'run/main_scene="{res_path}"', content)
    PROJECT_GODOT.write_text(content, encoding="utf-8")
    print(f"      main_scene -> {res_path}")


def build_apk() -> Path:
    result = subprocess.run([
        GODOT_EXE,
        "--headless",
        "--path", str(PROJECT_DIR),
        "--export-debug", "Android",
        str(EXPORT_APK),
    ])
    if result.returncode != 0:
        raise RuntimeError(f"Godot export failed (code {result.returncode})")
    if not EXPORT_APK.exists():
        raise RuntimeError("Export completed but APK file not found")
    return EXPORT_APK


def sideload(apk_path: Path) -> None:
    subprocess.run(["adb", "install", "-r", str(apk_path)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="G4 pipeline: description → VR APK")
    parser.add_argument("description", nargs="?", help="Natural language room description")
    parser.add_argument("--install",   action="store_true", help="Sideload to Quest 3 after build")
    parser.add_argument("--no-build",  action="store_true", help="Generate .tscn only, skip APK build")
    parser.add_argument("--sceneplan", help="Path to pre-generated ScenePlan JSON (skips API call)")
    args = parser.parse_args()

    if not args.sceneplan and not args.description:
        parser.error("Provide a description or --sceneplan <path>")

    # ── Step 1: Generate or load ScenePlan ────────────────────────────────────
    if args.sceneplan:
        print(f"\n[1/4] Loading ScenePlan from {args.sceneplan} ...")
        sceneplan = json.loads(Path(args.sceneplan).read_text(encoding="utf-8"))
    else:
        print(f"\n[1/4] Generating ScenePlan ...")
        print(f"      Input: {args.description!r}")
        sceneplan  = generate_sceneplan(args.description)
    scene_id   = sceneplan.get("id", str(uuid.uuid4()))
    zone_count = len(sceneplan.get("zones", []))
    obj_count  = sum(len(z.get("interactables", [])) for z in sceneplan.get("zones", []))
    print(f"      Scene: {sceneplan.get('name')}  (id={scene_id}, {zone_count} zones, {obj_count} objects)")

    sp_path = TOOLS_DIR / "last_sceneplan.json"
    sp_path.write_text(json.dumps(sceneplan, indent=2), encoding="utf-8")
    print(f"      Saved: {sp_path}")

    # ── Step 2: Convert to .tscn ──────────────────────────────────────────────
    print("[2/4] Converting ScenePlan to .tscn (VR mode) ...")
    tscn_out = PROJECT_DIR / "scenes" / "generated" / f"{scene_id}.tscn"
    result   = subprocess.run(
        [sys.executable, str(CONVERTER), str(sp_path), "--vr", "-o", str(tscn_out)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("Converter failed")
    print(f"      {result.stdout.strip()}")

    # ── Step 3: Update main scene ─────────────────────────────────────────────
    print("[3/4] Updating project main scene ...")
    update_main_scene(tscn_out)

    if args.no_build:
        print("\n--no-build set -- stopping here. Open the editor to preview the scene.")
        return

    # ── Step 4a: Build APK ────────────────────────────────────────────────────
    print("[4a/4] Building APK (headless Godot) ...")
    apk = build_apk()
    size_mb = apk.stat().st_size / 1_048_576
    print(f"       APK: {apk}  ({size_mb:.1f} MB)")

    # ── Step 4b: Sideload ─────────────────────────────────────────────────────
    if args.install:
        print("[4b/4] Sideloading to Quest 3 ...")
        sideload(apk)
        print("       Installed. Launch from Unknown Sources in the Quest library.")
    else:
        print("       (pass --install to sideload automatically)")

    print("\nDone.")


if __name__ == "__main__":
    main()
