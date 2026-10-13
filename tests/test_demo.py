"""The demo server, exercised over the offline pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from rlr.agent import Pipeline

fastapi = pytest.importorskip("fastapi")


@pytest.fixture
def client(pipeline: Pipeline) -> TestClient:
    from fastapi.testclient import TestClient

    from rlr.demo.server import create_app

    app = create_app(pipeline.settings)
    app.state.get_pipeline = lambda: pipeline
    return TestClient(app)


def test_index_and_static(client: TestClient) -> None:
    assert client.get("/").status_code == 200
    assert "Related Languages" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_status(client: TestClient) -> None:
    body = client.get("/api/status").json()
    assert body["languages_with_bibles"] == 4
    assert body["mt_backend"] == "none"


def test_languages_endpoint(client: TestClient) -> None:
    body = client.get("/api/languages", params={"target": "ngq", "lwc": "swh"}).json()
    assert body["target"]["name"] == "Ngoreme"
    assert body["lwc"]["code"] == "swh"
    assert [r["code"] for r in body["related"]] == ["reg", "wbi", "zga"]
    assert body["related"][0]["editions"][0]["provenance"]["license_name"] == "CC BY-SA 4.0"
    assert client.get("/api/languages", params={"target": "zzz"}).status_code == 404


def test_brief_endpoint(client: TestClient) -> None:
    r = client.get("/api/brief", params={"target": "ngq", "lwc": "swh", "passage": "MRK 1:6"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["passage_label"] == "MRK 1:6"
    assert body["lwc_reading"]["language"] == "swh"
    assert body["lwc_reading"]["text"].startswith("swh 1:6")
    assert body["readings"][0]["original"]["text"] == "reg 1:6 camel hair"
    assert body["readings"][0]["in_lwc"] is None  # Swahili has an open Bible; nothing to render
    assert body["notes"][0]["note"]["figure"]["label"] == "Metaphor"
    bad = client.get("/api/brief", params={"target": "ngq", "lwc": "swh", "passage": "Mark"})
    assert bad.status_code == 400


def test_brief_honours_exclusions(client: TestClient) -> None:
    r = client.get(
        "/api/brief",
        params={"target": "ngq", "lwc": "swh", "passage": "MRK 1:6", "exclude": "reg, swh"},
    )
    assert [x["language"]["code"] for x in r.json()["readings"]] == ["wbi"]


def test_brief_honours_inclusions(client: TestClient) -> None:
    r = client.get(
        "/api/brief",
        params={
            "target": "ngq",
            "lwc": "swh",
            "passage": "MRK 1:2",
            "include": "zga",
            "min_similarity": "0.99",
        },
    )
    body = r.json()
    assert [x["language"]["code"] for x in body["readings"]] == ["zga"]
    assert body["readings"][0]["language"]["requested"] is True
    langs = client.get(
        "/api/languages", params={"target": "ngq", "include": "zga", "min_similarity": "0.99"}
    ).json()
    assert [x["code"] for x in langs["related"]] == ["zga"]
