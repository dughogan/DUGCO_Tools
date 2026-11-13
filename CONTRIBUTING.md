# Adding a tool to DUGCO Tools

The checklist for publishing a ComfyUI custom node into this pack. It is written so that a person or an AI coding agent can follow it from top to bottom. The pack is public and MIT licensed, so step 1 matters most.

## 1. Decide whether it can be published

Stop and ask the maintainer if any of these is in doubt.

- **It is the maintainer's own work.** No client-provided code, no code copied from another project unless its licence allows redistribution under MIT, and then the licence and credit travel with it.
- **Its dependencies can be used by anyone.** Check the licence of every model and library it downloads or imports. A non-commercial model licence is a reason to stop and ask.
- **Nothing private is in it.** No client, show, shot or project names; no personal paths (`C:\...`, `D:\...`, network shares); no API keys; no references to internal tools or scripts. Check the code, the comments, the tooltips, the README text and every example workflow, including the notes and group titles inside the workflow JSON.
- **It is finished.** It has been run in a real ComfyUI, not only imported.

## 2. Put the files in place

| What | Where |
| --- | --- |
| Node code, one tool | `nodes/<tool_name>.py`, or `nodes/<tool_name>/__init__.py` plus helper files for a bigger tool |
| Front-end code | `web/js/<tool_name>.js` (the pack's `WEB_DIRECTORY` is `web/js`) |
| Example workflows | `example_workflows/<Name>.json`, with a same-named `.jpg` or `.webp` thumbnail |
| The guide | `docs/<tool_name>.md` |
| The README image | `docs/images/<tool_name>.jpg`, 1600 x 900 |
| Demo clip | `demos/<tool_name>/demo.mp4` and `thumbnail.jpg` (see `demos/README.md` for size limits) |

Everything in `nodes/` loads automatically: the file or folder only has to define `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`. Start from `nodes/_template.py`. Names that begin with an underscore are skipped.

## 3. Follow the pack's conventions

- **Node ids** start with `DUGco` (for example `DUGcoFilmFinish`). **Never rename an id that has been published**: every saved workflow that uses it would break. A tool that moves in from a standalone pack keeps the ids it already had.
- **Display names** start with `DUGco`. **Category** is `DUGco/<Group>`; reuse an existing group (`Passes`, `Film`, `Frames`) where one fits.
- **Every input has a tooltip** that says what it does in plain words.
- **No installs at import time.** Do not call `pip` or download anything when the module loads. Python packages go in `requirements.txt`; models are downloaded by the user or by the node that owns them.
- **No fixed paths.** Find ComfyUI folders through `folder_paths` (`get_input_directory()`, `get_output_directory()`, `get_temp_directory()`, `models_dir`, `get_folder_paths("custom_nodes")`).
- **A missing optional dependency must not break the pack.** The loader already isolates each file, so one failing tool does not stop the others; keep heavy or unusual imports inside the tool that needs them.
- **Be kind to memory.** Process long clips in chunks, move results off the GPU, and show a `comfy.utils.ProgressBar` for anything slow.

## 4. Update the requirements

If the tool needs a Python package that ComfyUI does not already ship:

1. Add it to `requirements.txt` **and** to `dependencies` in `pyproject.toml`.
2. Add it to the `REQUIRED` list in `scripts/check_install.py`, with the tool that needs it.
3. Add a row for it to the package table in `AGENTS.md`.

Never add `torch`, `numpy` or anything else ComfyUI pins.

## 5. Write the example workflow

- Use placeholder inputs (`your_clip.mp4`, a folder inside `input/`), never a real path.
- Keep it small: load, the tool, save or preview.
- Put a note in the workflow saying what it needs and how to run it.
- Open the saved JSON as text and search it for names and paths before committing.

## 6. Write the docs

- **`docs/<tool_name>.md`:** what the tool is for, where it goes in a graph, a table of its inputs, what it needs, and its limits. Say plainly what it does badly.
- **`README.md`:** add a row to "The tools" table, a section with the image, three or four bullets, the node names and links, and a row in "What each tool needs". Update the node count if the README states one.
- **`AGENTS.md`:** add the new node ids to the list in step 7, and any new optional extra to step 6.
- **`scripts/check_install.py`:** if the tool replaces a standalone pack, add that pack's folder name to `DUPLICATES`, and to the list in `AGENTS.md` step 3 and the note in the README's install section.

## 7. Test

Add the new node ids to `EXPECTED` in `tests/smoke_test.py`, and add a check that actually runs the node on small made-up data if it needs no model. Then run the test with ComfyUI's own Python:

```bash
set COMFYUI_PATH=C:\path\to\ComfyUI
python tests/smoke_test.py
```

(`COMFYUI_PATH` is the folder that holds ComfyUI's `folder_paths.py`. Use `export` on macOS and Linux.)

Then load the pack in a real ComfyUI and run the example workflow from start to finish. If the main ComfyUI still has a standalone copy of the tool, test in a separate ComfyUI started with its own base folder so the two do not clash. Say in your report what you ran and what you could not run.

## 8. Version, commit, push

1. Bump `version` in `pyproject.toml` (a new tool is a minor bump: `0.3.0` to `0.4.0`).
2. Run `git status` and read the list. Commit only the files for this tool; large or unreviewed media stays out.
3. Write a commit message that says what was added and anything that changed in behaviour.
4. **Do not push until the maintainer says so.** The repository is public: a push publishes the code, the workflows and every image in them.

## Giving this job to an agent

A prompt that works:

> Add my custom node `<folder or file>` to the DUGCO_Tools pack at `<path to this repository>`. Follow CONTRIBUTING.md in that repository exactly, including step 1. Keep the existing node ids. Test it in a separate ComfyUI, commit locally, and do not push. Tell me what you changed, what you tested, and anything in step 1 you were not sure about.
