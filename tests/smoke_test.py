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
    check_exr_round_trip(pack)
    print("OK: exporter -> EXR -> Pass Viewer loader round trip")


if __name__ == "__main__":
    main()
