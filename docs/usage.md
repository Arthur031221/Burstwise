# Usage

## Command line

```
burstwise cull ~/Pictures/2024-06-wedding
```

prints the number of photos, groups and verdicts and changes nothing. Add `-v` to list every
photo with the reason for its verdict.

```
burstwise cull FOLDER --write-xmp              # write sidecars next to the photos
burstwise cull FOLDER --write-xmp --dry-run    # count what would be written
burstwise cull FOLDER --copy-keepers ~/keep    # copy the picks and their sidecars
burstwise cull FOLDER --report report.json     # every measurement and verdict as JSON
burstwise undo FOLDER                          # restore the sidecars of the last write
burstwise serve FOLDER                         # open the review app
```

Options shared by `cull` and `serve`:

| Option | Meaning |
| --- | --- |
| `--similarity 0.8` | cosine similarity needed to share a group |
| `--scene-gap 120` | seconds apart that always split groups |
| `--cpu` | do not use the GPU |
| `--no-recursive` | skip subfolders |
| `--workers N` | photo decoding threads |

`--xmp-naming` picks `adobe` (`IMG_1.xmp`), `darktable` (`IMG_1.CR2.xmp`) or `both` (the default).
If a sidecar written by someone else already holds a rating (including rejected) or a colour
label, that photo is skipped, under both names, unless you pass `--overwrite`. Sidecars that
Burstwise wrote earlier are updated in place on the next run, and a photo that is now an
alternate gets its old Burstwise rating and label removed. A sidecar that cannot be parsed is
left alone and counted as skipped.

## Verdicts

| Verdict | Meaning | XMP written |
| --- | --- | --- |
| pick | best frame of its group, no problem found | rating 4, label Green |
| review | best frame of its group, but a problem was found | label Yellow |
| alt | not the best, no problem found | nothing |
| reject | not the best, and a problem was found | rating -1, label Red |

A rating of -1 is the value the XMP specification defines as rejected.
A rating you give in the review app wins over the verdict. Every verdict carries its reasons as numbers, for example `soft, 41% of the sharpest frame`.
The reason text is also stored in the sidecar as `burstwise:Reason`.

## Review app

`burstwise serve FOLDER` analyses the folder and opens a page on `127.0.0.1`. Nothing leaves
your computer. The page shows groups with their picks and rejects. Open a photo to compare it
with the group pick, see the detected faces with blink scores, and zoom on a face.

| Key | Action |
| --- | --- |
| `P` / `X` / `U` | pick, reject, back to automatic |
| `1` to `5` | set a star rating |
| `C` | compare with the group pick |
| `F` | show faces and blink scores |
| `Z` | zoom |
| `Left` / `Right` | previous and next photo |
| `Esc` | close the photo |
| `?` | list the keys |

Your decisions are saved in `FOLDER/.burstwise/decisions.json` and are used when you write
sidecars or copy keepers. The settings panel changes the group similarity and the softness
ratio and regroups from cached measurements without reading the photos again.

The page has nine languages (English, Traditional and Simplified Chinese, Japanese, Korean,
Spanish, French, German, Brazilian Portuguese), a dark and a light theme, and works on a phone
screen.

## Live demo

The [demo](https://arthur031221.github.io/Burstwise/) is the same page with the results of the
sample set baked in. It cannot write files. Decisions you make there stay in your browser.

## Python

```python
from pathlib import Path
from burstwise.config import Settings
from burstwise.library import analyze_folder

library = analyze_folder(Path("photos"), Settings(similarity=0.85))
for photo in library.photos:
    print(photo.name, library.verdicts[photo.id].state)
```
