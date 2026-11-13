"""DUGco Track Path To Shot.

Licence note: this file is MIT like the rest of the pack, but the tracker it downloads at run time
(CoTracker3, facebookresearch/co-tracker) is CC-BY-NC 4.0, so tracking is for non-commercial use only.
Turn `track` off and the node needs no model.

Draw a motion path on the first frame of a shot (KJNodes Spline Editor) and this node
sticks it to whatever surface it was drawn on, for every frame.

How: the path is sampled into anchor points on frame 0. CoTracker3 follows every anchor
through the whole shot. At frame t the travelling point sits a fraction t/(T-1) along
the path, so its position is read from the anchors on either side of that fraction,
at frame t. The result is a path that moves, stretches and folds with the surface.
"""
import json
import os

import numpy as np
import torch
import torch.nn.functional as F

import comfy.model_management as mm

_MODEL = {}


def _load_tracker(device):
    if "m" not in _MODEL:
        local = os.path.join(torch.hub.get_dir(), "facebookresearch_co-tracker_main")
        if os.path.isdir(local):
            m = torch.hub.load(local, "cotracker3_online", source="local")
        else:
            m = torch.hub.load("facebookresearch/co-tracker", "cotracker3_online", trust_repo=True)
        _MODEL["m"] = m.eval()
    return _MODEL["m"].to(device)


def _parse(coordinates):
    data = json.loads(coordinates.replace("'", '"'))
    if data and isinstance(data[0], list):  # several splines: use the first
        data = data[0]
    return np.array([[float(p["x"]), float(p["y"])] for p in data], dtype=np.float32)


def _resample(points, n):
    """n points spread along the list by index, keeping the editor's own timing (ease in/out)."""
    if len(points) == n:
        return points
    src = np.linspace(0, 1, len(points))
    dst = np.linspace(0, 1, n)
    return np.stack([np.interp(dst, src, points[:, 0]), np.interp(dst, src, points[:, 1])], 1).astype(np.float32)


def _smooth(path, radius):
    if radius <= 0 or len(path) < 3:
        return path
    k = np.arange(-radius, radius + 1)
    w = np.exp(-(k ** 2) / (2 * (radius / 2 + 1e-6) ** 2))
    w /= w.sum()
    pad = np.pad(path, ((radius, radius), (0, 0)), mode="edge")
    return np.stack([np.convolve(pad[:, i], w, mode="valid") for i in range(2)], 1).astype(np.float32)


