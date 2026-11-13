"""
ComfyUI Custom Node: Multi-Pass EXR Exporter (Chaining Version) — v2.0
Exports multiple render passes to embedded multi-channel EXR sequences
Uses "Add Pass" nodes that chain together for flexible pass assembly

v2.0 fixes (backwards compatible with v1 workflows):
- 3-channel alpha / depth / matte inputs are collapsed to ONE channel. In v1 a 3-channel
  `alpha` was written as R,G,B and silently overwrote the beauty; depth/mattes never got
  their documented `depth.Z` / `matte.alpha` names because ComfyUI IMAGEs are always 3-channel.
- `colorspace = sRGB` now converts the rgb input from sRGB to scene-linear before writing
  (EXR is a linear format). v1 only wrote a chromaticities tag, which cannot express the
  sRGB transfer curve, so sRGB-encoded pixels were read as linear by compositors.
  `linear` writes pixels unchanged (same as v1).
- MASK support: optional `alpha_mask` on the exporter, optional `mask` on Add Pass.
- `alpha` is optional (rgb-only EXRs are valid).
- Relative output paths resolve inside ComfyUI's output directory (v1: the process working dir).
- Clear errors for resolution mismatches and channel-name collisions (v1: crash or silent overwrite).
- Optional 16-bit half output.
"""

import torch
import numpy as np
import OpenEXR
import Imath
import os
from pathlib import Path

try:
    import folder_paths
except ImportError:  # running outside ComfyUI (tests)
    folder_paths = None

# Passes that are single-channel data: a 3-channel input is collapsed to its first channel.
SINGLE_CHANNEL_PREFIXES = ("alpha", "depth", "matte", "mask")
RESERVED = ("rgb", "alpha")


def _is_single_channel_name(name):
    return name.lower().startswith(SINGLE_CHANNEL_PREFIXES)


def _srgb_to_linear(x):
    """IEC 61966-2-1 sRGB EOTF. Values above 1 are extended with the same curve."""
    x = np.asarray(x, dtype=np.float32)
    return np.where(x <= 0.04045, x / 12.92, np.power(np.maximum(x + 0.055, 0) / 1.055, 2.4)).astype(np.float32)


def _frame(data, idx):
    """One frame as float32 [H, W, C] numpy from an IMAGE [B,H,W,C] or MASK [B,H,W] tensor."""
    f = data[idx]
    if isinstance(f, torch.Tensor):
        f = f.detach().cpu().float().numpy()
    f = np.asarray(f, dtype=np.float32)
    if f.ndim == 2:
        f = f[:, :, None]
    return f


