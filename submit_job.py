import urllib.request
import json

data = json.dumps({
    "name": "ArchwayFillerProps Test",
    "engine_type": "blender",
    "file_path": "F:\\Work\\unFoldAssets\\ArchwayFillerProps\\ArchwayFillerProps.blend",
    "output_folder": "F:\\Work\\unFoldAssets\\ArchwayFillerProps\\renders\\",
    "output_name": "render_",
    "output_format": "PNG",
    "is_animation": True,
    "frame_start": 0,
    "frame_end": 300,
    "original_start": 0,
    "target_worker": "Spencers-Laptop",
}).encode()

req = urllib.request.Request(
    "http://localhost:8080/api/jobs",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read().decode())
print(json.dumps(result, indent=2))
