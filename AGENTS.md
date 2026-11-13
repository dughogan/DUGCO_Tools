# AGENTS.md

Instructions for an AI coding agent that has been asked to **install DUGCO Tools into someone's ComfyUI**, or to fix an install that is not working. If you were asked to add a new tool to this pack instead, read [CONTRIBUTING.md](CONTRIBUTING.md).

DUGCO Tools is a ComfyUI custom node pack: nine nodes in four tools (Pass Viewer, Multi-Pass EXR Exporter, Film Finish, Frame Tools). It lives in one folder inside ComfyUI's `custom_nodes` folder and needs four Python packages.

## Ground rules

1. **Use the Python that runs ComfyUI, and only that one.** Installing into the system Python is the most common reason the nodes "do not show up".
2. **Never install, upgrade or remove `torch`, `torchvision`, `torchaudio`, `numpy` or `xformers`.** ComfyUI pins those. If a command would change them, stop and tell the user.
3. **Install only what is missing.** Run the checker first (step 4) and install the packages it names, not the whole requirements file blindly.
4. **Ask before you delete, disable or move anything**, including another custom node pack.
5. **Do not edit ComfyUI's own files or other packs.** Everything this pack needs is inside its own folder.
6. Say what you did and what you could not check. If a step fails, show the user the error text.

## 1. Find the ComfyUI install and its Python

Ask the user where ComfyUI is installed if you cannot find it. You need two paths: the folder that contains `custom_nodes`, and the Python executable.

