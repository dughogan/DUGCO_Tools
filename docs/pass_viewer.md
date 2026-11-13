# DUGco Pass Viewer

Step through the VFX passes of a shot inside one node: beauty, alpha, albedo, normals, depth, shading,
specular, roughness, metallic, clean plate.

| Node | What it does |
| --- | --- |
| **DUGco Load VFX Pass EXRs** | Opens a folder of multi-layer EXR frames (one EXR per frame) as a pass set. Reads nothing into memory. |
| **DUGco Passes From Images** | Bundles IMAGE batches already in a workflow (Marigold albedo / normals / depth, a matte...) into a pass set. |
| **DUGco Pass Viewer** | The viewer. Pass dropdown, up / down pass buttons, play, frame step, scrub bar. Switching pass keeps the frame. |
| **DUGco Pick Pass** | Pulls one pass out of a pass set as IMAGE + MASK. |

Keys (click the viewer first): Up / Down = pass, Left / Right = frame, Space = play.

How it shows each pass: HDR colour passes (beauty, shading, specular, clean plate) get `exposure`, then a soft
shoulder above 0.8 (or a clip at 1.0), then sRGB. Albedo is linear to sRGB. Normals are remapped from -1..1 to 0..1.
Alpha, depth, roughness and metallic are shown as grey. Image inputs are shown as they are.

The viewer writes one small all-key-frame H.264 preview per pass into ComfyUI's temp folder
(`dugco_pass_viewer/`). An EXR shot is encoded once per setting; running again is instant until ComfyUI restarts.

Example workflow: [DUGco Pass Viewer - VFX Passes](../example_workflows/DUGco%20Pass%20Viewer%20-%20VFX%20Passes.json) (expects the EXR frames in
`input/vfx_passes/`). Needs `OpenEXR`, `av` and `opencv-python`, which ComfyUI Desktop already has.
