"""DUGco film finishing pass, on the GPU with torch.

All maths works on (B, H, W, C) float tensors in 0..1 sRGB, the way ComfyUI
passes IMAGE batches. Every spatial size is scaled to image width / 2048 so a
720p clip and a 4K plate get the same look.
"""
import math

import torch
import torch.nn.functional as F

PRESETS = {
    # tungsten-balanced high speed stock: more grain, more halation
    "500T": dict(declarity=0.40, contrast=1.06, exposure=0.20, shoulder=0.80,
                 toe_black=0.012, hi_desat=0.35, sat=0.97, red_tame=0.85,
                 warm=0.03, cool=0.02, halation=0.35, hal_thresh=0.88,
                 soften=0.45, vignette=0.14, grain=0.016, grain_size=0.75,
                 weave=0.35),
    # daylight fine-grain stock: cleaner, less glow
    "250D": dict(declarity=0.35, contrast=1.04, exposure=0.16, shoulder=0.82,
                 toe_black=0.010, hi_desat=0.30, sat=0.98, red_tame=0.88,
                 warm=0.025, cool=0.015, halation=0.22, hal_thresh=0.90,
                 soften=0.35, vignette=0.12, grain=0.011, grain_size=0.65,
                 weave=0.25),
}

LUMA = (0.2126, 0.7152, 0.0722)


def srgb_to_lin(x):
    return torch.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(x):
    x = x.clamp(0, 1)
    return torch.where(x <= 0.0031308, x * 12.92, 1.055 * x.clamp_min(1e-12) ** (1 / 2.4) - 0.055)


def luma(x):
    return x[..., 0] * LUMA[0] + x[..., 1] * LUMA[1] + x[..., 2] * LUMA[2]


def _to_nchw(x):
    return x.unsqueeze(1) if x.dim() == 3 else x.permute(0, 3, 1, 2)


def _from_nchw(x, like):
    return x.squeeze(1) if like.dim() == 3 else x.permute(0, 2, 3, 1)


def blur(x, sigma):
    """Separable gaussian with reflect borders. x is (B,H,W) or (B,H,W,C)."""
    if sigma <= 0.05:
        return x
    r = max(1, int(math.ceil(3 * sigma)))
    t = torch.arange(-r, r + 1, device=x.device, dtype=x.dtype)
    k = torch.exp(-(t * t) / (2 * sigma * sigma))
    k = k / k.sum()
    y = _to_nchw(x)
    c = y.shape[1]
    h, w = y.shape[-2:]
    # reflect padding cannot exceed the dimension, fall back to replicate
    mode = "reflect" if r < min(h, w) else "replicate"
    y = F.pad(y, (r, r, 0, 0), mode=mode)
    y = F.conv2d(y, k.view(1, 1, 1, -1).repeat(c, 1, 1, 1), groups=c)
    y = F.pad(y, (0, 0, r, r), mode=mode)
    y = F.conv2d(y, k.view(1, 1, -1, 1).repeat(c, 1, 1, 1), groups=c)
    return _from_nchw(y, x)


def box(x, r):
    y = _to_nchw(x)
    h, w = y.shape[-2:]
    mode = "reflect" if r < min(h, w) else "replicate"
    y = F.pad(y, (r, r, r, r), mode=mode)
    y = F.avg_pool2d(y, 2 * r + 1, stride=1)
    return _from_nchw(y, x)


def guided(x, r, eps):
    """Self-guided filter: smooths texture but keeps strong edges, so
    de-clarity does not halo around silhouettes."""
    r = max(1, int(r))
    m = box(x, r)
    var = box(x * x, r) - m * m
    a = var / (var + eps)
    b = m - a * m
    return box(a, r) * x + box(b, r)


def declarity(lin, amount, s):
    """Shrink the mid-frequency band in log luminance (where clarity/local
    tone-mapping lives) while leaving fine texture and global shape alone."""
    if amount <= 0:
        return lin
    ly = torch.log2(luma(lin).clamp_min(1e-5))
    mid_band = blur(ly, 1.5 * s) - guided(ly, 40 * s, 0.35)
    return lin * torch.exp2(-amount * mid_band).unsqueeze(-1)


def film_curve(lin, p):
    """Log-domain contrast around 18% grey, then a soft shoulder and a toe
    with a slightly lifted print black."""
    x = lin * (2 ** p["exposure"])
    lx = torch.log2(x.clamp_min(1e-6) / 0.18)
    x = 0.18 * torch.exp2(lx * p["contrast"])
    k = p["shoulder"]
    over = (x - k).clamp_min(0)
    x = torch.where(x > k, k + (1 - k) * (1 - torch.exp(-over / (1 - k))), x)
    b = p["toe_black"]
    return b + (1 - b) * x


def colour(lin, p):
    y = luma(lin).unsqueeze(-1)
    # global saturation, then extra desat as values climb (print rolloff)
    hi = ((y - 0.35) / 0.65).clamp(0, 1) ** 1.5
    out = y + (lin - y) * (p["sat"] * (1 - p["hi_desat"] * hi))
    # tame hot reds: pull pixels where R dominates back toward luma
    r, g, b = out[..., 0], out[..., 1], out[..., 2]
    redness = ((r - torch.maximum(g, b)) / (r + 1e-4)).clamp(0, 1)
    out = y + (out - y) * (1 - (1 - p["red_tame"]) * redness).unsqueeze(-1)
    # split tone: warm highlights, cool/green-cyan shadows
    warm = out.new_tensor([1.0, 0.35, -0.6])
    cool = out.new_tensor([-0.5, 0.15, 0.6])
    out = out + p["warm"] * (y * 1.6).clamp(0, 1) * warm * y
    out = out + p["cool"] * (1 - (y / 0.25).clamp(0, 1)) * cool * 0.1
    return out.clamp_min(0)


