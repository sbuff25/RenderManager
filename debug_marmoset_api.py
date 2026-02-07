"""
Wain — Marmoset API Discovery Script
Run this via: toolbag.exe -hide debug_marmoset_api.py
Writes results to %TEMP%/_wain_api_discovery.json
"""
import mset
import json
import os
import sys

OUTPUT_PATH = os.path.join(os.environ.get("TEMP", "."), "_wain_api_discovery.json")
SCENE_PATH = r"F:/Work/unFoldAssets/DungeonElevator/DungeonEnterance/DungeonEnterance.tbscene"

results = {
    "mset_dir": [],
    "render_objects": [],
    "render_pass_classes": [],
    "pass_manipulation": [],
    "errors": [],
}

def log(msg):
    print(f"[Discovery] {msg}")
    sys.stdout.flush()

try:
    # 1. List all mset module contents
    mset_items = [x for x in dir(mset) if not x.startswith('_')]
    results["mset_dir"] = mset_items
    log(f"mset has {len(mset_items)} items")

    # 2. Find render-related classes/functions
    render_items = [x for x in mset_items if 'render' in x.lower() or 'pass' in x.lower()]
    results["render_related"] = render_items
    log(f"Render-related: {render_items}")

    # 3. Load scene
    log(f"Loading scene: {SCENE_PATH}")
    mset.loadScene(SCENE_PATH)
    log("Scene loaded")

    # 4. Find RenderObject(s)
    all_objects = mset.getAllObjects()
    for obj in all_objects:
        obj_type = type(obj).__name__
        if 'Render' in obj_type:
            obj_info = {
                "type": obj_type,
                "name": getattr(obj, "name", "?"),
                "dir": [x for x in dir(obj) if not x.startswith('_')],
            }

            # Check for renderPasses
            if hasattr(obj, 'renderPasses'):
                passes = obj.renderPasses
                obj_info["renderPasses_type"] = str(type(passes))
                obj_info["renderPasses_len"] = len(passes) if passes else 0
                pass_list = []
                for rp in (passes or []):
                    rp_info = {
                        "type": type(rp).__name__,
                        "dir": [x for x in dir(rp) if not x.startswith('_')],
                    }
                    if hasattr(rp, 'renderPass'):
                        rp_info["renderPass"] = rp.renderPass
                    if hasattr(rp, 'enabled'):
                        rp_info["enabled"] = rp.enabled
                    pass_list.append(rp_info)
                obj_info["passes"] = pass_list

            # Check for images property
            if hasattr(obj, 'images'):
                img = obj.images
                obj_info["images_type"] = str(type(img))
                obj_info["images_dir"] = [x for x in dir(img) if not x.startswith('_')]

            results["render_objects"].append(obj_info)
            log(f"Found render object: {obj_type} '{getattr(obj, 'name', '?')}'")

    # 5. Try to discover RenderPassOptions class
    for cls_name in ["RenderPassOptions", "RenderPass", "RenderPassObject"]:
        if hasattr(mset, cls_name):
            cls = getattr(mset, cls_name)
            cls_info = {
                "name": cls_name,
                "type": str(type(cls)),
                "dir": [x for x in dir(cls) if not x.startswith('_')],
            }
            # Try to instantiate
            try:
                instance = cls()
                cls_info["instantiable"] = True
                cls_info["instance_dir"] = [x for x in dir(instance) if not x.startswith('_')]
            except Exception as e:
                cls_info["instantiable"] = False
                cls_info["instantiate_error"] = str(e)
            results["render_pass_classes"].append(cls_info)
            log(f"Found class {cls_name}: instantiable={cls_info.get('instantiable')}")

    # 6. Try to manipulate render passes on the first RenderObject
    for obj in all_objects:
        if hasattr(obj, 'renderPasses'):
            passes = obj.renderPasses
            log(f"Trying to manipulate passes on {type(obj).__name__}")

            # Try A: Check if list supports append
            try:
                original_len = len(passes)
                # Try to find/create a RenderPassOptions
                for cls_name in ["RenderPassOptions", "RenderPass"]:
                    if hasattr(mset, cls_name):
                        try:
                            new_pass = getattr(mset, cls_name)()
                            new_pass.renderPass = "Normals"
                            new_pass.enabled = True
                            passes.append(new_pass)
                            new_len = len(passes)
                            results["pass_manipulation"].append({
                                "method": f"append({cls_name})",
                                "success": True,
                                "before": original_len,
                                "after": new_len,
                            })
                            log(f"append({cls_name}) worked! {original_len} -> {new_len}")
                            break
                        except Exception as e:
                            results["pass_manipulation"].append({
                                "method": f"append({cls_name})",
                                "success": False,
                                "error": str(e),
                            })
                            log(f"append({cls_name}) failed: {e}")
            except Exception as e:
                results["pass_manipulation"].append({
                    "method": "append",
                    "success": False,
                    "error": str(e),
                })

            # Try B: Enable existing passes
            for rp in (passes or []):
                if hasattr(rp, 'enabled'):
                    try:
                        old_val = rp.enabled
                        rp.enabled = True
                        new_val = rp.enabled
                        results["pass_manipulation"].append({
                            "method": "set_enabled",
                            "pass": getattr(rp, 'renderPass', '?'),
                            "old": old_val,
                            "new": new_val,
                            "success": old_val != new_val or new_val == True,
                        })
                        log(f"Set enabled on '{getattr(rp, 'renderPass', '?')}': {old_val} -> {new_val}")
                    except Exception as e:
                        results["pass_manipulation"].append({
                            "method": "set_enabled",
                            "success": False,
                            "error": str(e),
                        })

            # Try C: Direct list assignment
            try:
                # Try to see if renderPasses is settable
                obj.renderPasses = passes
                results["pass_manipulation"].append({
                    "method": "set_renderPasses",
                    "success": True,
                })
                log("Setting renderPasses directly worked")
            except Exception as e:
                results["pass_manipulation"].append({
                    "method": "set_renderPasses",
                    "success": False,
                    "error": str(e),
                })

            break  # Only try first render object

except Exception as e:
    log(f"Error: {e}")
    import traceback
    traceback.print_exc()
    results["errors"].append(str(e))

# Write results
try:
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    log(f"Results written to: {OUTPUT_PATH}")
except Exception as e:
    log(f"Failed to write results: {e}")

log("Done, quitting...")
mset.quit()
