"""DUGco Frame Tools: repeat latent frames along time, and keep every Nth image of a batch."""
import torch


class DUGcoRepeatLatentFrames:
    """Repeat every latent frame N times along time (B, C, T, H, W) before the VAE decode.
    A decode-side smear test: it shows how a video VAE blends neighbouring latent frames."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "samples": ("LATENT", {"tooltip": "A video latent (5 dimensions). Image latents pass through unchanged."}),
            "times": ("INT", {"default": 2, "min": 1, "max": 8,
                              "tooltip": "How many times each latent frame is repeated. 1 = no change."}),
            "keep_first": ("BOOLEAN", {"default": True, "tooltip": "Leave the causal first latent frame single."}),
            "latent_frames": ("INT", {"default": 0, "min": 0, "max": 4096,
                                      "tooltip": "Only use the first N latent frames (0 = all), to keep big decodes in memory."}),
        }}

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "run"
    CATEGORY = "DUGco/Frames"

    def run(self, samples, times, keep_first, latent_frames=0):
        s = samples["samples"]
        if latent_frames and s.ndim == 5:
            s = s[:, :, :latent_frames]
        result = dict(samples)
        result.pop("noise_mask", None)          # the mask no longer matches the new frame count
        if times == 1 or s.ndim != 5:
            result["samples"] = s
        elif keep_first:
            result["samples"] = torch.cat([s[:, :, :1], s[:, :, 1:].repeat_interleave(times, dim=2)], dim=2)
        else:
            result["samples"] = s.repeat_interleave(times, dim=2)
        return (result,)


class DUGcoSelectEveryNthFrame:
    """Keep every Nth image of a batch, starting at offset, capped at max_frames (0 = no cap)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE",),
            "n": ("INT", {"default": 2, "min": 1, "max": 64, "tooltip": "Keep one frame in every N."}),
            "offset": ("INT", {"default": 0, "min": 0, "max": 64, "tooltip": "The first frame to keep."}),
            "max_frames": ("INT", {"default": 0, "min": 0, "max": 100000,
                                   "tooltip": "Stop after this many kept frames. 0 = no cap."}),
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "DUGco/Frames"

    def run(self, images, n, offset, max_frames):
        out = images[offset::n]
        if max_frames:
            out = out[:max_frames]
        return (out,)


NODE_CLASS_MAPPINGS = {
    "DUGcoRepeatLatentFrames": DUGcoRepeatLatentFrames,
    "DUGcoSelectEveryNthFrame": DUGcoSelectEveryNthFrame,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DUGcoRepeatLatentFrames": "DUGco Repeat Latent Frames",
    "DUGcoSelectEveryNthFrame": "DUGco Select Every Nth Frame",
}
