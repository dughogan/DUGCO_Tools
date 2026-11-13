# Agent instructions: get Animated Path Insert running locally

For an AI coding agent that has been asked to set up the **DUGco Animated Path Insert (MiniMax H3)** workflow on someone's ComfyUI. Work through the steps in order. Check before you change anything, install only what is missing, and report what you did at the end.

A prompt that works:

> Set up the DUGco Animated Path Insert workflow on my ComfyUI by following https://github.com/dughogan/DUGCO_Tools/blob/main/docs/animated_path_insert_agents.md

What the workflow does is described in [animated_path_insert.md](animated_path_insert.md).

## Rules for you

- The ground rules in [AGENTS.md](../AGENTS.md) all apply: use ComfyUI's own Python, never touch `torch` or `numpy`, do not edit other packs.
- **Ask the user before** downloading model files (about 44 GB in total if none are present), before installing or updating custom node packs, and before restarting ComfyUI. State sizes and sources when you ask.
- **Never overwrite** an existing file of the same name without asking. Never delete anything.
- **Do not update ComfyUI core** unless a required node is missing and the user agrees.
- If a step fails, stop and report the exact error. Do not guess a workaround that changes what the workflow does.
- **Tell the user about the licence:** the route tracker downloads CoTracker3, which is CC-BY-NC 4.0 (non-commercial use only).

## Step 1. Find the ComfyUI install

