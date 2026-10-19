"""Tests for the lab-review API behind the light-box web app (api/lab.py)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from bacterioscope.api import lab
from bacterioscope.api.routes import app

_SAMPLE = "plate_mixed_sir"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def plate(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/plates", data={"sample_id": _SAMPLE})
    assert response.status_code == 200
    return response.json()


@pytest.fixture(autouse=True)
def _no_live_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    monkeypatch.setattr(lab, "_models", None)


class TestWebApp:
    def test_root_serves_html_with_csp(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        csp = response.headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "unsafe-inline" not in csp

    def test_static_assets_are_served(self, client: TestClient) -> None:
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/app.css").status_code == 200

    def test_legacy_analyze_route_still_exists(self, client: TestClient) -> None:
        assert any(getattr(r, "path", "") == "/analyze" for r in app.routes)


class TestSamples:
    def test_lists_synthetic_samples_with_disk_counts(self, client: TestClient) -> None:
        samples = {s["id"]: s for s in client.get("/api/samples").json()}
        assert samples[_SAMPLE]["synthetic"] is True
        assert samples[_SAMPLE]["disks"] == 6

    def test_unknown_sample_image_is_404(self, client: TestClient) -> None:
        assert client.get("/api/samples/..%2Fpyproject/image").status_code == 404

    def test_sample_image_is_served(self, client: TestClient) -> None:
        response = client.get(f"/api/samples/{_SAMPLE}/image")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"


class TestAnalyze:
    def test_geometry_payload(self, plate: dict[str, Any]) -> None:
        assert plate["image"] == {"width": 540, "height": 540}
        assert len(plate["disks"]) == 6
        rim = plate["calibration"]["plate"]
        assert abs(rim["r"] - 252) < 6
        disk = plate["disks"][0]
        assert {"center", "zone_radius", "diameter_mm", "flags", "contour"} <= disk.keys()
        assert len(disk["contour"]) >= 3

    def test_sample_layout_labels_every_disk(self, plate: dict[str, Any]) -> None:
        assert len(plate["suggested_labels"]) == 6
        assert all(plate["suggested_labels"])

    def test_requires_image_or_sample(self, client: TestClient) -> None:
        assert client.post("/api/plates").status_code == 422

    def test_rejects_unsupported_media(self, client: TestClient) -> None:
        files = {"image": ("note.txt", b"not an image", "text/plain")}
        assert client.post("/api/plates", files=files).status_code == 415

    def test_unknown_analysis_is_404(self, client: TestClient) -> None:
        response = client.post("/api/plates/nope/classify", json={"labels": []})
        assert response.status_code == 404


class TestClassify:
    def test_correction_changes_category_and_is_traced(
        self, client: TestClient, plate: dict[str, Any]
    ) -> None:
        labels = plate["suggested_labels"]
        body = {"labels": labels, "overrides": {"0": 35.0}}
        result = client.post(f"/api/plates/{plate['analysis_id']}/classify", json=body).json()
        first = result["disks"][0]
        assert first["corrected"] is True
        assert first["diameter_mm"] == 35.0
        assert first["category"] == "S"
        assert result["corrections"] == 1
        reset = {"labels": labels, "overrides": {}}
        client.post(f"/api/plates/{plate['analysis_id']}/classify", json=reset)

    def test_unassigned_disk_is_unknown(self, client: TestClient, plate: dict[str, Any]) -> None:
        body = {"labels": [None] * 6, "overrides": {}}
        result = client.post(f"/api/plates/{plate['analysis_id']}/classify", json=body).json()
        assert {d["category"] for d in result["disks"]} == {"UNKNOWN"}
        client.post(
            f"/api/plates/{plate['analysis_id']}/classify",
            json={"labels": plate["suggested_labels"], "overrides": {}},
        )

    def test_wrong_label_count_is_422(self, client: TestClient, plate: dict[str, Any]) -> None:
        response = client.post(
            f"/api/plates/{plate['analysis_id']}/classify", json={"labels": ["meropenem"]}
        )
        assert response.status_code == 422

    def test_out_of_range_correction_is_422(
        self, client: TestClient, plate: dict[str, Any]
    ) -> None:
        body = {"labels": plate["suggested_labels"], "overrides": {"0": 500.0}}
        response = client.post(f"/api/plates/{plate['analysis_id']}/classify", json=body)
        assert response.status_code == 422


class TestPanel:
    def test_unknown_panel_is_404(self, client: TestClient, plate: dict[str, Any]) -> None:
        response = client.post(f"/api/plates/{plate['analysis_id']}/panel", json={"name": "x"})
        assert response.status_code == 404

    def test_mismatched_disk_count_is_422(self, client: TestClient, plate: dict[str, Any]) -> None:
        response = client.post(
            f"/api/plates/{plate['analysis_id']}/panel", json={"name": "enterobacteria_clsi_12"}
        )
        assert response.status_code == 422
        assert "12 positions" in response.json()["detail"]

    def test_matching_panel_assigns_labels(
        self, client: TestClient, plate: dict[str, Any]
    ) -> None:
        response = client.post(
            f"/api/plates/{plate['analysis_id']}/panel", json={"name": "enterobacteria_clsi_6"}
        )
        assert response.status_code == 200
        assert len(response.json()["labels"]) == 6


class TestReview:
    def test_corrections_block_the_review(self, client: TestClient, plate: dict[str, Any]) -> None:
        analysis = plate["analysis_id"]
        client.post(
            f"/api/plates/{analysis}/classify",
            json={"labels": plate["suggested_labels"], "overrides": {"1": 30.0}},
        )
        response = client.post(
            f"/api/plates/{analysis}/review", json={"organism": "Escherichia coli", "alerts": False}
        )
        assert response.status_code == 409
        client.post(
            f"/api/plates/{analysis}/classify",
            json={"labels": plate["suggested_labels"], "overrides": {}},
        )

    def test_without_provider_key_returns_deterministic_fallback(
        self, client: TestClient, plate: dict[str, Any]
    ) -> None:
        analysis = plate["analysis_id"]
        client.post(
            f"/api/plates/{analysis}/classify",
            json={"labels": plate["suggested_labels"], "overrides": {}},
        )
        response = client.post(
            f"/api/plates/{analysis}/review", json={"organism": "Escherichia coli", "alerts": False}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "fallback"
        assert body["fallback_reason"] == "token_factory_unavailable"
        assert len(body["report"]["measurement"]["observations"]) == 6
        assert body["report"]["requires_human_review"] is True
