"""
Wain — Viewport Pass Name Discovery
Tests which viewportPass names actually produce different output.
Run via: toolbag.exe -hide debug_viewport_passes.py
"""
import mset
import json
import os
import sys
import hashlib

OUTPUT_DIR = os.path.join(os.environ.get("TEMP", "."), "_wain_pass_test")
RESULT_PATH = os.path.join(os.environ.get("TEMP", "."), "_wain_pass_test_results.json")
SCENE_PATH = r"F:/Work/unFoldAssets/DungeonElevator/DungeonEnterance/DungeonEnterance.tbscene"

# All candidate pass names to test
TEST_NAMES = [
    "",                     # Should be Full Quality / beauty
    "Full Quality",
    "Wireframe",
    "wireframe",
    "Normals",
    "normals",
    "Depth",
    "depth",
    "Unlit",
    "unlit",
    "Albedo",
    "albedo",
    "Ambient Occlusion",
    "AO",
    "Roughness",
    "Metalness",
    "Shadow",
    "Emissive",
    "UV Islands",
    "Alpha Mask",
    "Position",
    "Diffuse Lighting",
    "Specular Lighting",
    "Lighting (Direct)",
    "Lighting (Indirect)",
    "Reflection",
    "Cavity",
    "Curvature",
    "Thickness",
    "Transparency",
    "Subsurface",
    "Matte",
    "Object ID",
    "Group ID",
    "Material ID",
]

def log(msg):
    print(f"[PassTest] {msg}")
    sys.stdout.flush()

def file_hash(path):
    """Get hash of first 4KB to quickly compare images."""
    try:
        with open(path, 'rb') as f:
            return hashlib.md5(f.read(4096)).hexdigest()
    except Exception:
        return None

results = {"tests": [], "errors": [], "render_object_passes": []}

try:
    log(f"Loading scene: {SCENE_PATH}")
    mset.loadScene(SCENE_PATH)
    log("Scene loaded")

    # List existing render passes from RenderObject
    for obj in mset.getAllObjects():
        if type(obj).__name__ == 'RenderObject':
            for rp in (obj.renderPasses or []):
                name = getattr(rp, 'renderPass', '?')
                enabled = getattr(rp, 'enabled', '?')
                results["render_object_passes"].append({"name": name, "enabled": enabled})
                log(f"RenderObject pass: '{name}' (enabled={enabled})")
            break

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Render beauty first as baseline
    beauty_path = os.path.join(OUTPUT_DIR, "test_beauty.png")
    log("Rendering beauty baseline...")
    mset.renderCamera(beauty_path, width=256, height=256, sampling=1)
    beauty_hash = file_hash(beauty_path)
    beauty_size = os.path.getsize(beauty_path) if os.path.exists(beauty_path) else 0
    log(f"Beauty: {beauty_size} bytes, hash={beauty_hash}")

    # Test each pass name
    for name in TEST_NAMES:
        if name == "":
            continue  # Already tested as beauty
        test_path = os.path.join(OUTPUT_DIR, f"test_{name.replace(' ', '_').replace('(', '').replace(')', '')}.png")
        try:
            mset.renderCamera(test_path, width=256, height=256, sampling=1, viewportPass=name)
            if os.path.exists(test_path):
                size = os.path.getsize(test_path)
                h = file_hash(test_path)
                is_different = (h != beauty_hash)
                result = {
                    "name": name,
                    "rendered": True,
                    "size": size,
                    "different_from_beauty": is_different,
                }
                status = "UNIQUE" if is_different else "same as beauty"
                log(f"  '{name}': {size} bytes [{status}]")
            else:
                result = {"name": name, "rendered": False, "error": "no output file"}
                log(f"  '{name}': NO OUTPUT")
        except Exception as e:
            result = {"name": name, "rendered": False, "error": str(e)}
            log(f"  '{name}': ERROR {e}")
        results["tests"].append(result)

except Exception as e:
    log(f"Error: {e}")
    import traceback
    traceback.print_exc()
    results["errors"].append(str(e))

# Write results
try:
    with open(RESULT_PATH, 'w') as f:
        json.dump(results, f, indent=2)
    log(f"Results written to: {RESULT_PATH}")
except Exception as e:
    log(f"Failed to write: {e}")

# Cleanup test images
try:
    import shutil
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
except Exception:
    pass

log("Done")
mset.quit()
