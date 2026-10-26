import json

from burstwise.export import copy_keepers, edit_for, report, write_xmp
from burstwise.library import Library, regroup
from burstwise.pick import Verdict
from burstwise.xmp import Edit, read_existing, write_sidecar

from .helpers import make_photo


def test_pick_gets_stars_and_green(settings):
    edit = edit_for(Verdict("pick", 1, reasons=[{"code": "only_frame"}]), settings)
    assert (edit.rating, edit.label, edit.verdict) == (4, "Green", "pick")
    assert edit.reason == "only frame of its moment"


def test_reject_uses_the_xmp_rejected_rating(settings):
    edit = edit_for(Verdict("reject", 2, problems=[{"code": "soft", "percent": 30}]), settings)
    assert (edit.rating, edit.label) == (-1, "Red")


def test_review_is_labelled_but_not_rated(settings):
    edit = edit_for(
        Verdict("review", 1, problems=[{"code": "highlights", "percent": 20}]), settings
    )
    assert (edit.rating, edit.label) == (None, "Yellow")


def test_alternates_are_left_alone(settings):
    assert edit_for(Verdict("alt", 2), settings) is None


def test_user_decision_overrides_the_verdict(settings):
    edit = edit_for(Verdict("reject", 2), settings, {"state": "pick", "rating": 5})
    assert (edit.rating, edit.label, edit.verdict) == (5, "Green", "pick")


def test_write_xmp_writes_both_names_and_counts(library):
    tally = write_xmp(library, "both")
    assert tally["created"] == 2 * sum(1 for v in library.verdicts.values() if v.state != "alt")
    first = next(p for p in library.photos if library.verdicts[p.id].state == "pick")
    assert read_existing(library.folder / (first.name.rsplit(".", 1)[0] + ".xmp"))[0] == 4


def test_dry_run_touches_nothing(library):
    before = sorted(p.name for p in library.folder.iterdir())
    write_xmp(library, "both", dry_run=True)
    assert sorted(p.name for p in library.folder.iterdir()) == before


def test_originals_are_byte_identical_after_writing(library):
    before = {p.name: p.read_bytes() for p in library.folder.glob("*.JPG")}
    write_xmp(library, "both")
    assert {p.name: p.read_bytes() for p in library.folder.glob("*.JPG")} == before


def test_copy_keepers_keeps_sidecars_and_does_not_overwrite(tmp_path, settings):
    one, two = tmp_path / "a", tmp_path / "b"
    one.mkdir()
    two.mkdir()
    photos = []
    for folder, body in ((one, b"first"), (two, b"second")):
        photo = make_photo(name="IMG_0001.JPG", path=str(folder / "IMG_0001.JPG"), taken=1)
        photo.taken += len(photos) * 1000
        (folder / "IMG_0001.JPG").write_bytes(body)
        (folder / "IMG_0001.xmp").write_text("<x/>")
        photos.append(photo)
    lib = regroup(Library(folder=tmp_path, settings=settings, photos=photos))
    out = tmp_path / "keep"
    copied = copy_keepers(lib, out)
    assert sorted(p.name for p in copied) == ["IMG_0001.JPG", "IMG_0001_2.JPG"]
    assert {p.read_bytes() for p in copied} == {b"first", b"second"}
    assert (out / "IMG_0001_2.xmp").exists()
    assert (one / "IMG_0001.JPG").exists()


def test_report_counts_and_json_round_trip(library):
    data = report(library)
    assert json.loads(json.dumps(data))["counts"] == library.counts()


def test_a_rating_you_gave_a_reject_is_kept(settings):
    verdict = Verdict(state="reject", rank=2, problems=[{"code": "soft", "percent": 30}])
    assert edit_for(verdict, settings, {"rating": 3}).rating == 3
    assert edit_for(verdict, settings, {"rating": 3}).label is None
    assert edit_for(verdict, settings).rating == -1


def test_both_names_are_skipped_together_when_one_is_rated(library):
    pick = next(p for p in library.photos if library.verdicts[p.id].state == "pick")
    adobe = (library.folder / pick.name).with_suffix(".xmp")
    write_sidecar(adobe, Edit(rating=3))
    tally = write_xmp(library, "both")
    assert not (library.folder / (pick.name + ".xmp")).exists()
    assert tally["skipped"] >= 2


def test_two_photos_sharing_a_sidecar_name_write_it_once(library):
    names = [p for p in library.photos if library.verdicts[p.id].state == "pick"]
    clash = names[0]
    names[1].path = str((library.folder / clash.name).with_suffix(".HEIC"))
    tally = write_xmp(library, "adobe")
    assert tally["skipped"] >= 1


def test_rerun_after_a_change_clears_what_burstwise_wrote(library):
    pick = next(p for p in library.photos if library.verdicts[p.id].state == "pick")
    write_xmp(library, "adobe")
    sidecar = (library.folder / pick.name).with_suffix(".xmp")
    assert read_existing(sidecar)[0] == 4
    library.verdicts[pick.id] = Verdict(state="alt", rank=2)
    write_xmp(library, "adobe")
    assert read_existing(sidecar)[:2] == (None, None)


def test_copy_keepers_does_not_overwrite_a_foreign_sidecar(tmp_path, settings):
    src = tmp_path / "a"
    src.mkdir()
    photo = make_photo(name="IMG_0001.JPG", path=str(src / "IMG_0001.JPG"), taken=1)
    (src / "IMG_0001.JPG").write_bytes(b"x")
    out = tmp_path / "keep"
    out.mkdir()
    (out / "IMG_0001.xmp").write_text("<mine/>")
    lib = regroup(Library(folder=tmp_path, settings=settings, photos=[photo]))
    copied = copy_keepers(lib, out)
    assert copied[0].name == "IMG_0001_2.JPG"
    assert (out / "IMG_0001.xmp").read_text() == "<mine/>"
