# Configuration

Every threshold is a field of `Settings` in `src/burstwise/config.py`. There is no hidden score.
Each one is a plain rule you can read and change.

| Setting | Default | Rule |
| --- | --- | --- |
| `similarity` | 0.80 | Photos in one time scene whose DINOv2 embeddings have cosine similarity above this share a group. Average linkage. |
| `scene_gap` | 120 s | Photos taken further apart than this are never grouped together. |
| `blink_closed` | 0.50 | A face counts as closed when the mean of MediaPipe eyeBlinkLeft and eyeBlinkRight is at or above this. |
| `soft_ratio` | 0.55 | A frame is soft when its sharpness is below this share of the sharpest frame in its group. |
| `soft_floor` | 12 | A frame below this sharpness is soft even with no sharper neighbour. |
| `clip_highlight` | 0.08 | A frame has clipped highlights when this share of pixels is at 250 or above. |
| `clip_shadow` | 0.30 | A frame has crushed shadows when this share of pixels is at 5 or below. |
| `pick_stars` | 4 | Rating written for a pick. |
| `pick_label`, `review_label`, `reject_label` | Green, Yellow, Red | Colour labels written. |

## Where to change them

- The command line takes `--similarity` and `--scene-gap`.
- The review app has sliders for similarity and the softness ratio. Changes regroup at once
  because the measurements are cached.
- Everything else is set through the Python API: `analyze_folder(folder, Settings(soft_ratio=0.6))`.

## About the defaults

Sharpness is the variance of the Laplacian after a Gaussian blur of sigma 1, measured on a
preview at most 1600 pixels on the long side. The defaults are starting points that I picked by
looking at the sample set, not values fitted to a labelled data set. I have no measured accuracy
for them. If Burstwise is too strict or too lenient for your kind of photography, change them
and look at the result in the review app.

A lone frame that falls under `soft_floor` is marked review, not reject, because a plain sky
or wall can score low without being a bad photo.
