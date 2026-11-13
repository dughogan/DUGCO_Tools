# DUGco Frame Tools

Two small utility nodes under **DUGco / Frames**. Neither needs a model or any extra package.

## DUGco Repeat Latent Frames

Repeats each latent frame of a video latent along time, before the VAE decode.

```
Sampler  ->  DUGco Repeat Latent Frames  ->  VAE Decode
```

It is a decode-side smear test: because a video VAE decodes neighbouring latent frames together, repeating them shows how much the decoder blends across time.

| Input | What it does |
| --- | --- |
| `times` | How many times each latent frame is repeated. 1 leaves the latent as it is. |
| `keep_first` | Leaves the first latent frame single. Causal video VAEs treat that frame differently from the rest. |
| `latent_frames` | Uses only the first N latent frames (0 = all), to keep a big decode in memory. |

An image latent (4 dimensions) passes through unchanged. Any noise mask is dropped, because it no longer matches the new frame count.

## DUGco Select Every Nth Frame

Keeps every Nth image of a batch.

| Input | What it does |
| --- | --- |
| `n` | Keep one frame in every N. |
| `offset` | The first frame to keep. |
| `max_frames` | Stop after this many kept frames. 0 = no cap. |

For example, `n` 2 turns a 48 fps batch into 24 fps, and `n` 2 with `offset` 1 keeps the other half of the frames.
