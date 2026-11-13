"""Pass loading, display transforms and preview encoding for the DUGco Pass Viewer.

A "pass set" (the DUGCO_PASSES type) is lazy: it holds the EXR file list and the layer map, not pixels.
The viewer streams the frames straight into one small H.264 preview per pass, so a 217-frame, ten-pass
shot never sits in memory as tensors. Only DUGco Pick Pass loads pixels, and only for the one pass asked for.
DUGco Passes From Images makes the same kind of set from IMAGE batches already in a workflow.
"""
import hashlib
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np
import torch

import comfy.utils
import folder_paths

# Viewer order, labels and the one-line note shown under the picture.
KNOWN = {
    "beauty":     ("Beauty", "The plate. HDR when it comes from an EXR: highlights go above 1.0."),
    "alpha":      ("Alpha matte", "0 = background, 1 = subject."),
    "albedo":     ("Albedo", "Base colour with the lighting taken out."),
    "normals":    ("Normals", "Camera-space surface direction, -1 to 1 per axis."),
    "depth":      ("Depth", "Relative depth, 0 to 1. Not metric."),
    "shading":    ("Shading", "Diffuse light. Albedo x shading + specular adds back up to the beauty."),
    "specular":   ("Specular", "Reflections and highlights."),
    "roughness":  ("Roughness", "0 = mirror, 1 = matte."),
    "metallic":   ("Metallic", "Material metalness, 0 to 1."),
    "cleanplate": ("Clean plate", "The plate with the subject removed."),
}
ORDER = list(KNOWN)
ALIASES = {"rgba": "beauty", "rgb": "beauty", "a": "alpha", "n": "normals", "normal": "normals",
           "z": "depth", "clean_plate": "cleanplate", "clean": "cleanplate", "spec": "specular",
           "diffuse": "shading", "rough": "roughness", "metal": "metallic", "metalness": "metallic"}
HDR_KINDS = ("beauty", "shading", "specular", "cleanplate")
HDR_VIEWS = ["Soft shoulder", "Clip at 1.0"]
IMAGE_INPUTS = ["beauty", "alpha", "albedo", "normals", "depth", "shading", "specular", "roughness",
                "metallic", "clean_plate"]


def canonical(name):
    key = name.strip().lower()
    return ALIASES.get(key, key)


def label_for(name):
    return KNOWN.get(name, (name.replace("_", " ").title(), ""))[0]


def note_for(name):
    return KNOWN.get(name, ("", "Extra layer found in the file."))[1]


def sort_passes(names):
    return sorted(names, key=lambda n: (ORDER.index(n) if n in ORDER else len(ORDER), n))


# ---------------------------------------------------------------- EXR reading

def _open(path):
    import OpenEXR
    return OpenEXR.InputFile(str(path))


def scan_layers(path):
    """Group an EXR's channels into passes: 'albedo.R/G/B' -> albedo, bare R/G/B -> beauty, A -> alpha."""
    f = _open(path)
    header = f.header()
    dw = header["dataWindow"]
    size = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1)
    groups = {}
    for ch in header["channels"]:
        if "." in ch:
            layer, comp = ch.rsplit(".", 1)
        elif ch in ("R", "G", "B"):
            layer, comp = "beauty", ch
        elif ch == "A":
            layer, comp = "alpha", ch
        else:
            layer, comp = ch, ch
        groups.setdefault(canonical(layer), {})[comp.upper()] = ch
    layers = {}
    for name, comps in groups.items():
        for want in (("R", "G", "B"), ("X", "Y", "Z")):
            if all(c in comps for c in want):
                layers[name] = [comps[c] for c in want]
                break
        else:
            layers[name] = [comps[sorted(comps)[0]]]
    f.close()
    return layers, size


def read_exr(path, layers, size):
    """One frame: {pass: float32 HxWxC} for the passes asked for."""
    import Imath
    f = _open(path)
    half = Imath.PixelType(Imath.PixelType.HALF)
    names = [c for chans in layers.values() for c in chans]
    raw = dict(zip(names, f.channels(names, half)))
    f.close()
    w, h = size
    out = {}
    for name, chans in layers.items():
        planes = [np.frombuffer(raw[c], dtype=np.float16).reshape(h, w) for c in chans]
        out[name] = np.stack(planes, -1).astype(np.float32)
    return out


def frame_number(path):
    m = re.search(r"(\d+)(?=\.[^.]+$)", Path(path).name)
    return int(m.group(1)) if m else None


