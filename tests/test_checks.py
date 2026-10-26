import cv2
import numpy as np

from burstwise import checks

from .helpers import texture


def gray_of_image(sigma: float = 0.0) -> np.ndarray:
    rgb = np.asarray(texture(1, (800, 600)))
    if sigma:
        rgb = cv2.GaussianBlur(rgb, (0, 0), sigma)
    return checks.gray_of(rgb)


def test_blur_lowers_tile_sharpness_monotonically():
    scores = [checks.tile_sharpness(gray_of_image(s)) for s in (0, 1, 2, 4)]
    assert scores == sorted(scores, reverse=True)
    assert scores[-1] < 0.2 * scores[0]


def test_flat_frame_scores_near_zero():
    assert checks.tile_sharpness(np.full((600, 800), 128, dtype=np.uint8)) < 1


def test_face_sharpness_is_zero_without_faces():
    assert checks.face_sharpness(gray_of_image(), []) == 0.0


def test_face_sharpness_reads_the_face_patch():
    gray = gray_of_image()
    gray[:, :] = 128
    gray[200:400, 300:500] = gray_of_image()[200:400, 300:500]
    inside = checks.face_sharpness(gray, [[300 / 800, 200 / 600, 200 / 800, 200 / 600]])
    outside = checks.face_sharpness(gray, [[0.0, 0.0, 0.1, 0.1]])
    assert inside > 10 * max(outside, 1)


def test_exposure_shares():
    gray = np.full((100, 100), 128, dtype=np.uint8)
    gray[:50] = 255
    gray[50:60] = 0
    hi, lo = checks.exposure(gray)
    assert abs(hi - 0.5) < 1e-6 and abs(lo - 0.1) < 1e-6


def test_blink_is_the_mean_of_both_eyes():
    assert checks.blink({"blink_l": 0.2, "blink_r": 0.6}) == 0.4
