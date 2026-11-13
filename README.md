# DUGCO Tools

A growing pack of custom nodes, workflows and demo videos for [ComfyUI](https://github.com/comfyanonymous/ComfyUI), built by Doug Hogan for real production work. New tools are added as they are published.

## Install

Clone the pack into your ComfyUI `custom_nodes` folder:

```bash
git clone https://github.com/dughogan/DUGCO_Tools.git
```

Install the Python requirements with the same Python that runs ComfyUI, then restart ComfyUI:

```bash
pip install -r DUGCO_Tools/requirements.txt
```

To update later, run `git pull` inside the `DUGCO_Tools` folder and restart ComfyUI.

**Already have one of these as a separate pack?** Remove the standalone copy first (for example `exr_multi_pass_exporter`). Two packs that register the same node will clash.

## Nodes

All nodes appear under the **DUGco** category in the node menu.

| Tool | Nodes | What it does | Guide |
| --- | --- | --- | --- |
| **Pass Viewer** | Load VFX Pass EXRs, Passes From Images, Pass Viewer, Pick Pass | Step through the VFX passes of a shot inside one node: beauty, alpha, albedo, normals, depth and more, with scrub and playback. | [Guide](docs/pass_viewer.md) |
| **Multi-Pass EXR Exporter** | Multi-Pass EXR Exporter, Add Pass | Write any number of passes into multi-channel EXR sequences with proper channel names. | [Guide](docs/exr_multi_pass_exporter.md) |
| **Film Finish** | Film Finish | Make AI and digital renders read as 35mm film: de-clarity, film curve, halation, grain, gate weave. | [Guide](docs/film_finish.md) |

### What each tool needs

| Tool | Extra requirements |
| --- | --- |
| Pass Viewer | `OpenEXR`, `av`, `opencv-python` (in `requirements.txt`) |
| Multi-Pass EXR Exporter | `OpenEXR`, `Imath` (in `requirements.txt`) |
| Film Finish | None |

## Workflows

Workflows live in [example_workflows](example_workflows) and also appear in ComfyUI's Templates browser once the pack is installed. The video workflows use [Video Helper Suite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) to load and save clips.

| Workflow | What it does |
| --- | --- |
| [DUGco Pass Viewer - VFX Passes](example_workflows/DUGco%20Pass%20Viewer%20-%20VFX%20Passes.json) | Load a folder of multi-layer EXR frames and step through every pass. |
| [DUGco Film Finish - video](example_workflows/DUGco%20Film%20Finish%20-%20video.json) | Load a clip, apply the film finish, save at a grain-safe bitrate. |

## Demo videos

Short previews live in [demos](demos). None are published yet.

## What's in the repository

| Folder | Contents |
| --- | --- |
| `nodes/` | One Python file or folder per tool. Loaded automatically. |
| `web/js/` | Front-end code for nodes with custom UI. |
| `example_workflows/` | Workflow `.json` files and their thumbnails. |
| `docs/` | A guide for each tool. |
| `demos/` | Short demo clips, one folder per tool or workflow. |
| `tests/` | A smoke test that checks the pack loads. |

## License

[MIT](LICENSE)
