# Architecture

```
folder
  |  find_photos            JPEG, PNG, WebP, TIFF, HEIC, 20 RAW extensions; a JPEG next to a RAW of the same name is skipped
  v
preview (long side 1600)    RAW: embedded JPEG preview, or a half size decode
  |
  +-- MediaPipe FaceLandmarker  -> face boxes, eyeBlinkLeft / eyeBlinkRight
  +-- sharpness                 -> face patches, tile 90th percentile
  +-- exposure                  -> share of clipped highlights and shadows
  +-- DINOv2 small (ONNX)       -> 384 number embedding of a 224 x 224 resize
  |
  v
cache (SQLite)              one row per photo, keyed by path, size and mtime
  |
  v
group                       split by time gap, then average linkage clustering
  |
  v
pick                        rank each group, label pick / review / alt / reject
  |
  v
export                      XMP sidecars, copy keepers, JSON report
```

## Modules

| Module | Job |
| --- | --- |
| `media.py` | find photos, decode previews, read capture time |
| `models.py` | download and verify models, run them |
| `checks.py` | sharpness, exposure and blink as plain numbers |
| `analyze.py` | one photo in, one `Photo` of measurements out |
| `cache.py` | SQLite cache of `Photo`, versioned by `ANALYSIS_VERSION` |
| `group.py` | scene split and clustering |
| `pick.py` | verdicts with coded reasons |
| `library.py` | analyse a folder with threads, then group and judge |
| `export.py`, `xmp.py` | sidecars, undo log, copy keepers, report |
| `server.py`, `web/` | the review app |

RAW files use their embedded JPEG preview when it is at least 1000 px on the long side. A RAW
file without one is decoded at half size, which is slower.

## Choices that matter

**Measurements are cached, decisions are not.** The expensive step is reading and measuring a
photo. Grouping and picking take milliseconds from cached numbers, so moving a threshold in the
review app regroups at once.

**Face sharpness and frame sharpness are never compared with each other.** A face patch and a
whole frame tile are on different scales, so inside one group every frame is scored the same way.
The absolute `soft_floor` is one number for both scales, which is a rough edge. A group uses face sharpness only when every frame in it has a face, and frame
sharpness otherwise. Mixing them made good frames look soft in testing, which is why the rule exists.

**Reasons are codes with numbers.** The command line prints English, and the page renders the
same codes in its own language, so a reason can be translated without parsing text.

**XMP is merged, not replaced.** A sidecar from Lightroom or darktable holds your edits. Burstwise
parses it with lxml, sets only `xmp:Rating`, `xmp:Label` and its own `burstwise:` fields, and
leaves every other element alone. External entities are not resolved. Every sidecar it touches is
copied to `.burstwise/undo` first, with the log written as it goes so a crash cannot lose it, and
`burstwise undo` restores them.

**The server is local only.** It binds to 127.0.0.1, answers only requests whose Host header is
a loopback name, which stops DNS rebinding, and refuses writes that carry a foreign Origin. There is no login, so any program running as you on
the same computer can use the same API.

## Limits

- Groups come from how photos look and when they were taken, not from who or what is in them.
  Two different moments that look alike within the scene gap can land in one group.
- Sharpness cannot tell focus blur from motion blur, and cannot tell deliberate blur from an
  accident. It compares frames of one group, so a lone photo is only judged against the floor.
- Blink scores come from a face model and can call a laugh or a squint closed. I checked it by
  eye on one sample set and make no accuracy claim.
- Pictures where no face is found are judged on sharpness and exposure only.
