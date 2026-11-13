# DUGco Film Finish

One ComfyUI node, **DUGco Film Finish** (`DUGco/Film`), that makes AI/digital renders read as if they were shot on 35mm film. Put it after VAE Decode (or a Load Video) and before Video Combine / Save Image.

```
VAE Decode / Load Video  ->  DUGco Film Finish  ->  Video Combine (ProRes or high-bitrate H.264)
```

## What it does

| Step | Why |
|---|---|
| De-clarity (edge-aware) | pulls back the crunchy mid-frequency micro-contrast of AI renders without haloing silhouettes |
| Film curve | log contrast round 18% grey, soft highlight shoulder, lifted print black |
| Colour | highlight desaturation, tamed hot reds, warm highs / cool shadows |
| Halation | thin red-orange glow round *small* highlights only (chrome, lamps, glints) |
| Lens | slight softening and vignette |
| Exposure flicker | tiny smoothed frame-to-frame breathing (video only) |
| Grain | luma-weighted, per-dye-layer grain, a fresh pattern every frame |
| Gate weave | sub-pixel drift of the frame (video only) |

Presets: **500T** (tungsten, more grain and glow) and **250D** (daylight, fine grain). `grain`, `halation` and `declarity` multiply the preset.

## Tips

- **Encode for grain.** Low-bitrate H.264 smears grain into mush. Save ProRes, or H.264 at CRF 12-14.
- **Grade after keying.** Never run it on green-screen plates; run it on the comp.
- **Long clips in pieces:** set `frame_offset` to the first frame of each piece so grain, weave and flicker continue instead of restarting.
- Same `seed` gives the same grain on a re-run.

Example workflow: [DUGco Film Finish - video](../example_workflows/DUGco%20Film%20Finish%20-%20video.json) (needs Video Helper Suite for the load and save nodes).
