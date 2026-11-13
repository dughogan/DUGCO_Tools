"""Starting point for a new DUGCO node.

Copy this file to ``nodes/<your_node>.py`` (no leading underscore) and edit it.
The pack loads it on the next ComfyUI restart. This template itself is skipped
because its name starts with an underscore.

Conventions for this pack:
  * Node ids start with ``DUGCO_`` so they never clash with other packs.
  * Display names are plain and readable; the category is ``DUGCO`` or
    ``DUGCO/<group>``.
"""


class DUGCOTemplateNode:
    CATEGORY = "DUGCO"
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


NODE_CLASS_MAPPINGS = {"DUGCO_TemplateNode": DUGCOTemplateNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DUGCO_TemplateNode": "Template Node"}
