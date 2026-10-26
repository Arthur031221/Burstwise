import calendar
import time

from burstwise import media

from .helpers import texture, write_jpeg


def test_exif_time_with_subseconds(tmp_path):
    path = write_jpeg(tmp_path / "a.jpg", texture(1), "2024:06:01 10:00:00")
    taken, from_exif = media.capture_time(path)
    assert from_exif and taken == 1717236000.0


def test_missing_exif_falls_back_to_file_time(tmp_path):
    path = write_jpeg(tmp_path / "a.jpg", texture(1))
    taken, from_exif = media.capture_time(path)
    assert not from_exif
    assert taken == calendar.timegm(time.localtime(path.stat().st_mtime))


def test_preview_is_fitted_and_reports_full_size(tmp_path):
    path = write_jpeg(tmp_path / "big.jpg", texture(1, (1200, 800)))
    img, (w, h) = media.load_preview(path, 400)
    assert (w, h) == (1200, 800) and max(img.size) == 400


def test_raw_wins_over_a_jpeg_with_the_same_name(tmp_path):
    for name in ("IMG_1.CR2", "IMG_1.JPG", "IMG_2.JPG", "notes.txt"):
        (tmp_path / name).write_bytes(b"x")
    names = [p.name for p in media.find_photos(tmp_path)]
    assert names == ["IMG_1.CR2", "IMG_2.JPG"]


def test_working_folder_is_ignored(tmp_path):
    hidden = tmp_path / ".burstwise"
    hidden.mkdir()
    (hidden / "x.jpg").write_bytes(b"x")
    assert media.find_photos(tmp_path) == []


def test_no_recursive_skips_subfolders(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.jpg").write_bytes(b"x")
    assert media.find_photos(tmp_path, recursive=False) == []
    assert len(media.find_photos(tmp_path)) == 1
