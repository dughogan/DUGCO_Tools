"""Checks the pack loads the way ComfyUI loads it, then runs the nodes that need no model.

The nodes import ComfyUI modules, so point the test at a ComfyUI checkout and
run it with ComfyUI's own Python:

    set COMFYUI_PATH=C:\\path\\to\\ComfyUI
    python tests/smoke_test.py
"""

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPECTED = {
    "DUGcoLoadPassEXRs", "DUGcoPassViewer", "DUGcoPassesFromImages", "DUGcoPickPass",
    "DUGcoFilmFinish", "MultiPassEXRExporter", "AddPass",
    "DUGcoRepeatLatentFrames", "DUGcoSelectEveryNthFrame",
    "DUGcoTrackPathToShot",
    "LightTransfer", "TemporalDeflicker", "AddLightFromPasses",
    "ComfyAuditStudioProfile", "ComfyAuditWorkflow", "ComfyAuditClaudeReview", "ComfyAuditGate", "ComfyAuditHistoryGate",
    "ComfyAuditSaveReport",
}


def load_pack():
    comfy = os.environ.get("COMFYUI_PATH")
    if not comfy or not (Path(comfy) / "folder_paths.py").is_file():
        sys.exit("Set COMFYUI_PATH to a ComfyUI checkout (the folder that holds folder_paths.py).")
    sys.path.insert(0, comfy)
    sys.argv = [sys.argv[0], "--cpu"]  # ComfyUI reads its options from argv; stay off the GPU
    spec = importlib.util.spec_from_file_location(
        "dugco_tools_under_test", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check_registration(pack):
    classes, names = pack.NODE_CLASS_MAPPINGS, pack.NODE_DISPLAY_NAME_MAPPINGS
    missing = EXPECTED - set(classes)
    assert not missing, f"nodes did not load: {sorted(missing)}"
    for node_id, cls in classes.items():
        assert node_id in names, f"{node_id}: missing display name"
        assert hasattr(cls, "INPUT_TYPES"), f"{node_id}: missing INPUT_TYPES"
        cls.INPUT_TYPES()
        assert hasattr(cls, getattr(cls, "FUNCTION", "")), f"{node_id}: FUNCTION method not found"
    web = ROOT / pack.WEB_DIRECTORY
    assert web.is_dir() and list(web.glob("*.js")), "WEB_DIRECTORY has no JavaScript"
    print(f"OK: {len(classes)} nodes registered")


def check_film_finish(pack):
    import torch

    node = pack.NODE_CLASS_MAPPINGS["DUGcoFilmFinish"]()
    frames = torch.rand(3, 64, 96, 3)
    (out,) = node.run(frames, "500T", 1.0, 1.0, 1.0, 1.0, True, 0.006, 0)
    assert out.shape == frames.shape and torch.isfinite(out).all()
    assert not torch.equal(out, frames), "Film Finish returned the input unchanged"
    print("OK: Film Finish ran on 3 frames")


def check_frame_tools(pack):
    import torch

    repeat = pack.NODE_CLASS_MAPPINGS["DUGcoRepeatLatentFrames"]()
    video = {"samples": torch.arange(5.0).view(1, 1, 5, 1, 1).repeat(1, 2, 1, 3, 3), "noise_mask": torch.ones(1)}
    (out,) = repeat.run(video, 2, True, 0)
    assert out["samples"][0, 0, :, 0, 0].tolist() == [0, 1, 1, 2, 2, 3, 3, 4, 4] and "noise_mask" not in out
    (out,) = repeat.run(video, 3, False, 2)
    assert out["samples"][0, 0, :, 0, 0].tolist() == [0, 0, 0, 1, 1, 1]
    image = {"samples": torch.rand(1, 4, 8, 8)}
    assert repeat.run(image, 2, True, 0)[0]["samples"].shape == (1, 4, 8, 8), "image latents must pass through"

    every = pack.NODE_CLASS_MAPPINGS["DUGcoSelectEveryNthFrame"]()
    frames = torch.arange(10.0).view(10, 1, 1, 1).repeat(1, 2, 2, 3)
    assert every.run(frames, 2, 0, 0)[0][:, 0, 0, 0].tolist() == [0, 2, 4, 6, 8]
    assert every.run(frames, 3, 1, 2)[0][:, 0, 0, 0].tolist() == [1, 4]
    print("OK: Frame Tools repeat and select the right frames")


def check_track_path(pack):
    """Track Path To Shot with tracking off needs no model: the route is only timed, not tracked."""
    import json

    import torch

    node = pack.NODE_CLASS_MAPPINGS["DUGcoTrackPathToShot"]()
    frames = torch.rand(12, 64, 96, 3)
    route = json.dumps([{"x": 10 + 4 * i, "y": 50 - 3 * i} for i in range(8)])
    canvas = torch.zeros(1, 128, 192)                       # the route was drawn on a canvas twice the shot's size
    coords, preview, count = node.run(frames, route, 0, 0, 2, 9, False, 32, 2, 768, path_canvas=canvas)
    points = json.loads(coords)
    assert count == 12 and len(points) == 12 and preview.shape == frames.shape
    assert points[0] == points[2] == {"x": 5.0, "y": 25.0}, "the point should wait at the start until start_frame"
    assert points[9] == points[11] == {"x": 19.0, "y": 14.5}, "the point should wait at the end after end_frame"
    print("OK: Track Path To Shot times a route (tracking off)")


def check_exr_round_trip(pack):
    """Exporter writes multi-channel EXRs; the Pass Viewer loader reads them back."""
    import torch

    c = pack.NODE_CLASS_MAPPINGS
    frames, h, w = 2, 32, 48
    rgb = torch.rand(frames, h, w, 3)
    depth = torch.rand(frames, h, w, 1).repeat(1, 1, 1, 3)

    def call(node_id, *args, **kwargs):
        node = c[node_id]()
        return getattr(node, c[node_id].FUNCTION)(*args, **kwargs)

    with tempfile.TemporaryDirectory() as tmp:
        (passes,) = call("AddPass", image=depth, pass_name="depth")[:1]
        call("MultiPassEXRExporter", rgb=rgb, output_name="smoke", output_path=tmp, start_frame=1001,
             colorspace="linear", passes=passes)
        written = sorted(Path(tmp).rglob("*.exr"))
        assert len(written) == frames, f"expected {frames} EXRs, found {len(written)}"

        pass_set, count, info = call("DUGcoLoadPassEXRs", str(written[0].parent), 24.0, 0, 0)
        assert count == frames, info
        assert {"beauty", "depth"} <= set(pass_set["layers"]), f"layers found: {list(pass_set['layers'])}"
        print("   Loader says:", info.replace("\n", " | "))


def main():
    pack = load_pack()
    check_registration(pack)
    check_film_finish(pack)
    check_frame_tools(pack)
    check_track_path(pack)
    check_exr_round_trip(pack)
    print("OK: exporter -> EXR -> Pass Viewer loader round trip")


if __name__ == "__main__":
    main()
