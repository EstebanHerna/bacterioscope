"""Tests for the BacterioScope FastAPI endpoints."""

from __future__ import annotations

import io

import cv2
import numpy as np
from fastapi.testclient import TestClient

from bacterioscope.api.routes import app

client = TestClient(app, raise_server_exceptions=False)


def _encode_image(size: int = 300, fmt: str = ".png") -> bytes:
    img = np.zeros((size, size, 3), dtype=np.uint8)
    img[:] = [148, 185, 210]
    cv2.circle(img, (size // 2, size // 2), size // 4, (220, 220, 215), -1)
    _, buf = cv2.imencode(fmt, img)
    return buf.tobytes()


class TestHealth:
    def test_returns_200(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_status_is_ok(self) -> None:
        response = client.get("/health")
        assert response.json()["status"] == "ok"

    def test_version_present(self) -> None:
        response = client.get("/health")
        assert "version" in response.json()


class TestAnalyzeValid:
    def test_valid_png_returns_200(self) -> None:
        response = client.post(
            "/analyze",
            files={"image": ("plate.png", io.BytesIO(_encode_image()), "image/png")},
        )
        assert response.status_code == 200

    def test_valid_jpeg_returns_200(self) -> None:
        jpg = _encode_image(fmt=".jpg")
        response = client.post(
            "/analyze",
            files={"image": ("plate.jpg", io.BytesIO(jpg), "image/jpeg")},
        )
        assert response.status_code == 200

    def test_response_has_required_fields(self) -> None:
        response = client.post(
            "/analyze",
            files={"image": ("plate.png", io.BytesIO(_encode_image()), "image/png")},
        )
        data = response.json()
        assert "px_per_mm" in data
        assert "disk_count" in data
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_px_per_mm_positive(self) -> None:
        response = client.post(
            "/analyze",
            files={"image": ("plate.png", io.BytesIO(_encode_image()), "image/png")},
        )
        assert response.json()["px_per_mm"] > 0.0


class TestAnalyzeRejections:
    def test_pdf_content_type_returns_415(self) -> None:
        response = client.post(
            "/analyze",
            files={"image": ("doc.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
        assert response.status_code == 415

    def test_text_content_type_returns_415(self) -> None:
        response = client.post(
            "/analyze",
            files={"image": ("data.csv", io.BytesIO(b"a,b,c"), "text/csv")},
        )
        assert response.status_code == 415

    def test_corrupted_bytes_returns_422(self) -> None:
        response = client.post(
            "/analyze",
            files={"image": ("bad.png", io.BytesIO(b"not-an-image"), "image/png")},
        )
        assert response.status_code == 422

    def test_oversized_image_returns_413(self) -> None:
        big = b"\x00" * (51 * 1024 * 1024)
        response = client.post(
            "/analyze",
            files={"image": ("huge.png", io.BytesIO(big), "image/png")},
        )
        assert response.status_code == 413

    def test_error_detail_does_not_expose_traceback(self) -> None:
        response = client.post(
            "/analyze",
            files={"image": ("bad.png", io.BytesIO(b"garbage"), "image/png")},
        )
        body = response.text
        assert "Traceback" not in body
        assert "File " not in body
