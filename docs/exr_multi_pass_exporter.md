# Multi-Pass EXR Exporter for ComfyUI

Export multiple render passes (beauty, mattes, depth, etc.) into multi-channel EXR sequences. Simple chaining system lets you add as many passes as you need.

Part of [DUGCO Tools](../README.md). Both nodes are under **DUGco / Passes** in the node menu.

---

## Quick Start

### Basic Setup (RGB + Alpha only):
1. Add "Multi-Pass EXR Exporter" node
2. Connect your RGB image to `rgb` input
3. Connect your alpha/matte to `alpha` (IMAGE) or `alpha_mask` (MASK). This is optional.
4. Set output settings (name, path, frame number)
5. Run!

### Adding More Passes:
Use "Add Pass" nodes to add depth, additional mattes, or other passes:

```
[Load RGB] → rgb input ─┐
[Load Alpha] → alpha input ─┤
                            │
[Load Depth] → [Add Pass: "depth"] ─┐
                                    │
[Load MatteB] → [Add Pass: "matteB"] ┤
                                     │
                                     └→ passes input
                                        
                        [Multi-Pass EXR Exporter]
                        - output_name: "render"
                        - output_path: "output"
                        - start_frame: 1001
```

**Chain additional passes together**, then connect the final chain to the exporter's `passes` input.

---

## The Two Nodes

### Multi-Pass EXR Exporter
Main export node with these inputs:
- `rgb` - Your RGB render (required)
- `alpha` - Your alpha/matte as an IMAGE (optional). The first channel is written to `A`.
- `alpha_mask` - Your alpha/matte as a MASK (optional). Use `alpha` OR `alpha_mask`, not both.
- `passes` - Chain of additional passes from Add Pass nodes (optional)
- `output_name` - Base filename (e.g., "render")
- `output_path` - Where to save. Relative paths go inside ComfyUI's output folder (`output` = the output folder itself); absolute paths are used as-is.
- `start_frame` - Starting frame number (default: 1001)
- `colorspace` - The encoding of the **rgb input**. `sRGB` converts it to scene-linear on write, because EXR is a linear format. `linear` writes it unchanged.
- `bit_depth` - `32-bit float` (default) or `16-bit half` (optional)
- `linearize_passes` - Comma-separated names of extra passes that are sRGB colour images (e.g. `cleanplate`) to convert like rgb (optional). Never list data passes (depth, normals, mattes).

### Add Pass
Chainable node for adding passes:
- `image` - The pass image to add, **or**
- `mask` - A MASK to add (e.g. straight from SAM)
- `pass_name` - Name for this pass (e.g., "depth", "matteB"). `rgb` and `alpha` are reserved.
- `passes` - Connect previous Add Pass here (optional)

Chain as many Add Pass nodes as you need!

---

## Output Format

**Files**: `{output_name}.{frame_number}.exr`
- Example: `render.1001.exr`, `render.1002.exr`, etc.

**Channels**: Each pass becomes channels in the EXR:
- RGB → `R`, `G`, `B` (no prefix)
- Alpha → `A` (no prefix)
- Depth → `depth.Z`
- MatteB → `matteB.alpha`
- Cleanplate → `cleanplate.R`, `cleanplate.G`, `cleanplate.B`
- Custom → `{pass_name}.{channel}`

**Smart naming**:
- Pass names starting with "matte" or "mask" → one channel, `.alpha` suffix
- Pass names starting with "depth" → one channel, `.Z` suffix
- The `alpha` input → one channel, `A`
- Everything else → `.R`, `.G`, `.B`, `.A` suffixes

ComfyUI IMAGEs are always 3-channel, so a greyscale IMAGE connected as alpha/depth/matte is collapsed to its first channel. MASK inputs are already one channel.

---

## Changelog
**v2.0**
- **Fixed: alpha overwrote the beauty.** A 3-channel `alpha` IMAGE was written as `R`,`G`,`B`. It is now collapsed to `A`.
- **Fixed: depth and mattes never got `.Z` / `.alpha`** with stock nodes. They are now collapsed to one channel.
- **Fixed: `colorspace = sRGB` didn't convert pixels.** v1 only wrote a chromaticities tag, which can't describe the sRGB curve, so Nuke read sRGB values as linear. sRGB input is now converted to linear. `linear` behaves as before.
- **Fixed: relative `output_path`** resolved against the process working directory. It now resolves inside ComfyUI's output folder.
- **New:** MASK inputs (`alpha_mask`, Add Pass `mask`), optional alpha, 16-bit half, `linearize_passes`.
- **New:** clear errors for resolution mismatches, reserved and duplicate pass names, and channel collisions.
- v1 workflows load unchanged. Behaviour changes only for v1 workflows that used `colorspace = sRGB` (now correctly converted), a 3-channel alpha (now correct), or a relative `output_path`.

---

## Features

✅ Clean chaining system - add unlimited passes  
✅ Custom pass names for each  
✅ Multi-channel EXR output  
✅ Preserved channel names  
✅ sRGB input converted to scene-linear (or linear written as-is)  
✅ IMAGE or MASK inputs, 32-bit float or 16-bit half  
✅ Batch processing for sequences  
✅ Flexible frame numbering  

---

## Troubleshooting

### "No module named 'OpenEXR'"
Install the pack's requirements with the same Python that runs ComfyUI (`pip install -r requirements.txt` from the `DUGCO_Tools` folder), then restart ComfyUI.

### "Different batch size error"
All passes must have the same number of frames. Make sure all your loaded images have matching frame counts.

### Permission errors when saving
Make sure the `output_path` directory exists and is writable. Use absolute paths if relative paths cause issues.

---

## Tips

💡 **Colorspace**: Set it to what your rgb input *is*. Most ComfyUI images are sRGB, so leave it on "sRGB" and the EXR will be linear. Use "linear" only if you linearised upstream.  
💡 **Frame padding**: Uses 4-digit padding automatically (1001, 1002, etc.)  
💡 **Pass naming**: Name passes clearly - they become your EXR channel prefixes  
💡 **Batch processing**: Load multiple frames and they'll export as a sequence  
💡 **Resolution**: All passes must have identical dimensions  

---

## Example Workflow

Full example with 5 passes:

```
[Load RGB] → rgb input ─┐
[Load Alpha] → alpha input ─┤
                            │
                            │
[Load Depth] → [Add Pass: "depth"] ─┐
                                    │
[Load MatteB] → [Add Pass: "matteB"] ┤
                                     │
[Load Cleanplate] → [Add Pass: "cleanplate"] ┤
                                              │
                                              └→ passes input
                                                 
                        [Multi-Pass EXR Exporter]
                        - output_name: "shot_010"  
                        - output_path: "renders"
                        - start_frame: 1001
                        - colorspace: "sRGB"
                        
                        Output ↓
                        renders/shot_010.1001.exr
                        renders/shot_010.1002.exr
                        ...
```

Each EXR contains:
- `R`, `G`, `B` (from rgb input)
- `A` (from alpha input)
- `depth.Z` (from Add Pass)
- `matteB.alpha` (from Add Pass)
- `cleanplate.R`, `cleanplate.G`, `cleanplate.B` (from Add Pass)
