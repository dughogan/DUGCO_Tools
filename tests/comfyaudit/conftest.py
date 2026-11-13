"""Make the pack importable as ``comfyaudit`` however the tests are invoked.

The pack directory *is* the Python package, because that is what ComfyUI
requires of a custom node pack, so its parent has to be on ``sys.path``.
"""

import os
import sys

# In DUGCO Tools the package lives at <repo>/nodes/comfyaudit, so <repo>/nodes goes on the path.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACK_ROOT = os.path.join(REPO, "nodes", "comfyaudit")
PARENT = os.path.dirname(PACK_ROOT)

if PARENT not in sys.path:
    sys.path.insert(0, PARENT)