class DUGcoTrackPathToShot:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The shot. The path is drawn on its first frame."}),
                "coordinates": ("STRING", {"forceInput": True, "tooltip": "coord_str from a KJNodes Spline Editor, drawn over frame 1 of the shot."}),
                "path_width": ("INT", {"default": 0, "min": 0, "max": 16384, "tooltip": "Width of the canvas the path was drawn on (the Spline Editor's mask_width). 0 = same as the shot."}),
                "path_height": ("INT", {"default": 0, "min": 0, "max": 16384, "tooltip": "Height of the canvas the path was drawn on. 0 = same as the shot."}),
                "start_frame": ("INT", {"default": 0, "min": 0, "max": 100000, "tooltip": "Frame where the move begins. Before it, the point waits at the start of the path (still tracked)."}),
                "end_frame": ("INT", {"default": 0, "min": 0, "max": 100000, "tooltip": "Frame where the move ends. 0 = the last frame. After it, the point waits at the end of the path (still tracked)."}),
                "track": ("BOOLEAN", {"default": True, "tooltip": "On = the path is tracked onto the surface with CoTracker3, which is licensed CC-BY-NC 4.0: non-commercial use only. Off = the path stays where it was drawn (screen space), for a locked-off shot or to compare, and no model is used."}),
                "anchors": ("INT", {"default": 32, "min": 2, "max": 256, "tooltip": "How many points along the path are tracked. More follows cloth folds more closely."}),
                "smooth": ("INT", {"default": 2, "min": 0, "max": 24, "tooltip": "Temporal smoothing of the result, in frames, to take out tracker jitter."}),
                "track_size": ("INT", {"default": 768, "min": 256, "max": 2048, "step": 32, "tooltip": "The shot is scaled so its long edge is this size for tracking only."}),
            },
            "optional": {
                "path_canvas": ("MASK", {"tooltip": "The Spline Editor's mask output. Its size tells this node what canvas the path was drawn on, so the path lands in the right place at any shot resolution."}),
            },
        }

    RETURN_TYPES = ("STRING", "IMAGE", "INT")
    RETURN_NAMES = ("coordinates", "preview", "frames")
    FUNCTION = "run"
    CATEGORY = "DUGco/Tracking"
    DESCRIPTION = ("Sticks a path drawn on frame 1 (KJNodes Spline Editor) to the surface it was drawn on. Feed the result to "
                   "Create Shape Mask On Path. The tracker is CoTracker3, downloaded through torch.hub the first time the node runs "
                   "(about 100 MB). CoTracker3 is licensed CC-BY-NC 4.0: non-commercial use only.")

    def run(self, images, coordinates, path_width, path_height, start_frame, end_frame, track, anchors, smooth, track_size, path_canvas=None):
        T, H, W, _ = images.shape
        pts = _parse(coordinates)
        if path_canvas is not None:
            path_height, path_width = int(path_canvas.shape[-2]), int(path_canvas.shape[-1])
        if path_width and path_height:
            pts = pts * np.array([W / path_width, H / path_height], dtype=np.float32)
        end = (T - 1) if end_frame <= 0 else min(end_frame, T - 1)
        start = min(start_frame, end)
        # fraction along the path for every frame, keeping the editor's timing between start and end
        timed = _resample(pts, max(end - start + 1, 2))
        M = len(timed)

        if not track:
            out = np.concatenate([np.repeat(timed[:1], start, 0), timed, np.repeat(timed[-1:], max(T - 1 - end, 0), 0)], 0)[:T]
        else:
            # anchors are taken from the timed samples, so "how far along" is just an index
            K = max(2, min(anchors, M))
            anchor_pts = timed[np.linspace(0, M - 1, K).round().astype(int)]
            j = np.clip(np.arange(T) - start, 0, M - 1).astype(np.float32)
            frame_pos = j * (K - 1) / max(M - 1, 1)  # position of every frame on the anchor chain

            device = mm.get_torch_device()
            scale = min(1.0, track_size / max(H, W))
            video = images.permute(0, 3, 1, 2)
            if scale < 1.0:
                video = F.interpolate(video, size=(int(round(H * scale / 8)) * 8, int(round(W * scale / 8)) * 8), mode="bilinear", antialias=True)
            sy, sx = video.shape[2] / H, video.shape[3] / W
            video = (video * 255.0)[None].float().to(device)
            q = torch.tensor([[0.0, x * sx, y * sy] for x, y in anchor_pts], dtype=torch.float32, device=device)[None]
            model = _load_tracker(device)
            with torch.no_grad():  # online CoTracker3: prime, then slide over the shot in overlapping windows
                model(video_chunk=video, is_first_step=True, grid_size=0, queries=q, add_support_grid=True)
                tracks = None
                for ind in range(0, max(video.shape[1] - model.step, 1), model.step):
                    tracks, _vis = model(video_chunk=video[:, ind: ind + model.step * 2], is_first_step=False, grid_size=0, queries=q, add_support_grid=True)
            tracks = tracks[0, :, :K].float().cpu().numpy() / np.array([sx, sy], dtype=np.float32)  # T, K, 2
            model.to("cpu")
            del video
            mm.soft_empty_cache()

            idx = np.arange(K, dtype=np.float32)
            out = np.zeros((T, 2), dtype=np.float32)
            for t in range(T):
                out[t, 0] = np.interp(frame_pos[t], idx, tracks[t, :, 0])
                out[t, 1] = np.interp(frame_pos[t], idx, tracks[t, :, 1])
            out = _smooth(out, smooth)

        coords = json.dumps([{"x": float(round(x, 2)), "y": float(round(y, 2))} for x, y in out])

        # preview: the shot with the travelled trail and the current point
        import cv2
        frames = (images.cpu().numpy() * 255).astype(np.uint8)
        prev = []
        r = max(3, int(round(min(H, W) * 0.008)))
        for t in range(T):
            f = np.ascontiguousarray(frames[t][..., :3])
            if t > 0:
                cv2.polylines(f, [out[: t + 1].round().astype(np.int32).reshape(-1, 1, 2)], False, (255, 120, 0), max(1, r // 3), cv2.LINE_AA)
            cv2.circle(f, (int(round(out[t, 0])), int(round(out[t, 1]))), r, (255, 60, 0), -1, cv2.LINE_AA)
            cv2.circle(f, (int(round(out[t, 0])), int(round(out[t, 1]))), r, (255, 255, 255), 1, cv2.LINE_AA)
            prev.append(f)
        preview = torch.from_numpy(np.stack(prev)).float() / 255.0
        return (coords, preview, T)


NODE_CLASS_MAPPINGS = {"DUGcoTrackPathToShot": DUGcoTrackPathToShot}
NODE_DISPLAY_NAME_MAPPINGS = {"DUGcoTrackPathToShot": "DUGco Track Path To Shot"}
