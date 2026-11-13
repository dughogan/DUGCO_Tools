"""DUGco Film Finish: make AI/digital renders read as 35mm film."""
import torch

import comfy.model_management as mm
import comfy.utils

from .film import PRESETS, finish


class FilmFinish:
    """Film finishing pass for generated video or stills. Pulls back the over-processed
    'clarity' look of AI renders, then adds a film print curve, highlight rolloff,
    tamed reds, thin halation round small highlights, lens softness, vignette,
    per-frame 35mm grain and gate weave. Put it after the VAE Decode and before
    Video Combine / Save. Grade AFTER keying or comps, never on green-screen plates."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE", {"tooltip": "Decoded frames (a video batch) or a single still."}),
            "preset": (list(PRESETS), {"default": "500T",
                                       "tooltip": "500T: tungsten high-speed stock, more grain and glow. "
                                                  "250D: daylight fine-grain stock, cleaner."}),
            "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.5, "step": 0.05,
                                   "tooltip": "Mix with the original. 1.0 = full pass."}),
            "grain": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 4.0, "step": 0.05,
                                "tooltip": "Grain amount, multiplies the preset. 0 turns it off. "
                                           "Use a high-bitrate or ProRes save, H.264 at low bitrate smears grain."}),
            "halation": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05,
                                   "tooltip": "Red-orange glow round small highlights (chrome, lamps, glints). "
                                              "Multiplies the preset."}),
            "declarity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05,
                                    "tooltip": "How much of the crunchy AI micro-contrast to pull back. Multiplies the preset."}),
            "gate_weave": ("BOOLEAN", {"default": True,
                                       "tooltip": "Sub-pixel drift of the frame, like film running through a gate. Video only."}),
            "flicker": ("FLOAT", {"default": 0.006, "min": 0.0, "max": 0.05, "step": 0.001,
                                  "tooltip": "Frame-to-frame exposure breathing in stops. 0.005-0.01 is barely visible and reads as organic."}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF,
                             "tooltip": "Grain and flicker pattern. Same seed = same grain on a re-run."}),
        }, "optional": {
            "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.001,
                              "tooltip": "Clip frame rate, keeps the weave speed right at 24/25/30 fps."}),
            "frame_offset": ("INT", {"default": 0, "min": 0, "max": 1000000,
                                     "tooltip": "First frame number of this batch, when a long clip is processed in pieces, "
                                                "so grain, weave and flicker continue instead of restarting."}),
            "chunk_size": ("INT", {"default": 8, "min": 1, "max": 256,
                                   "tooltip": "Frames processed on the GPU at once. Lower it if 4K runs out of VRAM."}),
        }}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "run"
    CATEGORY = "DUGco/Film"

    def run(self, images, preset, strength, grain, halation, declarity, gate_weave, flicker, seed,
            fps=24.0, frame_offset=0, chunk_size=8):
        p = dict(PRESETS[preset])
        p["grain"] *= grain
        p["halation"] *= halation
        p["declarity"] *= declarity
        if not gate_weave:
            p["weave"] = 0.0
        animate = images.shape[0] > 1 or frame_offset > 0
        device = mm.get_torch_device()
        out = []
        bar = comfy.utils.ProgressBar(images.shape[0])
        for i in range(0, images.shape[0], chunk_size):
            batch = images[i:i + chunk_size].to(device, torch.float32)
            res = finish(batch, p, strength, seed, frame_offset + i, fps, flicker, animate)
            out.append(res.to(mm.intermediate_device(), images.dtype))
            bar.update(batch.shape[0])
        return (torch.cat(out, 0),)


NODE_CLASS_MAPPINGS = {"DUGcoFilmFinish": FilmFinish}
NODE_DISPLAY_NAME_MAPPINGS = {"DUGcoFilmFinish": "DUGco Film Finish"}
