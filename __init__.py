"""DUGCO Tools: a growing pack of custom nodes and workflows for ComfyUI.

Every Python file or package in ``nodes/`` is loaded automatically. To add a
node, drop a new file or folder in there (copy ``nodes/_template.py`` to
start). Names that start with an underscore are skipped.
"""

import importlib
import pkgutil
import traceback
from pathlib import Path

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web/js"

_nodes_dir = Path(__file__).parent / "nodes"

for _info in sorted(pkgutil.iter_modules([str(_nodes_dir)]), key=lambda m: m.name):
    if _info.name.startswith("_"):
        continue
    try:
        _module = importlib.import_module(f".nodes.{_info.name}", __name__)
    except Exception:
        # One broken node file must not take the rest of the pack down with it.
        print(f"[DUGCO Tools] Could not load nodes/{_info.name}.py:")
        traceback.print_exc()
        continue
    for _node_id in getattr(_module, "NODE_CLASS_MAPPINGS", {}):
        if _node_id in NODE_CLASS_MAPPINGS:
            print(f"[DUGCO Tools] nodes/{_info.name} re-registers node id {_node_id}; the later one wins.")
    NODE_CLASS_MAPPINGS.update(getattr(_module, "NODE_CLASS_MAPPINGS", {}))
    NODE_DISPLAY_NAME_MAPPINGS.update(getattr(_module, "NODE_DISPLAY_NAME_MAPPINGS", {}))

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
