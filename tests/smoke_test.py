"""Checks the pack loads the way ComfyUI loads it. Run: python tests/smoke_test.py"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_pack():
    spec = importlib.util.spec_from_file_location(
        "dugco_tools_under_test", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    pack = load_pack()
    classes = pack.NODE_CLASS_MAPPINGS
    names = pack.NODE_DISPLAY_NAME_MAPPINGS

    node_files = [p for p in (ROOT / "nodes").glob("*.py") if not p.name.startswith("_")]
    if node_files:
        assert classes, "node files exist but no nodes were registered"

    for node_id, cls in classes.items():
        assert node_id.startswith("DUGCO_"), f"{node_id}: node ids must start with DUGCO_"
        assert node_id in names, f"{node_id}: missing display name"
        assert hasattr(cls, "INPUT_TYPES"), f"{node_id}: missing INPUT_TYPES"
        assert hasattr(cls, getattr(cls, "FUNCTION", "")), f"{node_id}: FUNCTION method not found"

    assert (ROOT / pack.WEB_DIRECTORY).is_dir(), "WEB_DIRECTORY does not exist"
    print(f"OK: {len(classes)} node(s) registered from {len(node_files)} file(s)")


if __name__ == "__main__":
    main()
