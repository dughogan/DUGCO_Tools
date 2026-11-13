"""Starting point for a new DUGCO node.

Copy this file to ``nodes/<your_node>.py`` (no leading underscore) and edit it.
A tool with several files can be a folder instead: ``nodes/<your_tool>/__init__.py``.
The pack loads it on the next ComfyUI restart. This template itself is skipped
because its name starts with an underscore.

Conventions for this pack:
  * Node ids start with ``DUGco`` (``DUGcoFilmFinish``) so they never clash with
    other packs. Never rename an id once published: saved workflows break.
  * Display names start with ``DUGco``; the category is ``DUGco/<group>``.
  * Front-end code goes in ``web/js/``, example workflows in
    ``example_workflows/``, and a guide in ``docs/``.
"""


class DUGcoTemplateNode:
    CATEGORY = "DUGco/Utilities"
    FUNCTION = "run"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    DESCRIPTION = "Describe what the node does in one sentence."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    def run(self, image, strength):
        return (image * strength,)


NODE_CLASS_MAPPINGS = {"DUGcoTemplateNode": DUGcoTemplateNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DUGcoTemplateNode": "DUGco Template Node"}
