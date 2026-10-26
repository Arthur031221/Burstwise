from burstwise.pick import group_sharpness, judge_group, reason_text

from .helpers import face, make_photo


def codes(items):
    return [i["code"] for i in items]


def test_single_sharp_frame_is_a_pick(settings):
    photo = make_photo()
    verdict = judge_group([photo], settings)[photo.id]
    assert verdict.state == "pick"
    assert codes(verdict.reasons) == ["only_frame"]


def test_sharpest_frame_wins_and_soft_one_is_rejected(settings):
    sharp, soft = make_photo(sharp_tile=100), make_photo(sharp_tile=30)
    verdicts = judge_group([soft, sharp], settings)
    assert verdicts[sharp.id].state == "pick"
    assert verdicts[soft.id].state == "reject"
    assert verdicts[soft.id].problems[0] == {"code": "soft", "percent": 30}


def test_a_close_runner_up_is_kept_as_alternative(settings):
    a, b = make_photo(sharp_tile=100), make_photo(sharp_tile=90)
    verdicts = judge_group([a, b], settings)
    assert verdicts[b.id].state == "alt"


def test_closed_eyes_lose_to_a_sharper_frame(settings):
    blink = make_photo(sharp_face=300, faces=[face(0.9)])
    open_eyes = make_photo(sharp_face=200, faces=[face(0.1)])
    verdicts = judge_group([blink, open_eyes], settings)
    assert verdicts[open_eyes.id].state == "pick"
    assert verdicts[blink.id].state == "reject"
    assert verdicts[blink.id].problems[0]["code"] == "closed_eyes"


def test_blink_threshold_uses_the_mean_of_both_eyes(settings):
    wink = make_photo(faces=[{"box": [0, 0, 1, 1], "blink_l": 0.8, "blink_r": 0.0}])
    shut = make_photo(faces=[{"box": [0, 0, 1, 1], "blink_l": 1.0, "blink_r": 0.0}])
    assert judge_group([wink], settings)[wink.id].state == "pick"
    assert judge_group([shut], settings)[shut.id].state == "review"


def test_every_frame_blinking_leaves_the_best_one_for_review(settings):
    a = make_photo(sharp_face=300, faces=[face(0.9)])
    b = make_photo(sharp_face=100, faces=[face(0.9)])
    verdicts = judge_group([a, b], settings)
    assert verdicts[a.id].state == "review"


def test_clipped_highlights_and_shadows_are_flagged(settings):
    bright = make_photo(clip_hi=0.2)
    dark = make_photo(clip_lo=0.5)
    problems = [
        judge_group([bright], settings)[bright.id].problems,
        judge_group([dark], settings)[dark.id].problems,
    ]
    assert codes(problems[0]) == ["highlights"]
    assert codes(problems[1]) == ["shadows"]


def test_absolute_floor_flags_a_single_blank_frame(settings):
    blank = make_photo(sharp_tile=4)
    assert judge_group([blank], settings)[blank.id].state == "review"


def test_face_and_tile_scores_are_never_mixed(settings):
    with_face = make_photo(sharp_face=500, sharp_tile=100)
    without = make_photo(sharp_face=0, sharp_tile=100)
    scores = group_sharpness([with_face, without])
    assert scores == {with_face.id: 100, without.id: 100}
    verdicts = judge_group([with_face, without], settings)
    assert not any(v.state == "reject" for v in verdicts.values())


def test_reasons_render_with_their_numbers():
    text = reason_text({"code": "soft", "percent": 41})
    assert text == "soft, 41% of the sharpest frame"
    assert "2 of 5" in reason_text({"code": "eyes_open", "peers": 2, "of": 5})