class AddPass:
    """
    Add a single pass to the pass chain.
    Can be chained with other AddPass nodes.
    Connect an IMAGE to `image` or a MASK to `mask` (one of the two).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pass_name": ("STRING", {"default": "pass"}),
            },
            "optional": {
                "image": ("IMAGE",),
                "mask": ("MASK",),
                "passes": ("PASS_CHAIN",),
            }
        }

    RETURN_TYPES = ("PASS_CHAIN",)
    RETURN_NAMES = ("passes",)
    FUNCTION = "add_pass"
    CATEGORY = "DUGco/Passes"

    def add_pass(self, pass_name, image=None, mask=None, passes=None):
        """
        Add this pass to the chain.
        """
        if image is None and mask is None:
            raise ValueError(f"Add Pass '{pass_name}': connect an image or a mask.")
        if image is not None and mask is not None:
            raise ValueError(f"Add Pass '{pass_name}': connect an image OR a mask, not both.")

        # Start a new chain or append to existing
        pass_chain = {} if passes is None else passes.copy()

        clean_name = pass_name.strip() if pass_name.strip() else "unnamed_pass"
        if clean_name.lower() in RESERVED:
            raise ValueError(f"Add Pass: '{clean_name}' is reserved for the exporter's own inputs; "
                             f"choose another name (e.g. '{clean_name}_2').")
        if clean_name in pass_chain:
            raise ValueError(f"Add Pass: a pass named '{clean_name}' is already in the chain.")
        pass_chain[clean_name] = image if image is not None else mask

        return (pass_chain,)


class MultiPassEXRExporter:
    """
    Exports multiple render passes (beauty, depth, mattes, etc.) into
    multi-channel EXR image sequences with preserved channel names.
    Uses chained AddPass nodes for flexible pass assembly.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "rgb": ("IMAGE",),
                "output_name": ("STRING", {"default": "render"}),
                "output_path": ("STRING", {"default": "output",
                                           "tooltip": "Relative paths are inside ComfyUI's output folder "
                                                      "('output' = the output folder itself). Absolute paths are used as-is."}),
                "start_frame": ("INT", {"default": 1001, "min": 0, "max": 999999}),
                "colorspace": (["sRGB", "linear"], {"default": "sRGB",
                                                    "tooltip": "Encoding of the rgb INPUT. sRGB = converted to scene-linear "
                                                               "on write (EXR is linear). linear = written unchanged."}),
            },
            "optional": {
                "alpha": ("IMAGE", {"tooltip": "Matte as an IMAGE; the first channel is written to A."}),
                "alpha_mask": ("MASK", {"tooltip": "Matte as a MASK; written to A. Use alpha OR alpha_mask."}),
                "passes": ("PASS_CHAIN",),
                "bit_depth": (["32-bit float", "16-bit half"], {"default": "32-bit float"}),
                "linearize_passes": ("STRING", {"default": "",
                                                "tooltip": "Comma-separated pass names that are sRGB colour images "
                                                           "(e.g. cleanplate) to convert to linear like rgb. Data passes "
                                                           "(depth, normals, mattes) must never be converted."}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output_info",)
    FUNCTION = "export_exr"
    CATEGORY = "DUGco/Passes"
    OUTPUT_NODE = True

    @staticmethod
    def _resolve_dir(output_path):
        p = Path(output_path.strip() or "output")
        if p.is_absolute() or folder_paths is None:
            return p
        out_root = Path(folder_paths.get_output_directory())
        # v1 default was "output" relative to the ComfyUI folder: map it to the output folder itself
        if p.parts and p.parts[0].lower() == "output":
            p = Path(*p.parts[1:]) if len(p.parts) > 1 else Path()
        return out_root / p

    def export_exr(self, rgb, output_name, output_path, start_frame, colorspace, alpha=None, alpha_mask=None,
                   passes=None, bit_depth="32-bit float", linearize_passes=""):
        """
        Export multi-channel EXR sequence from render passes.
        """
        if alpha is not None and alpha_mask is not None:
            raise ValueError("Connect alpha OR alpha_mask, not both.")

        output_dir = self._resolve_dir(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Collect all passes with their names
        all_passes = {"rgb": rgb}
        a = alpha if alpha is not None else alpha_mask
        if a is not None:
            all_passes["alpha"] = a
        if passes is not None:
            for k in passes:
                if k.lower() in RESERVED:
                    raise ValueError(f"Pass name '{k}' is reserved; rename that Add Pass.")
            all_passes.update(passes)

        lin_set = {"rgb"} if colorspace == "sRGB" else set()
        lin_set |= {s.strip() for s in (linearize_passes or "").split(",") if s.strip()}
        unknown = [s for s in lin_set if s not in all_passes]
        if unknown:
            raise ValueError(f"linearize_passes names passes that are not connected: {', '.join(unknown)}")

        # Validate batch size and resolution
        batch_size = rgb.shape[0]
        h, w = rgb.shape[1], rgb.shape[2]
        for pass_name, pass_data in all_passes.items():
            if pass_data.shape[0] != batch_size:
                raise ValueError(f"Pass '{pass_name}' has different batch size: {pass_data.shape[0]} vs {batch_size}")
            if pass_data.shape[1] != h or pass_data.shape[2] != w:
                raise ValueError(f"Pass '{pass_name}' is {pass_data.shape[2]}x{pass_data.shape[1]}, "
                                 f"rgb is {w}x{h}: all passes must have the same resolution.")

        half = bit_depth.startswith("16")
        exported_files = []
        layout = None
        for frame_idx in range(batch_size):
            frame_number = start_frame + frame_idx
            output_filepath = output_dir / f"{output_name}.{frame_number:04d}.exr"
            layout = self._export_single_frame(all_passes, frame_idx, output_filepath, lin_set, half)
            exported_files.append(str(output_filepath))

        info = f"Exported {len(exported_files)} frames:\n"
        info += f"Range: {start_frame} - {start_frame + batch_size - 1}\n"
        info += f"Location: {output_dir}\n"
        info += f"Input colorspace: {colorspace} ({'converted to linear' if colorspace == 'sRGB' else 'written as-is'})\n"
        info += f"Bit depth: {bit_depth}\n"
        info += f"Channels: {', '.join(layout or [])}"

        print(info)
        return (info,)

    def _export_single_frame(self, passes, frame_idx, output_filepath, lin_set, half):
        """
        Export a single frame with all passes to an EXR file. Returns the channel names written.
        """
        first_pass = next(iter(passes.values()))
        height, width = first_pass.shape[1], first_pass.shape[2]

        header = OpenEXR.Header(width, height)
        # Rec.709 / sRGB primaries, D65 (pixels are scene-linear after conversion)
        header['chromaticities'] = Imath.Chromaticities(
            Imath.V2f(0.64, 0.33), Imath.V2f(0.30, 0.60), Imath.V2f(0.15, 0.06), Imath.V2f(0.3127, 0.3290))

        channels = {}
        channel_names = []
        owner = {}

        for pass_name, pass_data in passes.items():
            frame = _frame(pass_data, frame_idx)  # [H, W, C]
            if pass_name in lin_set:
                rgb_part = _srgb_to_linear(frame[:, :, :3])
                frame = np.concatenate([rgb_part, frame[:, :, 3:]], axis=2) if frame.shape[2] > 3 else rgb_part

            if _is_single_channel_name(pass_name) and frame.shape[2] > 1:
                frame = frame[:, :, :1]  # greyscale IMAGE carrying a matte/depth: keep one channel
            num_channels = frame.shape[2]

            if num_channels == 1:
                if pass_name == "alpha":
                    channel_suffix = ["A"]
                elif pass_name.lower().startswith("depth"):
                    channel_suffix = ["Z"]
                elif pass_name.lower().startswith(("matte", "mask")):
                    channel_suffix = ["alpha"]
                else:
                    channel_suffix = ["A"]
            elif num_channels == 3:
                channel_suffix = ["R", "G", "B"]
            elif num_channels == 4:
                channel_suffix = ["R", "G", "B", "A"]
            else:
                channel_suffix = [str(i) for i in range(num_channels)]

            for ch_idx, suffix in enumerate(channel_suffix):
                # rgb and alpha are the default layer (no prefix)
                channel_name = suffix if pass_name in RESERVED else f"{pass_name}.{suffix}"
                if channel_name in owner:
                    raise ValueError(f"Channel '{channel_name}' would be written by both '{owner[channel_name]}' "
                                     f"and '{pass_name}'. Rename one of the passes.")
                owner[channel_name] = pass_name
                channel_names.append(channel_name)
                data = np.ascontiguousarray(frame[:, :, ch_idx])
                channels[channel_name] = (data.astype(np.float16) if half else data.astype(np.float32)).tobytes()

        ptype = Imath.PixelType(Imath.PixelType.HALF if half else Imath.PixelType.FLOAT)
        header['channels'] = {name: Imath.Channel(ptype) for name in channel_names}

        exr_file = OpenEXR.OutputFile(str(output_filepath), header)
        exr_file.writePixels(channels)
        exr_file.close()

        print(f"Exported: {output_filepath}")
        return channel_names


# Node registration for ComfyUI
NODE_CLASS_MAPPINGS = {
    "MultiPassEXRExporter": MultiPassEXRExporter,
    "AddPass": AddPass,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MultiPassEXRExporter": "Multi-Pass EXR Exporter",
    "AddPass": "Add Pass",
}
