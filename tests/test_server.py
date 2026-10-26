import pytest
from fastapi.testclient import TestClient

from burstwise.server import Session, create_app

LOCAL = {"base_url": "http://127.0.0.1:8765"}


@pytest.fixture
def client(library, monkeypatch, tmp_path):
    monkeypatch.setenv("BURSTWISE_HOME", str(tmp_path / "home"))
    session = Session(library.folder, library.settings, use_gpu=False)
    session.library = library
    session.job["state"] = "done"
    return TestClient(create_app(session), **LOCAL)


def test_state_lists_photos_groups_and_counts(client, library):
    state = client.get("/api/state").json()
    assert len(state["photos"]) == 4 and len(state["groups"]) == 2
    assert state["counts"] == library.counts()
    assert {"id", "name", "state", "reasons", "problems", "faces"} <= set(state["photos"][0])


def test_decision_is_validated_and_persisted(client, library):
    pid = library.photos[1].id
    ok = client.put(f"/api/decision/{pid}", json={"state": "pick", "rating": 5, "label": "Blue"})
    assert ok.json()["decisions"][pid] == {"state": "pick", "rating": 5, "label": "Blue"}
    assert (library.folder / ".burstwise" / "decisions.json").exists()
    client.put(f"/api/decision/{pid}", json={"state": "bogus", "rating": 99, "label": "Pink"})
    assert client.get("/api/state").json()["decisions"] == {}


def test_unknown_photo_is_404(client):
    assert client.put("/api/decision/nope", json={"state": "pick"}).status_code == 404
    assert client.get("/api/thumb/nope").status_code == 404


def test_thumbnail_is_a_jpeg(client, library):
    res = client.get(f"/api/thumb/{library.photos[0].id}?size=200")
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"


def test_foreign_host_name_is_refused(client):
    res = client.get("/api/state", headers={"host": "evil.example:8765"})
    assert res.status_code == 403


def test_cross_origin_write_is_refused_and_changes_nothing(client, library):
    res = client.post(
        "/api/xmp",
        json={"naming": "both"},
        headers={"origin": "http://evil.example"},
    )
    assert res.status_code == 403
    assert not list(library.folder.glob("*.xmp"))


def test_same_origin_write_works_and_can_be_undone(client, library):
    res = client.post("/api/xmp", json={"naming": "adobe"}, headers={"origin": LOCAL["base_url"]})
    assert res.json()["tally"]["created"] == 3
    assert len(list(library.folder.glob("*.xmp"))) == 3
    assert client.post("/api/undo").json() == {"restored": 3}
    assert not list(library.folder.glob("*.xmp"))


def test_bad_naming_is_400(client):
    assert client.post("/api/xmp", json={"naming": "../x"}).status_code == 400


def test_xmp_preview_matches_the_decision(client, library):
    pid = library.photos[0].id
    client.put(f"/api/decision/{pid}", json={"state": "reject"})
    edit = client.get(f"/api/xmp-preview/{pid}").json()["edit"]
    assert edit["rating"] == -1


def test_settings_regroup_without_reanalysis(client):
    state = client.post("/api/settings", json={"similarity": 0.9999}).json()
    assert len(state["groups"]) == 4
    assert state["settings"]["similarity"] == 0.9999


def test_export_copies_picks(client, tmp_path):
    dest = tmp_path / "keep"
    res = client.post("/api/export", json={"dest": str(dest)}).json()
    assert res["copied"] == 2 and len(list(dest.glob("*.JPG"))) == 2
    assert client.post("/api/export", json={}).status_code == 400


def test_locales_endpoint_lists_nine(client):
    assert len(client.get("/api/locales").json()) == 9


def test_page_is_served(client):
    assert "Burstwise" in client.get("/").text


def test_settings_are_validated(client):
    assert client.post("/api/settings", json={"pick_stars": 99}).status_code == 400
    assert client.post("/api/settings", json={"similarity": "high"}).status_code == 400
    assert client.post("/api/settings", json={"pick_label": "Pink"}).status_code == 400
    assert client.post("/api/settings", json=[1, 2]).status_code == 400
    assert client.post("/api/settings", content=b"nope").status_code == 400
    assert client.post("/api/settings", json={"similarity": 0.9}).status_code == 200
