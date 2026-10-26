# Install

Burstwise needs Python 3.10 or newer. It was developed and tested on Linux with an NVIDIA GPU.
macOS and Windows installs below are untested by me.

## From GitHub

```
pipx install git+https://github.com/Arthur031221/Burstwise
```

or into a virtual environment:

```
python -m venv .venv
. .venv/bin/activate
pip install git+https://github.com/Arthur031221/Burstwise
```

I have not published the package to PyPI yet.

The first run downloads two model files (about 90 MB) into `~/.cache/burstwise/models` and
checks their SHA-256. `burstwise models` downloads them ahead of time.

## From source

```
git clone https://github.com/Arthur031221/Burstwise
cd Burstwise
pip install -e ".[dev]"
```

## GPU or CPU

On Linux and Windows the package depends on `onnxruntime-gpu`, which also runs on the CPU. It uses
CUDA when the CUDA libraries are installed and falls back to the CPU when they are not. Pass
`--cpu` to force the CPU. On macOS the CPU build of onnxruntime is installed.

CPU only is about five times slower on the sample set, see [benchmark](benchmark.md).

## ExifTool (optional)

Burstwise does not need ExifTool. The tests use it, when it is installed, to read the written
sidecars back with an independent XMP reader.

## Where files go

| Path | What |
| --- | --- |
| `~/.cache/burstwise/models` | the two downloaded models |
| `~/.cache/burstwise/analysis.db` | cached measurements, keyed by path, size and modified time |
| `~/.cache/burstwise/thumbs` | thumbnails for the review app |
| `FOLDER/.burstwise/` | your decisions and the undo log for that folder |
| `IMG.xmp`, `IMG.ext.xmp` | sidecars, only when you ask for them |

Set `BURSTWISE_HOME` to move the cache directory. Without it, `XDG_CACHE_HOME` is honoured. Originals are never written to.
