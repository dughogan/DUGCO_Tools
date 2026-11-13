"""DUGco Pass Viewer: step through VFX passes (beauty, albedo, normals, depth, ...) inside a node."""
from .passes import LoadPassEXRs, PassesFromImages, PassViewer, PickPass

NODE_CLASS_MAPPINGS = {
    "DUGcoLoadPassEXRs": LoadPassEXRs,
    "DUGcoPassViewer": PassViewer,
    "DUGcoPassesFromImages": PassesFromImages,
    "DUGcoPickPass": PickPass,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DUGcoLoadPassEXRs": "DUGco Load VFX Pass EXRs",
    "DUGcoPassViewer": "DUGco Pass Viewer",
    "DUGcoPassesFromImages": "DUGco Passes From Images",
    "DUGcoPickPass": "DUGco Pick Pass",
}
# The viewer UI is web/js/pass_viewer.js, served by the pack's WEB_DIRECTORY.

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