Follow step 1 of [AGENTS.md](../AGENTS.md#1-find-the-comfyui-install-and-its-python) to find the `custom_nodes` folder and the Python. For this workflow you also need:

1. The running server address (default `http://127.0.0.1:8188`; ComfyUI Desktop often uses `8000`). Confirm with `GET /system_stats`.
2. The `models` folder. Check `extra_model_paths.yaml`: models may live on another drive.
3. The `input` folder and the `user/default/workflows` folder.

**Tested on:** ComfyUI core 0.45.0, Windows 11, a 96 GB NVIDIA GPU. It has not been tested on smaller cards.

## Step 2. Install DUGCO Tools

Follow [AGENTS.md](../AGENTS.md) steps 2 to 5 (clone the pack, check for clashing packs, run the checker, install what is missing). The node this workflow needs from the pack is `DUGcoTrackPathToShot`.

An older standalone pack named `ComfyUI-DUGco-FrameTools` may already provide that node. It clashes with this pack; AGENTS.md step 3 says what to do.

## Step 3. Check the other nodes

Query `GET /object_info/<NodeName>` for each name. An empty `{}` reply means it is missing.

| Node | Comes from | If missing |
| --- | --- | --- |
| `MiniMaxH3ReferenceToVideo`, `EmptyMiniMaxH3LatentAV` | ComfyUI core | Core is too old. Ask the user about updating ComfyUI |
| `SAM3_VideoTrack`, `SAM3_TrackToMask` | ComfyUI core | Same |
| `LoadVideo`, `GetVideoComponents`, `CreateVideo`, `SaveVideo`, `ResizeImageMaskNode`, `ComfyMathExpression`, `LTXVConcatAVLatent`, `LTXVSeparateAVLatent` | ComfyUI core | Same |
| `SplineEditor`, `CreateShapeMaskOnPath`, `GrowMaskWithBlur`, `PreviewAnimation` | [kijai/ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) (tested with 1.5.0) | Install the pack |
| `MVEx_SubjectCrop`, `MVEx_SubjectUncrop`, `MVEx_MaskToLatentSpace` | [drozbay/MaskVidExperiments](https://github.com/drozbay/MaskVidExperiments) (tested at commit `6d15c77`) | Install the pack |

`SetNode` and `GetNode` (KJNodes) exist only in the browser and never appear in `/object_info`. That is normal.

To install a missing pack, use ComfyUI Manager if it is available. Otherwise `git clone` the repository into `custom_nodes` and, if the pack has a `requirements.txt`, install it with ComfyUI's Python.

## Step 4. CoTracker3 (the tracker inside Track Path To Shot)

The node loads CoTracker3 through `torch.hub` the first time it runs:

- **Code:** the `facebookresearch/co-tracker` GitHub repository, cached in `<torch hub dir>/facebookresearch_co-tracker_main`.
- **Weights:** `scaled_online.pth` (about 100 MB) from `https://huggingface.co/facebook/cotracker3/resolve/main/scaled_online.pth`, cached in `<torch hub dir>/checkpoints/`.

Find the hub folder with ComfyUI's Python: `python -c "import torch; print(torch.hub.get_dir())"`.

If both are already cached, nothing needs doing. If not, and the machine has internet access, fetch them now so the first render does not stall. Ask the user first, then run with ComfyUI's Python:

```bash
python -c "import torch; torch.hub.load('facebookresearch/co-tracker', 'cotracker3_online', trust_repo=True); print('CoTracker3 ready')"
```

On an offline machine, copy the repository folder and `scaled_online.pth` into the two cache locations above from a machine that has them.

## Step 5. Models

Check each file in the `models` folder before downloading. Sizes are the files as installed on the test machine.

| File | Folder | Size | Source |
| --- | --- | --- | --- |
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | `diffusion_models` | 21.0 GB | https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `text_encoders` | 15.7 GB | https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors |
| `minimax_h3_video_vae_fp16.safetensors` | `vae` | 5.2 GB | See the note below |
| `minimax_h3_audio_vae_fp32.safetensors` | `vae` | 0.6 GB | https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors |
| `sam3.1_multiplex_fp16.safetensors` | `checkpoints` | 1.7 GB | https://huggingface.co/Comfy-Org/sam3.1/resolve/main/checkpoints/sam3.1_multiplex_fp16.safetensors |

**Video VAE note.** The workflow was built with `minimax_h3_video_vae_fp16.safetensors`. The official ComfyUI template links `minimax_h3_video_vae_int8_convrot.safetensors` in the same repository (`https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_int8_convrot.safetensors`). The fp16 download address was not verified when this was written. Look in the `vae` folder of https://huggingface.co/Comfy-Org/MiniMax-H3 for the fp16 file. If only the int8 file is available or installed, use it and follow step 7. The int8 VAE was not tested with this workflow.

Some Hugging Face repositories need the user to be signed in and to accept terms. If a download returns 401 or 403, tell the user and let them handle the sign-in.

## Step 6. Copy the example inputs and the workflow

1. Copy `example_workflows/inputs/path_insert_plate.mp4` and `example_workflows/inputs/path_insert_spider.jpg` from the pack into ComfyUI's `input` folder.
2. The workflow is `example_workflows/DUGco Animated Path Insert - MiniMax H3.json`. Once the pack is installed it also appears in ComfyUI's Templates browser under **DUGCO_Tools**. Copy it into `user/default/workflows/` if the user wants it in their own workflow list.

## Step 7. Match file names if anything differs

If an installed model has a different file name from the table (for example the int8 video VAE), edit **the user's copy** of the workflow JSON so the loader points at what is installed: find the node whose `widgets_values` holds the old file name and replace the name. Change nothing else, and do not edit the copy inside the pack. List every substitution in your final report.

## Step 8. Restart and verify

1. Ask the user to restart ComfyUI. On ComfyUI Desktop the user has to do this.
2. After the restart, confirm `GET /object_info/DUGcoTrackPathToShot` returns the node, and re-run the step 3 checks.
3. Open the workflow in the browser. There should be no red (missing) nodes and no missing-model or missing-media warnings.

## Step 9. Test run

1. Press Run with the example inputs unchanged.
2. Within a minute or two, group 3 saves `output/path_insert/route_preview_*.mp4`: an orange dot climbs the jacket and stays on the cloth as she moves.
3. The full run saves `comp_*.mp4`, `matte_*.mp4` and 192 PNGs in `output/path_insert/element/`. On the test machine this took about 15 minutes. Compare the finished shot with `demos/animated_path_insert/demo.mp4`: results will not be pixel-identical, but the spider should climb the same route and stop on the placket between the chest pockets.

If the machine runs out of memory, lower "Crop detail (megapixels)" in group 5 from 0.9, or load a shorter shot, and say so in your report.

## Step 10. Report back

Tell the user: what was already installed, what you installed and from where, any file names you substituted, whether the test run completed, the CoTracker3 licence, and anything you could not verify.
