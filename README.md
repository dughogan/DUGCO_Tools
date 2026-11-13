# DUGCO Tools

A growing pack of custom nodes, workflows and demo videos for [ComfyUI](https://github.com/comfyanonymous/ComfyUI), built by Doug Hogan for real production work. New tools are added as they are published.

## Install

Clone the pack into your ComfyUI `custom_nodes` folder and restart ComfyUI:

```bash
git clone https://github.com/dughogan/DUGCO_Tools.git
```

Then install the Python requirements with the same Python that runs ComfyUI:

```bash
pip install -r DUGCO_Tools/requirements.txt
```

To update later, run `git pull` inside the `DUGCO_Tools` folder and restart ComfyUI.

## Nodes

All nodes appear under the **DUGCO** category in the node menu.

| Node | What it does | Demo |
| --- | --- | --- |
| *First nodes coming soon* | | |

## Workflows

Workflows live in [example_workflows](example_workflows) and also appear in ComfyUI's Templates browser once the pack is installed.

| Workflow | What it does | Demo |
| --- | --- | --- |
| *First workflows coming soon* | | |

## Demo videos

Short previews live in [demos](demos). Longer videos are linked from the tables above.

## What's in the repository

| Folder | Contents |
| --- | --- |
| `nodes/` | One Python file per node or group of nodes. Loaded automatically. |
| `web/js/` | Front-end extensions for nodes that need custom UI. |
| `example_workflows/` | Workflow `.json` files and their thumbnails. |
| `demos/` | Short demo clips, one folder per tool or workflow. |
| `tests/` | A smoke test that checks the pack loads. |

## License

[MIT](LICENSE)
