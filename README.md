**English** | [Traditional Chinese](README.zh-TW.md) | [Simplified Chinese](README.zh-CN.md) | [Japanese](README.ja.md) | [Korean](README.ko.md) | [Spanish](README.es.md) | [French](README.fr.md) | [German](README.de.md) | [Portuguese (Brazil)](README.pt-BR.md)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img src="assets/banner-light.svg" alt="Burstwise: one burst, one pick, the rest kept as alternates" width="720">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/Arthur031221/Burstwise/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Arthur031221/Burstwise/ci.yml?branch=main&label=tests&labelColor=0e1015&color=ffb020" alt="tests"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-ffb020?labelColor=0e1015" alt="python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-ffb020?labelColor=0e1015" alt="MIT license">
  <a href="https://arthur031221.github.io/Burstwise/"><img src="https://img.shields.io/badge/live%20demo-open-ffb020?labelColor=0e1015" alt="live demo"></a>
</p>

<p align="center">
  <img src="assets/demo.gif" alt="Burstwise culling a folder of 166 photos and opening the review app" width="880">
</p>

Burstwise culls a shoot on your own machine. It groups photos of the same moment, flags blur, closed eyes and clipped exposure, picks the best frame in each group and writes the result as XMP ratings and colour labels next to your files. Nothing is uploaded and no original is touched.

On the sample set it reads, groups and judges 166 photos in 1.9 seconds on a GPU, and in 10.5 seconds on the CPU alone. The method and the other numbers are in the [benchmark](docs/benchmark.md). [Try the live demo](https://arthur031221.github.io/Burstwise/).

## Before and after

The sample folder is 166 frames cut from four short videos, so many of them look alike on purpose.

| | Before | After `burstwise cull --write-xmp` |
| --- | --- | --- |
| Order | 166 files in one folder | 17 groups, one per moment |
| Best frame | You scroll and compare | 17 picks, rated 4 and labelled Green |
| Bad frames | Found by zooming in on each | 15 rejects (9 closed eyes, 6 soft), rated -1 and labelled Red |
| The rest | Mixed in with the keepers | 134 alternates, left untouched |
| Reasons | None | A number for every verdict, for example `soft, 41% of the sharpest frame` |
| Your originals | Safe | Safe. Only `.xmp` files are written, and `burstwise undo` restores them |

A culling tool should show its work. Every verdict has a reason you can read, every threshold is a plain setting, and there's no hidden score.

## Quick start

```
pipx install git+https://github.com/Arthur031221/Burstwise
burstwise cull ~/Pictures/shoot              # print the plan, change nothing
burstwise cull ~/Pictures/shoot --write-xmp  # write ratings and labels
burstwise serve ~/Pictures/shoot             # review and override in the browser
```

The first run downloads two model files, about 90 MB in total, and checks their SHA-256.

<details>
<summary>Install on Linux (tested)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

For the GPU you need a working CUDA 12 setup for `onnxruntime-gpu`. Without it Burstwise falls back to the CPU on its own, or you can pass `--cpu`. I develop and test on Ubuntu with an NVIDIA GPU. On a minimal server, a container or WSL, install the graphics libraries first with `sudo apt install libegl1 libgles2`, or Burstwise stops with a message about the face model.

</details>

<details>
<summary>Install on macOS (not tested)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

The package asks for the CPU build of onnxruntime on macOS. I haven't run Burstwise on a Mac, so treat this as untried.

</details>

<details>
<summary>Install on Windows (not tested)</summary>

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

I haven't run Burstwise on Windows, so treat this as untried.

</details>

<details>
<summary>Install from source</summary>

```
git clone https://github.com/Arthur031221/Burstwise
cd Burstwise
pip install -e ".[dev]"
```

</details>

## How it decides

1. Photos are split into scenes wherever the capture time jumps by more than 120 seconds.
2. Inside a scene, photos with close DINOv2 embeddings (cosine similarity above 0.80, average linkage) form a group.
3. Each photo gets three checks: MediaPipe blink scores for every face, sharpness of the face (or of the sharpest tiles when a group has a frame without a face), and clipped highlights or shadows.
4. A group ranks its frames by closed faces, then by the number of other problems, then by sharpness. The top frame is a pick, or a review if it has a problem of its own. The others are alternates, or rejects if they have a problem.

[Architecture](docs/architecture.md) has the details and [config](docs/config.md) lists every threshold.

## What it writes

| Verdict | XMP |
| --- | --- |
| pick | rating 4, label Green |
| review | label Yellow |
| alt | nothing |
| reject | rating -1 (rejected), label Red |

Sidecars are merged, not replaced. Edits already in a Lightroom or darktable sidecar stay, and only `xmp:Rating`, `xmp:Label` and a `burstwise:Verdict` and `burstwise:Reason` pair are set. If a sidecar written by someone else already holds a rating (rejected counts) or a label, the photo is skipped unless you pass `--overwrite`. Sidecars Burstwise wrote earlier are updated on the next run.

Lightroom Classic reads `.xmp` sidecars for raw files only. For JPEG, TIFF, PNG and HEIC it keeps XMP inside the file, so the ratings and labels written here won't show up in Lightroom for those formats. darktable reads sidecars for every format. That comes from Adobe's documentation and I haven't tried it in Lightroom.

## What I checked and what I did not

- I read the written sidecars back with ExifTool 13.59 and compared the rating, the label, the rejected value, and that existing `crs:` develop settings survive. That's in the test suite.
- I have not opened the sidecars in Lightroom, Capture One or darktable. They're standard XMP, but I can't say how each program treats them.
- I haven't measured accuracy. The checks are heuristics. Blink scores can call a laugh or a squint closed, and sharpness can't tell focus blur from motion blur. I judged the sample results by eye and that's all.
- Linux is the only system I tested. The speed figures come from one machine.
- Grouping uses how photos look and when they were taken. Two different moments that look alike and fall within the scene gap can land in one group, so check the groups in the review app.
- Adobe and paid tools such as Aftershoot and Narrative Select also do culling. Burstwise is for people who want it free, local and readable, with plain XMP as the output.

## Docs

- [Install](docs/install.md)
- [Usage and the review app](docs/usage.md)
- [Configuration](docs/config.md)
- [Architecture](docs/architecture.md)
- [Benchmark](docs/benchmark.md)
- [Contributing](CONTRIBUTING.md)

In the review app each group shows its best frame large and folds long groups. The arrow keys, P, X, U and 1 to 5 work straight from the grid. The app speaks English, Traditional and Simplified Chinese, Japanese, Korean, Spanish, French, German and Brazilian Portuguese, with a dark and a light theme.

## Sample data

The code is MIT. The sample photos are frames from Creative Commons videos, listed in [examples/CREDITS.md](examples/CREDITS.md). They aren't stored in this repository and some of them are CC BY-SA, so keep their credits if you reuse them.

## The name

Burstwise is a made up adverb compound: burst, as in a burst of frames, plus wise, as in sensible and as in "one burst at a time".

## License

MIT. See [LICENSE](LICENSE).

Assisted by Claude/Codex.
