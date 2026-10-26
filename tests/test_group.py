from burstwise.group import group_photos, sort_photos, split_scenes

from .helpers import make_photo, unit


def test_scene_split_on_time_gap():
    photos = [make_photo(taken=t) for t in (0, 1, 2, 500, 501)]
    assert split_scenes(photos, 120) == [[0, 1, 2], [3, 4]]


def test_similar_frames_group_and_different_ones_do_not(settings):
    photos = sort_photos(
        [
            make_photo(taken=0, embedding=unit(0)),
            make_photo(taken=1, embedding=unit(8)),
            make_photo(taken=2, embedding=unit(90)),
        ]
    )
    assert group_photos(photos, settings) == [[0, 1], [2]]


def test_identical_look_in_different_scenes_stays_apart(settings):
    photos = sort_photos(
        [make_photo(taken=0, embedding=unit(0)), make_photo(taken=600, embedding=unit(0))]
    )
    assert group_photos(photos, settings) == [[0], [1]]


def test_similarity_setting_moves_the_boundary(settings):
    photos = sort_photos(
        [make_photo(taken=0, embedding=unit(0)), make_photo(taken=1, embedding=unit(45))]
    )
    assert len(group_photos(photos, settings)) == 2
    settings.similarity = 0.5
    assert len(group_photos(photos, settings)) == 1


def test_every_photo_lands_in_exactly_one_group(settings):
    photos = sort_photos([make_photo(taken=i, embedding=unit(i * 7)) for i in range(30)])
    members = sorted(i for g in group_photos(photos, settings) for i in g)
    assert members == list(range(30))