def halation(lin, p, s):
    if p["halation"] <= 0:
        return lin
    y = luma(lin)
    mask = ((y - p["hal_thresh"]) / (1.0 - p["hal_thresh"] + 1e-4)).clamp(0, 1)
    # small highlights only (chrome, globes, glints): big bright areas like
    # sky would otherwise haze over every silhouette edge
    mask = (mask - blur(mask, 25 * s)).clamp(0, 1)
    src = luma(lin) * mask
    glow = 0.7 * blur(src, 3 * s) + 0.3 * blur(src, 9 * s)
    spill = glow * (1 - mask)  # thin edge outside the highlight only
    tint = lin.new_tensor([1.0, 0.30, 0.08])
    return lin + p["halation"] * spill.unsqueeze(-1) * tint


def lens(lin, p, s):
    out = blur(lin, p["soften"] * s)
    if p["vignette"] <= 0:
        return out
    h, w = lin.shape[1:3]
    yy = torch.linspace(-1, 1, h, device=lin.device, dtype=lin.dtype).view(h, 1)
    xx = torch.linspace(-1, 1, w, device=lin.device, dtype=lin.dtype).view(1, w)
    r2 = xx ** 2 + (yy * h / w) ** 2
    vig = 1 - p["vignette"] * r2.clamp(0, 1.6) ** 1.4 / 1.6 ** 1.4
    return out * vig.view(1, h, w, 1)


def _unit_noise(shape, gen, device, dtype, size):
    n = torch.randn(shape, generator=gen, device="cpu", dtype=torch.float32).to(device, dtype)
    n = blur(n, size)
    return n / (n.std(dim=(-2, -1), keepdim=True) + 1e-6)


def grain(srgb, p, s, seeds):
    """Luma-weighted grain, one fresh pattern per frame (seeded per frame so a
    re-run, or the next chunk of a long clip, matches)."""
    if p["grain"] <= 0:
        return srgb
    b, h, w, _ = srgb.shape
    y = luma(srgb)
    # grain is strongest in the mids, weaker in deep shadow and highlight
    weight = 0.35 + 0.65 * torch.exp(-((y - 0.45) ** 2) / 0.08)
    gs = p["grain_size"] * s
    out = srgb.clone()
    for i, seed in enumerate(seeds):
        gen = torch.Generator().manual_seed(int(seed) & 0xFFFFFFFF)
        base = _unit_noise((1, h, w), gen, srgb.device, srgb.dtype, gs)[0]
        for c, chroma in enumerate((0.55, 0.40, 0.75)):  # blue layer grainiest
            n = _unit_noise((1, h, w), gen, srgb.device, srgb.dtype, gs)[0]
            out[i, ..., c] += p["grain"] * ((1 - chroma) * base + chroma * n) * weight[i]
    return out.clamp(0, 1)


def weave(srgb, p, s, frames, fps):
    """Sub-pixel gate weave: a slow, irregular drift of the whole frame."""
    if p["weave"] <= 0:
        return srgb
    b, h, w, _ = srgb.shape
    amp = p["weave"] * s
    t = torch.tensor(frames, dtype=torch.float32) / fps * 6.0
    dx = amp * (torch.sin(t * 0.9) * 0.6 + torch.sin(t * 2.3 + 1) * 0.4)
    dy = amp * 1.4 * (torch.sin(t * 1.3 + 2) * 0.6 + torch.sin(t * 3.1) * 0.4)
    theta = torch.zeros(b, 2, 3)
    theta[:, 0, 0] = 1
    theta[:, 1, 1] = 1
    # pixels -> normalised coords; positive shift moves the image right/down
    theta[:, 0, 2] = -dx * 2 / w
    theta[:, 1, 2] = -dy * 2 / h
    theta = theta.to(srgb.device, srgb.dtype)
    x = srgb.permute(0, 3, 1, 2)
    grid = F.affine_grid(theta, x.shape, align_corners=False)
    x = F.grid_sample(x, grid, mode="bilinear", padding_mode="reflection", align_corners=False)
    return x.permute(0, 2, 3, 1)


def flicker(lin, amount, frames, seed):
    """Tiny frame-to-frame exposure wobble, smoothed so it breathes rather than strobes."""
    if amount <= 0:
        return lin
    gen = torch.Generator().manual_seed(int(seed) & 0xFFFFFFFF)
    lo, hi = min(frames), max(frames)
    # one random value per frame index, from a fixed sequence so chunks agree
    seq = torch.randn(hi + 3, generator=gen)
    seq = (seq[:-2] + seq[1:-1] + seq[2:]) / 3
    gains = torch.tensor([2 ** (amount * float(seq[f]) * 1.7) for f in frames])
    return lin * gains.view(-1, 1, 1, 1).to(lin.device, lin.dtype)


def finish(images, p, strength=1.0, seed=0, frame_offset=0, fps=24.0,
           flicker_amount=0.0, animate=True):
    """images: (B,H,W,3) sRGB 0..1. Returns the same shape."""
    src = images[..., :3]
    s = src.shape[2] / 2048.0
    frames = [frame_offset + i for i in range(src.shape[0])]
    lin = srgb_to_lin(src)
    x = declarity(lin, p["declarity"], s)
    x = flicker(x, flicker_amount, frames, seed) if animate else x
    x = film_curve(x, p)
    x = colour(x, p)
    x = halation(x, p, s)
    x = lens(x, p, s)
    out = lin_to_srgb(x)
    out = grain(out, p, s, [seed * 100003 + f for f in frames] if animate else [seed] * len(frames))
    if animate:
        out = weave(out, p, s, frames, fps)
    if strength != 1.0:
        out = src + (out - src) * strength
    return out.clamp(0, 1)