def resolve_folder(folder):
    folder = folder.strip().strip('"')
    p = Path(folder)
    if p.is_absolute():
        return p
    for base in (folder_paths.get_input_directory(), folder_paths.get_output_directory()):
        if (Path(base) / folder).is_dir():
            return Path(base) / folder
    return Path(folder_paths.get_input_directory()) / folder


def find_exrs(folder):
    """The EXR frames in a folder; if the folder only holds one sub-folder of EXRs (an unzipped export), use that."""
    files = sorted(folder.glob("*.exr"))
    if not files:
        subs = [d for d in sorted(folder.iterdir()) if d.is_dir() and any(d.glob("*.exr"))] if folder.is_dir() else []
        if subs:
            files = sorted(subs[0].glob("*.exr"))
    return files


# ---------------------------------------------------------------- display transforms

def linear_to_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def soft_shoulder(x, knee=0.8):
    """Linear up to the knee so the picture matches the plate, then highlights roll off towards 1.0."""
    over = np.maximum(x - knee, 0.0)
    return np.where(x <= knee, x, knee + (1 - knee) * (1 - np.exp(-over / (1 - knee))))


def to_display(name, img, exposure=0.0, hdr_view=HDR_VIEWS[0]):
    """Scene-linear / data pass -> 0..1 sRGB picture for the viewer."""
    if name == "normals":
        return np.clip(img * 0.5 + 0.5, 0.0, 1.0)
    if img.shape[-1] == 1:                       # alpha, depth, roughness, metallic: data, shown as grey
        return np.clip(img, 0.0, 1.0)
    if name in HDR_KINDS or name not in KNOWN:
        img = np.maximum(img, 0.0) * (2.0 ** exposure)
        if hdr_view == HDR_VIEWS[0]:
            img = soft_shoulder(img)
    return linear_to_srgb(img)


# ---------------------------------------------------------------- preview encoding

class Encoder:
    """One H.264 preview. Every frame is a key frame, so stepping and switching passes land instantly."""

    def __init__(self, path, width, height, fps):
        self.container = av.open(str(path), "w")
        self.stream = self.container.add_stream("libx264", rate=Fraction(fps).limit_denominator(1001))
        self.stream.width, self.stream.height = width, height
        self.stream.pix_fmt = "yuv420p"
        self.stream.options = {"crf": "17", "preset": "veryfast", "g": "1", "movflags": "+faststart"}

    def add(self, rgb8):
        frame = av.VideoFrame.from_ndarray(rgb8, format="rgb24")
        for packet in self.stream.encode(frame):
            self.container.mux(packet)

    def close(self):
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()


def fit(img, max_height):
    h, w = img.shape[:2]
    if max_height and h > max_height:
        w, h = int(round(w * max_height / h)), max_height
    w, h = w - w % 2, h - h % 2
    if (w, h) != (img.shape[1], img.shape[0]):
        img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        if img.ndim == 2:
            img = img[..., None]
    return img


def to_rgb8(img):
    if img.shape[-1] == 1:
        img = np.repeat(img, 3, -1)
    return np.ascontiguousarray((np.clip(img[..., :3], 0, 1) * 255.0 + 0.5).astype(np.uint8))


# ---------------------------------------------------------------- nodes