| Install type | Where `custom_nodes` is | Python to use |
| --- | --- | --- |
| ComfyUI Desktop (Windows, macOS) | In the base folder the user chose at setup (the app's settings show it) | `<base folder>/.venv/Scripts/python.exe` on Windows, `<base folder>/.venv/bin/python` on macOS |
| Windows portable | `ComfyUI_windows_portable/ComfyUI/custom_nodes` | `ComfyUI_windows_portable/python_embeded/python.exe` |
| Manual install (git clone) | `ComfyUI/custom_nodes` | The venv or conda environment ComfyUI is started from |

If ComfyUI is running, its process command line shows the exact Python and the base folder. Confirm you have the right Python before going on:

```bash
"<python>" -c "import torch, sys; print(sys.executable, torch.__version__)"
```

If that fails with `No module named 'torch'`, it is the wrong Python.

## 2. Get the pack

From inside the `custom_nodes` folder:

```bash
git clone https://github.com/dughogan/DUGCO_Tools.git
```

If the folder already exists, update it instead with `git pull` inside `DUGCO_Tools`. If `git` is not available, the user can install the pack with ComfyUI Manager ("Install via Git URL") using the same address.

## 3. Check for clashing packs

These older standalone packs register the same node ids as DUGCO Tools. If any of them is in `custom_nodes`, tell the user and ask whether to remove it or disable it (renaming the folder to end in `.disabled` is enough):

- `ComfyUI-DUGco-PassViewer`
- `ComfyUI-DUGco-FilmFinish`
- `ComfyUI-DUGco-FrameTools`
- `exr_multi_pass_exporter` or `ComfyUI_exr_multi_pass_exporter`

## 4. Run the checker

```bash
"<python>" "<custom_nodes>/DUGCO_Tools/scripts/check_install.py"
```

It only reads. It prints each required package as `OK` or `MISSING`, the exact `pip` command for anything missing, and notes about clashing packs and optional extras. Add `--json` for machine-readable output. Exit code 0 means every required package is present.

## 5. Install what is missing

Run the command the checker printed. It has this shape:

```bash
"<python>" -m pip install OpenEXR Imath av
```

| Module | pip package | Needed by | Notes |
| --- | --- | --- | --- |
| `OpenEXR` | `OpenEXR` | Pass Viewer, EXR Exporter | Installs from a prebuilt wheel on common platforms. If pip starts compiling from source and fails, stop and show the user the error; do not install a compiler toolchain without asking. |
| `Imath` | `Imath` | EXR Exporter | A small pure-Python package. |
| `av` | `av` | Pass Viewer | PyAV. ComfyUI itself requires it, so it is normally already there. |
| `cv2` | `opencv-python` | Pass Viewer | **Only install if `import cv2` fails.** `opencv-python`, `opencv-contrib-python` and the `-headless` variants all provide `cv2`; adding a second one on top of an existing one can break it. |

If `pip` is not available in that environment (some ComfyUI Desktop environments are managed by `uv`), use:

```bash
uv pip install --python "<python>" OpenEXR Imath av
```

Run the checker again afterwards. Do not go on until it reports that the required packages are all present.

## 6. Optional extras

Nothing here is needed for the pack to load. Offer each one only if the user wants it.

- **The video example workflow** uses [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) to load and save clips.
- **The Pass Viewer example workflow** expects a folder of multi-layer EXR frames at `<ComfyUI>/input/vfx_passes/`. The user supplies those.

## 7. Restart and verify

ComfyUI loads custom nodes only at startup, so ask the user to restart it (or restart it yourself if you started it). Then confirm the nodes registered. With ComfyUI running (the default address is `http://127.0.0.1:8188`; ComfyUI Desktop often uses port 8000):

```bash
curl -s http://127.0.0.1:8188/object_info/DUGcoPassViewer
```

A JSON description of the node means the pack loaded. An empty object `{}` means it did not: read the ComfyUI startup log for a line that mentions `DUGCO_Tools` or `[DUGCO Tools]`.

All nine node ids, for checking: `DUGcoLoadPassEXRs`, `DUGcoPassesFromImages`, `DUGcoPassViewer`, `DUGcoPickPass`, `MultiPassEXRExporter`, `AddPass`, `DUGcoFilmFinish`, `DUGcoRepeatLatentFrames`, `DUGcoSelectEveryNthFrame`.

In the ComfyUI interface the nodes are under the **DUGco** category, and the example workflows are in the Templates browser under **DUGCO_Tools**.

## Troubleshooting

| What you see | Likely cause | What to do |
| --- | --- | --- |
| No DUGco nodes after a restart, and the log shows `IMPORT FAILED` for `DUGCO_Tools` | The pack's own `__init__.py` could not load | Read the traceback just above that line in the log. |
| Some DUGco nodes are missing, and the log has `[DUGCO Tools] Could not load nodes/<name>.py` | One tool's package is missing; the pack loads the rest | Run the checker and install what it names. `No module named 'OpenEXR'` is the usual one. |
| The checker says everything is `OK` but ComfyUI still reports a missing module | The checker ran with a different Python from the one ComfyUI uses | Go back to step 1. |
| The checker reports `torch` as `MISSING` | Wrong Python | Go back to step 1. Do not install torch. |
| `[DUGCO Tools] ... re-registers node id` in the log, or a node behaves like an old version | A standalone copy of the same tool is also installed | Step 3. |
| `cv2` errors after installing packages | Two OpenCV packages installed over each other | Tell the user. The usual fix is to uninstall all `opencv-*` packages and reinstall one, but other packs may depend on a specific one, so ask first. |
| The Pass Viewer shows "This preview is gone" | ComfyUI was restarted, which clears its temp folder | Run the workflow again. |
| The Film Finish example workflow shows missing nodes | VideoHelperSuite is not installed | Step 6. |
| pip tries to build `OpenEXR` from source and fails | No prebuilt wheel for this Python version or platform | Report the Python version and platform to the user. The other tools (Film Finish, Frame Tools) work without it. |

## Updating and removing

- **Update:** `git pull` inside `custom_nodes/DUGCO_Tools`, run the checker again, restart ComfyUI.
- **Remove:** delete the `DUGCO_Tools` folder (ask first) and restart ComfyUI. The Python packages can stay; other packs commonly use them.
