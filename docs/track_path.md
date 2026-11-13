# DUGco Track Path To Shot

One node under **DUGco / Tracking**. You draw a route on the first frame of a shot, and the node makes that route follow the surface it was drawn on for every frame.

It was built for the classic "insert creature here" shot: a spider that has to climb a jacket while the actor moves. A mask animated in screen space slides off the cloth as soon as she leans. This node keeps it on the cloth.

> **Licence.** The node's code is MIT like the rest of the pack. The tracker it uses, [CoTracker3](https://github.com/facebookresearch/co-tracker), is downloaded the first time the node runs and is licensed **CC-BY-NC 4.0: non-commercial use only**. With `track` switched off the node needs no model.

## Where it goes in a graph

```
Load Video ─ frames ─────────────────────────┐
                                              ▼
Spline Editor (KJNodes) ─ coord_str ─▶ DUGco Track Path To Shot ─ coordinates ─▶ Create Shape Mask On Path (KJNodes) ─▶ mask
              └────────── mask ─────▶ path_canvas
```

- The **Spline Editor** is where the artist draws. Wire frame 1 of the shot into its `bg_image` so the frame shows in the editor (it appears after the node has run once). Set its `sampling_method` to `path`.
- **Create Shape Mask On Path** turns the tracked coordinates into a travelling mask, one frame per coordinate.
- The `preview` output is the shot with the tracked point and its trail drawn on. Check it before you render anything expensive.

## How it works

1. The route is resampled so there is one position per frame between `start_frame` and `end_frame`.
2. A number of **anchor** points along the route are placed on frame 1.
3. CoTracker3 follows every anchor through the whole shot.
4. At frame *t* the travelling point is a certain fraction of the way along the route. Its position is read from the anchors either side of that fraction, at frame *t*.

So the route itself moves, stretches and folds with the surface, and the point walks along it.

## Inputs

| Input | What it does |
| --- | --- |
| `images` | The shot. The route is drawn on its first frame. |
| `coordinates` | `coord_str` from a KJNodes Spline Editor. |
| `path_canvas` | Optional. The Spline Editor's `mask` output. Its size tells the node what canvas the route was drawn on, so the route lands correctly at any shot resolution. |
| `path_width`, `path_height` | The canvas size, if `path_canvas` is not connected. 0 = same as the shot. |
| `start_frame` | Frame where the move begins. Before it, the point waits at the start of the route, still tracked. |
| `end_frame` | Frame where the move ends. 0 = the last frame. After it, the point waits at the end of the route, still tracked. |
| `track` | Off = the route stays where it was drawn. Use it for a locked-off shot, or to compare. |
| `anchors` | How many points along the route are tracked (default 32). More follows cloth folds more closely. |
| `smooth` | Temporal smoothing of the result, in frames, to take out tracker jitter. |
| `track_size` | The shot is scaled so its long edge is this size, for tracking only. |

## Outputs

| Output | What it is |
| --- | --- |
| `coordinates` | One `{x, y}` per frame, in shot pixels, in the format KJNodes path nodes read. |
| `preview` | The shot with the travelled trail and the current point drawn on. |
| `frames` | The number of frames. |

## What it needs

- [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) for the Spline Editor and Create Shape Mask On Path.
- `opencv-python` (already in this pack's requirements).
- Internet access the first time it runs, to fetch CoTracker3 through `torch.hub` (the code from GitHub and about 100 MB of weights from Hugging Face). After that it works offline.

## Limits

- **Non-commercial tracker.** See the licence note above. If you need this on paid work, the tracker has to be replaced with one whose licence allows it; the rest of the node does not care which tracker produced the anchor tracks.
- **The surface has to be visible on frame 1**, because that is where the route is drawn. A surface that only comes into view later cannot be tracked this way.
- **Occlusion.** If something passes in front of the route, the tracker keeps guessing. Check the preview.
- **Flat, featureless or motion-blurred cloth** gives the tracker little to hold. Draw the route over seams, pockets and folds where you can.
- **One route.** If the Spline Editor holds several splines, the first is used.
- Tested on one shot at 1344 x 768, 192 frames, where tracking took well under a minute on an RTX PRO 6000. Longer or larger shots have not been measured.