class LoadPassEXRs:
    """Open a folder of multi-layer EXR frames (the VFX passes export: one EXR per frame with beauty, alpha,
    albedo, normals, depth, shading, specular, roughness, metallic, clean plate) as a pass set.
    Nothing is read into memory here: wire the pass set into DUGco Pass Viewer to look at it, or into
    DUGco Pick Pass to pull one pass out as images."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "folder": ("STRING", {"default": "vfx_passes",
                                  "tooltip": "Folder of .exr frames. A full path, or a folder inside ComfyUI's input "
                                             "(or output) folder. An unzipped export with one sub-folder works too."}),
            "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.001,
                              "tooltip": "Playback rate of the shot."}),
            "skip_first_frames": ("INT", {"default": 0, "min": 0, "max": 100000,
                                          "tooltip": "Start this many frames into the sequence."}),
            "frame_count": ("INT", {"default": 0, "min": 0, "max": 100000,
                                    "tooltip": "How many frames to use. 0 = to the end."}),
        }}

    RETURN_TYPES = ("DUGCO_PASSES", "INT", "STRING")
    RETURN_NAMES = ("passes", "frame_count", "info")
    FUNCTION = "load"
    CATEGORY = "DUGco/Passes"

    @classmethod
    def IS_CHANGED(cls, folder, **kwargs):
        files = find_exrs(resolve_folder(folder))
        return f"{len(files)}:{os.path.getmtime(files[-1]) if files else 0}"

    def load(self, folder, fps, skip_first_frames, frame_count):
        root = resolve_folder(folder)
        files = find_exrs(root)
        if not files:
            raise ValueError(f"No .exr frames found in {root}")
        files = files[skip_first_frames:]
        if frame_count:
            files = files[:frame_count]
        if not files:
            raise ValueError("skip_first_frames is past the end of the sequence.")
        layers, size = scan_layers(files[0])
        names = sort_passes(layers)
        passes = {"files": [str(f) for f in files], "layers": {n: layers[n] for n in names}, "size": size,
                  "fps": float(fps), "first_frame": frame_number(files[0])}
        first, last = frame_number(files[0]), frame_number(files[-1])
        info = (f"{len(files)} frames, {size[0]}x{size[1]}, {fps:g} fps, frames {first}-{last}\n"
                f"{len(names)} passes: " + ", ".join(label_for(n) for n in names))
        return (passes, len(files), info)


class PassViewer:
    """Look at every pass of a shot inside the node. Pick the pass from the dropdown (or step with the arrows);
    the picture stays on the same frame, so you can flip beauty / albedo / normals / depth and compare.
    Feed it a pass set: from DUGco Load VFX Pass EXRs (an EXR export), or from DUGco Passes From Images
    (passes coming straight out of a workflow)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "passes": ("DUGCO_PASSES", {"tooltip": "A pass set from DUGco Load VFX Pass EXRs or DUGco Passes From Images."}),
            "exposure": ("FLOAT", {"default": 0.0, "min": -8.0, "max": 8.0, "step": 0.25,
                                   "tooltip": "Stops, on the HDR passes of an EXR pass set (beauty, shading, specular, "
                                              "clean plate). Pull it down to see what is in the highlights."}),
            "hdr_view": (HDR_VIEWS, {"tooltip": "How values above 1.0 are shown. Soft shoulder rolls the highlights "
                                                "off; Clip at 1.0 shows what an SDR display would."}),
            "max_height": ("INT", {"default": 864, "min": 0, "max": 4320, "step": 8,
                                   "tooltip": "Previews are scaled down to this height. 0 = full size."}),
        }, "hidden": {"unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ()
    FUNCTION = "view"
    OUTPUT_NODE = True
    CATEGORY = "DUGco/Passes"

    def view(self, passes, exposure, hdr_view, max_height, unique_id=None):
        root = Path(folder_paths.get_temp_directory()) / "dugco_pass_viewer"
        fps, first_frame = passes["fps"], passes.get("first_frame")
        entries = []

        if "files" in passes:
            files = passes["files"]
            sig = "|".join([files[0], files[-1], str(len(files)), str(os.path.getmtime(files[0])),
                            str(os.path.getmtime(files[-1])), f"{exposure}", hdr_view, str(max_height),
                            f"{fps}", ",".join(passes["layers"])])
            key = hashlib.sha1(sig.encode()).hexdigest()[:16]
            folder = root / key
            names = list(passes["layers"])
            done = folder / "done.txt"
            if not done.exists():          # same shot, same settings: the previews are already there
                folder.mkdir(parents=True, exist_ok=True)
                self._encode_exrs(passes, names, folder, exposure, hdr_view, max_height)
                done.write_text("ok")
            w, h = self._preview_size(passes["size"], max_height)
            for n in names:
                entries.append(self._entry(n, f"dugco_pass_viewer/{key}", len(files), fps, w, h,
                                           first_frame, key, n in HDR_KINDS))
        else:
            images = passes["images"]
            sub = f"node_{unique_id or 0}"
            folder = root / sub
            folder.mkdir(parents=True, exist_ok=True)
            rev = str(int(time.time() * 1000))
            bar = comfy.utils.ProgressBar(sum(v.shape[0] for v in images.values()))
            for n, batch in images.items():
                first = fit(batch[0].cpu().numpy(), max_height)
                enc = Encoder(folder / f"{n}.mp4", first.shape[1], first.shape[0], fps)
                try:
                    for i in range(batch.shape[0]):
                        enc.add(to_rgb8(fit(batch[i].cpu().numpy(), max_height)))
                        bar.update(1)
                finally:
                    enc.close()
                entries.append(self._entry(n, f"dugco_pass_viewer/{sub}", batch.shape[0], fps, first.shape[1],
                                           first.shape[0], first_frame, rev, False))

        return {"ui": {"dugco_passes": entries}}

    @staticmethod
    def _preview_size(size, max_height):
        w, h = size
        if max_height and h > max_height:
            w, h = int(round(w * max_height / h)), max_height
        return w - w % 2, h - h % 2

    @staticmethod
    def _entry(name, subfolder, frames, fps, w, h, first_frame, rev, hdr):
        return {"name": name, "label": label_for(name), "note": note_for(name), "filename": f"{name}.mp4",
                "subfolder": subfolder, "type": "temp", "frames": int(frames), "fps": float(fps),
                "width": int(w), "height": int(h), "first_frame": first_frame if first_frame is not None else 1,
                "rev": rev, "hdr": bool(hdr)}

    @staticmethod
    def _encode_exrs(passes, names, folder, exposure, hdr_view, max_height):
        files, size = passes["files"], passes["size"]
        layers = {n: passes["layers"][n] for n in names}
        w, h = PassViewer._preview_size(size, max_height)
        encoders = {n: Encoder(folder / f"{n}.mp4", w, h, passes["fps"]) for n in names}
        bar = comfy.utils.ProgressBar(len(files))

        def load(path):
            frame = read_exr(path, layers, size)
            return {n: to_rgb8(fit(to_display(n, img, exposure, hdr_view), max_height)) for n, img in frame.items()}

        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                for frame in pool.map(load, files):
                    for n, rgb in frame.items():
                        encoders[n].add(rgb)
                    bar.update(1)
        finally:
            for enc in encoders.values():
                enc.close()


class PassesFromImages:
    """Bundle passes that come straight out of a workflow (Marigold albedo / normals / depth, a matte, a clean
    plate...) into a pass set for DUGco Pass Viewer. Connect only the ones you have. Images are shown as they
    are, so wire in the display-ready pictures you would send to a Save or Video Combine node."""

    @classmethod
    def INPUT_TYPES(cls):
        optional = {name: ("IMAGE", {"tooltip": f"{label_for(canonical(name))} frames."}) for name in IMAGE_INPUTS}
        return {"required": {
            "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.001, "tooltip": "Playback rate."}),
            "first_frame": ("INT", {"default": 1001, "min": 0, "max": 1000000,
                                    "tooltip": "Frame number shown for the first frame."}),
        }, "optional": optional}

    RETURN_TYPES = ("DUGCO_PASSES",)
    RETURN_NAMES = ("passes",)
    FUNCTION = "bundle"
    CATEGORY = "DUGco/Passes"

    def bundle(self, fps, first_frame, **images):
        images = {canonical(k): v for k, v in images.items() if v is not None}
        if not images:
            raise ValueError("Connect at least one pass.")
        names = sort_passes(images)
        return ({"images": {n: images[n] for n in names}, "layers": {n: [] for n in names},
                 "fps": float(fps), "first_frame": int(first_frame)},)


class PickPass:
    """Pull one pass out of a pass set as images, to wire into the rest of a workflow (a relight, a grade,
    a save). 'Display' gives the picture the viewer shows; 'Raw' gives the values in the file
    (scene-linear colour, -1..1 normals), which can go above 1.0."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "passes": ("DUGCO_PASSES",),
            "pass_name": (ORDER, {"default": "albedo", "tooltip": "Which pass to pull out."}),
            "values": (["Display", "Raw"], {"tooltip": "Display = what the viewer shows. Raw = the values in the EXR."}),
        }}

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("images", "mask")
    FUNCTION = "pick"
    CATEGORY = "DUGco/Passes"

    def pick(self, passes, pass_name, values):
        if pass_name not in passes["layers"]:
            raise ValueError(f"This pass set has no '{pass_name}'. It has: {', '.join(passes['layers'])}")
        if "images" in passes:
            images = passes["images"][pass_name]
            return (images, images[..., 0].clamp(0, 1))
        layers = {pass_name: passes["layers"][pass_name]}
        bar = comfy.utils.ProgressBar(len(passes["files"]))
        frames = []
        for path in passes["files"]:
            img = read_exr(path, layers, passes["size"])[pass_name]
            if values == "Display":
                img = to_display(pass_name, img)
            if img.shape[-1] == 1:
                img = np.repeat(img, 3, -1)
            frames.append(torch.from_numpy(np.ascontiguousarray(img, dtype=np.float32)))
            bar.update(1)
        images = torch.stack(frames)
        return (images, images[..., 0].clamp(0, 1))
