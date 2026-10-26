"""Write ratings and labels to XMP sidecars without touching anything else in them."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lxml import etree

NS_X = "adobe:ns:meta/"
NS_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
NS_XMP = "http://ns.adobe.com/xap/1.0/"
NS_BW = "https://github.com/Arthur031221/Burstwise/ns/1.0/"

RATING = f"{{{NS_XMP}}}Rating"
LABEL = f"{{{NS_XMP}}}Label"
DESCRIPTION = f"{{{NS_RDF}}}Description"

NEW_SIDECAR = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    f'<x:xmpmeta xmlns:x="{NS_X}" x:xmptk="Burstwise">\n'
    f' <rdf:RDF xmlns:rdf="{NS_RDF}">\n'
    f'  <rdf:Description rdf:about="" xmlns:xmp="{NS_XMP}" xmlns:burstwise="{NS_BW}"/>\n'
    " </rdf:RDF>\n"
    "</x:xmpmeta>\n"
    '<?xpacket end="w"?>\n'
)

PARSER = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False)


@dataclass
class Edit:
    rating: int | None = None
    label: str | None = None
    verdict: str | None = None
    reason: str | None = None


def sidecar_paths(photo: Path, naming: str) -> list[Path]:
    """`adobe` gives IMG_1.xmp, `darktable` gives IMG_1.CR2.xmp, `both` gives each."""
    adobe = photo.with_suffix(".xmp")
    darktable = photo.with_name(photo.name + ".xmp")
    return {"adobe": [adobe], "darktable": [darktable], "both": [adobe, darktable]}[naming]


def _find(root: etree._Element, tag: str) -> tuple[etree._Element, str | None] | None:
    """Locate a property written either as an attribute or as a child element."""
    for desc in root.iter(DESCRIPTION):
        if tag in desc.attrib:
            return desc, desc.get(tag)
        child = desc.find(tag)
        if child is not None:
            return child, child.text
    return None


def _set(root: etree._Element, tag: str, value: str) -> None:
    """Set a property where it already lives, else on a Description that declares its namespace."""
    found = _find(root, tag)
    if found is not None and found[0].tag == DESCRIPTION:
        found[0].set(tag, value)
    elif found is not None:
        found[0].text = value
    else:
        ns, _, _name = tag[1:].partition("}")
        rdf = root.find(f"{{{NS_RDF}}}RDF")
        if rdf is None:
            raise ValueError("sidecar has no rdf:RDF element")
        target = next((d for d in rdf.iter(DESCRIPTION) if ns in d.nsmap.values()), None)
        if target is None:
            prefix = "xmp" if ns == NS_XMP else "burstwise"
            target = etree.SubElement(rdf, DESCRIPTION, nsmap={prefix: ns})
            target.set(f"{{{NS_RDF}}}about", "")
        target.set(tag, value)


def _unset(root: etree._Element, tag: str) -> None:
    """Remove a property wherever it lives."""
    for desc in root.iter(DESCRIPTION):
        desc.attrib.pop(tag, None)
        for child in desc.findall(tag):
            desc.remove(child)


def read_existing(sidecar: Path) -> tuple[int | None, str | None, bool]:
    """Rating, label and whether Burstwise wrote this sidecar (it carries a verdict)."""
    if not sidecar.exists():
        return None, None, False
    try:
        root = etree.parse(str(sidecar), PARSER).getroot()
    except etree.XMLSyntaxError:
        return None, None, False
    rating = _find(root, RATING)
    label = _find(root, LABEL)
    try:
        rating_value = int(rating[1]) if rating and rating[1] is not None else None
    except ValueError:
        rating_value = None
    ours = _find(root, f"{{{NS_BW}}}Verdict") is not None
    return rating_value, label[1] if label else None, ours


def is_protected(sidecar: Path) -> bool:
    """True when someone else already rated or labelled the photo in this sidecar."""
    rating, label, ours = read_existing(sidecar)
    return not ours and (bool(rating) or bool(label))


def clear_ours(sidecar: Path) -> bool:
    """Take back what an earlier Burstwise run wrote. Other settings in the file stay."""
    if not sidecar.exists() or not read_existing(sidecar)[2]:
        return False
    tree = etree.parse(str(sidecar), PARSER)
    root = tree.getroot()
    for tag in (RATING, LABEL, f"{{{NS_BW}}}Verdict", f"{{{NS_BW}}}Reason"):
        _unset(root, tag)
    _store(tree, sidecar)
    return True


def write_sidecar(sidecar: Path, edit: Edit, overwrite: bool = False) -> str:
    """Merge `edit` into the sidecar. Returns created, updated or skipped."""
    existed = sidecar.exists()
    ours = False
    if existed:
        if not overwrite and is_protected(sidecar):
            return "skipped"
        try:
            tree = etree.parse(str(sidecar), PARSER)
        except etree.XMLSyntaxError:
            return "skipped"
        ours = read_existing(sidecar)[2]
    else:
        tree = etree.ElementTree(etree.fromstring(NEW_SIDECAR.encode("utf-8"), PARSER))
    root = tree.getroot()
    if ours:
        for tag in (RATING, LABEL):
            _unset(root, tag)
    try:
        if edit.rating is not None:
            _set(root, RATING, str(edit.rating))
        if edit.label:
            _set(root, LABEL, edit.label)
        for key, value in (("Verdict", edit.verdict), ("Reason", edit.reason)):
            if value:
                _set(root, f"{{{NS_BW}}}{key}", value)
    except ValueError:
        return "skipped"
    _store(tree, sidecar)
    return "updated" if existed else "created"


def _store(tree: etree._ElementTree, sidecar: Path) -> None:
    data = etree.tostring(tree, xml_declaration=not _has_packet(tree), encoding="UTF-8")
    data = data.replace(b"?><x:xmpmeta", b"?>\n<x:xmpmeta").replace(
        b"</x:xmpmeta><?", b"</x:xmpmeta>\n<?"
    )
    tmp = sidecar.with_name(sidecar.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, sidecar)


def _has_packet(tree: etree._ElementTree) -> bool:
    node = tree.getroot().getprevious()
    return node is not None and node.tag is etree.ProcessingInstruction


class UndoLog:
    """Keeps the original sidecars of one run so `burstwise undo` can restore them."""

    def __init__(self, folder: Path):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.dir = folder / ".burstwise" / "undo" / stamp
        self.entries: list[dict] = []

    def remember(self, sidecar: Path) -> None:
        entry = {"path": str(sidecar), "existed": sidecar.exists()}
        if entry["existed"]:
            self.dir.mkdir(parents=True, exist_ok=True)
            backup = self.dir / f"{len(self.entries):05d}.xmp"
            shutil.copy2(sidecar, backup)
            entry["backup"] = backup.name
        self.entries.append(entry)
        self.save()

    def save(self) -> Path | None:
        if not self.entries:
            return None
        self.dir.mkdir(parents=True, exist_ok=True)
        manifest = self.dir / "manifest.json"
        manifest.write_text(json.dumps(self.entries, indent=1))
        return manifest


def undo_latest(folder: Path) -> int:
    """Restore the most recent run. Returns the number of sidecars put back or removed."""
    runs = sorted((folder / ".burstwise" / "undo").glob("*/manifest.json"))
    if not runs:
        return 0
    manifest = runs[-1]
    count = 0
    for entry in reversed(json.loads(manifest.read_text())):
        target = Path(entry["path"])
        if entry["existed"]:
            shutil.copy2(manifest.parent / entry["backup"], target)
        else:
            target.unlink(missing_ok=True)
        count += 1
    shutil.rmtree(manifest.parent)
    return count
