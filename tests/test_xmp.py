from pathlib import Path

import pytest
from lxml import etree

from burstwise.xmp import (
    NS_BW,
    NS_XMP,
    Edit,
    UndoLog,
    clear_ours,
    read_existing,
    sidecar_paths,
    undo_latest,
    write_sidecar,
)

LIGHTROOM = """<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
    crs:Exposure2012="+0.35" xmp:Rating="{rating}">
   <crs:ToneCurve><rdf:Seq><rdf:li>0, 0</rdf:li></rdf:Seq></crs:ToneCurve>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
"""


def props(path: Path) -> dict[str, str]:
    root = etree.parse(str(path)).getroot()
    desc = next(root.iter("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description"))
    out = {etree.QName(k).localname: v for k, v in desc.attrib.items()}
    out.update({etree.QName(c).localname: c.text for c in desc if c.text and c.text.strip()})
    return out


def test_new_sidecar_is_valid_xmp(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    assert write_sidecar(side, Edit(rating=4, label="Green", verdict="pick")) == "created"
    got = props(side)
    assert got["Rating"] == "4" and got["Label"] == "Green" and got["Verdict"] == "pick"
    assert side.read_text().startswith("<?xpacket")


def test_existing_edits_survive_the_merge(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    side.write_text(LIGHTROOM.format(rating="0"), encoding="utf-8")
    assert write_sidecar(side, Edit(rating=4, label="Green")) == "updated"
    text = side.read_text(encoding="utf-8")
    assert 'crs:Exposure2012="+0.35"' in text
    assert "ToneCurve" in text
    assert props(side)["Rating"] == "4"


def test_rated_photo_is_skipped_unless_overwrite(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    side.write_text(LIGHTROOM.format(rating="5"), encoding="utf-8")
    assert write_sidecar(side, Edit(rating=-1)) == "skipped"
    assert read_existing(side) == (5, None, False)
    assert write_sidecar(side, Edit(rating=-1), overwrite=True) == "updated"
    assert read_existing(side)[0] == -1


def test_rating_as_child_element_is_replaced_not_duplicated(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    side.write_text(
        LIGHTROOM.replace('xmp:Rating="{rating}"', "").replace(
            "</rdf:Description>",
            f"<xmp:Rating xmlns:xmp='{NS_XMP}'>0</xmp:Rating></rdf:Description>",
        ),
        encoding="utf-8",
    )
    write_sidecar(side, Edit(rating=3))
    assert side.read_text(encoding="utf-8").count("Rating") == 2  # one open, one close tag
    assert props(side)["Rating"] == "3"


def test_burstwise_namespace_is_declared(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    write_sidecar(side, Edit(verdict="reject", reason="soft, 30% of the sharpest frame"))
    assert NS_BW in side.read_text()


def test_external_entities_are_not_resolved(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    side = tmp_path / "IMG_1.xmp"
    side.write_text(
        f'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file://{secret}">]>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>&e;</dc:title></rdf:Description></rdf:RDF></x:xmpmeta>"
    )
    write_sidecar(side, Edit(rating=2), overwrite=True)
    assert "TOP-SECRET" not in side.read_text()


@pytest.mark.parametrize(
    ("naming", "names"),
    [
        ("adobe", ["IMG_1.xmp"]),
        ("darktable", ["IMG_1.CR2.xmp"]),
        ("both", ["IMG_1.xmp", "IMG_1.CR2.xmp"]),
    ],
)
def test_sidecar_naming(naming, names):
    assert [p.name for p in sidecar_paths(Path("/x/IMG_1.CR2"), naming)] == names


def test_undo_restores_edited_and_removes_created(tmp_path):
    old = tmp_path / "A.xmp"
    old.write_text(LIGHTROOM.format(rating="0"), encoding="utf-8")
    before = old.read_bytes()
    new = tmp_path / "B.xmp"
    log = UndoLog(tmp_path)
    for side in (old, new):
        log.remember(side)
        write_sidecar(side, Edit(rating=4))
    log.save()
    assert undo_latest(tmp_path) == 2
    assert old.read_bytes() == before
    assert not new.exists()
    assert undo_latest(tmp_path) == 0


def test_a_rejected_photo_is_protected_too(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    side.write_text(LIGHTROOM.format(rating="-1"), encoding="utf-8")
    assert write_sidecar(side, Edit(rating=4, label="Green")) == "skipped"
    assert read_existing(side)[0] == -1


def test_a_malformed_sidecar_is_skipped_not_fatal(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    side.write_text("<x:xmpmeta", encoding="utf-8")
    assert write_sidecar(side, Edit(rating=4)) == "skipped"
    assert side.read_text(encoding="utf-8") == "<x:xmpmeta"


def test_a_sidecar_without_rdf_is_skipped_not_fatal(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    side.write_text('<x:xmpmeta xmlns:x="adobe:ns:meta/"/>', encoding="utf-8")
    assert write_sidecar(side, Edit(rating=4)) == "skipped"


def test_our_own_sidecar_is_updated_and_stale_values_go(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    write_sidecar(side, Edit(rating=4, label="Green", verdict="pick"))
    assert write_sidecar(side, Edit(label="Yellow", verdict="review")) == "updated"
    got = props(side)
    assert got["Label"] == "Yellow" and "Rating" not in got and got["Verdict"] == "review"
    assert clear_ours(side)
    assert not {"Label", "Verdict", "Reason"} & set(props(side))


def test_clear_ours_leaves_other_sidecars_alone(tmp_path):
    side = tmp_path / "IMG_1.xmp"
    side.write_text(LIGHTROOM.format(rating="3"), encoding="utf-8")
    assert not clear_ours(side)
    assert read_existing(side)[0] == 3


def test_manifest_exists_even_if_the_run_dies(tmp_path):
    old = tmp_path / "A.xmp"
    old.write_text(LIGHTROOM.format(rating="0"), encoding="utf-8")
    before = old.read_bytes()
    log = UndoLog(tmp_path)
    log.remember(old)
    write_sidecar(old, Edit(rating=4))
    assert undo_latest(tmp_path) == 1
    assert old.read_bytes() == before


def test_two_runs_in_one_second_keep_separate_undo_folders(tmp_path):
    side = tmp_path / "A.xmp"
    first, second = UndoLog(tmp_path), UndoLog(tmp_path)
    assert first.dir != second.dir
    first.remember(side)
    write_sidecar(side, Edit(rating=4, verdict="pick"))
    second.remember(side)
    write_sidecar(side, Edit(rating=3, verdict="pick"), overwrite=True)
    assert undo_latest(tmp_path) == 1
    assert read_existing(side)[0] == 4
    assert undo_latest(tmp_path) == 1
    assert not side.exists()
