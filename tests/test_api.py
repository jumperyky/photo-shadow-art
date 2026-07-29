#!/usr/bin/env python3
"""
backend/app/main.py のAPIテスト。

    python3 -m pytest tests/test_api.py -q
    (pytest が無い環境では)  python3 tests/test_api.py

サーバーを別途起動する必要はない(FastAPIのTestClientを使う)。
"""

import base64
import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SAMPLE = REPO / "samples" / "test_face.png"
client = TestClient(app)


def upload() -> str:
    res = client.post(
        "/api/upload",
        files={"file": ("test_face.png", SAMPLE.read_bytes(), "image/png")},
    )
    assert res.status_code == 200, res.text
    return res.json()["image_id"]


# ---------------------------------------------------------------------------
def test_health_and_config():
    assert client.get("/api/health").json()["status"] == "ok"
    cfg = client.get("/api/config").json()
    assert cfg["max_print_size_mm"] == 1800.0
    assert set(cfg["shapes"]) == {"square", "rectangle", "circle", "hexagon"}


def test_upload_and_fetch_image():
    image_id = upload()
    res = client.get(f"/api/images/{image_id}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"


def test_upload_rejects_non_image():
    res = client.post("/api/upload", files={"file": ("x.txt", b"not an image", "text/plain")})
    assert res.status_code == 400


def test_unknown_image_id_is_404():
    assert client.get("/api/images/" + "0" * 32).status_code == 404


def test_image_id_traversal_is_rejected():
    """パス・トラバーサルを試すIDが通らないこと"""
    for bad in ["../../etc/passwd", "..%2f..%2fetc", "abc", "z" * 32]:
        res = client.get(f"/api/images/{bad}")
        assert res.status_code in (404, 400, 422), f"{bad} -> {res.status_code}"


def test_preview_returns_png_data_url():
    image_id = upload()
    res = client.post("/api/preview", json={"image_id": image_id, "diameter": 150})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["image"].startswith("data:image/png;base64,")
    raw = base64.b64decode(body["image"].split(",", 1)[1])
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert body["size"]["within_print_limit"] is True


def test_preview_rectangle_uses_aspect():
    image_id = upload()
    res = client.post("/api/preview", json={
        "image_id": image_id, "shape": "rectangle", "aspect": 2.0,
        "diameter": 150, "frame_width": 10,
    })
    size = res.json()["size"]
    assert size["design_width_mm"] == 150.0
    assert size["design_height_mm"] == 300.0
    assert size["outer_width_mm"] == 170.0
    assert size["outer_height_mm"] == 320.0


def test_circle_ignores_aspect():
    """円は等方なので aspect を送っても縦長にならないこと"""
    image_id = upload()
    res = client.post("/api/preview", json={
        "image_id": image_id, "shape": "circle", "aspect": 2.0, "diameter": 150,
    })
    size = res.json()["size"]
    assert size["outer_width_mm"] == size["outer_height_mm"]


# ------------------------------------------------------- サイズ上限 (1800mm)
def test_large_size_within_limit_has_no_warnings():
    """1800mm以内なら警告もエラーも出さずに通ること(要件)"""
    image_id = upload()
    res = client.post("/api/preview", json={
        "image_id": image_id, "shape": "square", "diameter": 1700,
        "frame_width": 45, "lines": 90, "min_width": 6, "max_width": 16,
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["warnings"] == [], body["warnings"]
    assert body["size"]["outer_width_mm"] == 1790.0
    assert body["size"]["within_print_limit"] is True


def test_diameter_at_exact_limit_is_accepted():
    image_id = upload()
    res = client.post("/api/preview", json={
        "image_id": image_id, "diameter": 1800, "frame_width": 0,
        "lines": 60, "min_width": 8, "max_width": 20,
    })
    assert res.status_code == 200, res.text
    assert res.json()["warnings"] == []


def test_diameter_over_limit_is_rejected_by_validation():
    image_id = upload()
    res = client.post("/api/preview", json={"image_id": image_id, "diameter": 2500})
    assert res.status_code == 422


def test_outer_size_over_limit_warns_but_succeeds():
    """枠を含めて1800mmを超えた場合は、生成はできるが警告が付くこと"""
    image_id = upload()
    res = client.post("/api/preview", json={
        "image_id": image_id, "diameter": 1750, "frame_width": 60,
        "lines": 60, "min_width": 8, "max_width": 20,
    })
    assert res.status_code == 200
    body = res.json()
    assert body["size"]["within_print_limit"] is False
    assert any("最大造形サイズ" in w for w in body["warnings"])


# ------------------------------------------------------------------- 顔検出
def test_detect_face():
    image_id = upload()
    res = client.post("/api/detect-face", json={
        "image_id": image_id, "aspect": 1.4, "margin": 0.5,
    })
    body = res.json()
    assert res.status_code == 200
    if not body["available"]:
        return  # OpenCV未導入の環境
    assert body["detected"] is True
    assert body["faces"]
    crop = body["crop"]
    assert 0 <= crop["left"] < crop["right"] <= 1
    assert 0 <= crop["top"] < crop["bottom"] <= 1


def test_auto_face_falls_back_without_error():
    """顔のない画像で auto_face を使ってもエラーにならず、理由が notices に載ること"""
    image_id_res = client.post(
        "/api/upload",
        files={"file": ("s.png", (REPO / "samples" / "test_silhouette.png").read_bytes(),
                        "image/png")},
    )
    image_id = image_id_res.json()["image_id"]
    res = client.post("/api/preview", json={
        "image_id": image_id, "auto_face": True, "diameter": 150,
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["applied_crop"] is None
    assert any("中央クロップ" in n for n in body["notices"])


def test_manual_crop_wins_over_auto_face():
    image_id = upload()
    crop = {"left": 0.1, "top": 0.1, "right": 0.6, "bottom": 0.6}
    res = client.post("/api/preview", json={
        "image_id": image_id, "auto_face": True, "crop": crop, "diameter": 150,
    })
    assert res.json()["applied_crop"] == crop


# ------------------------------------------------------------------ バリデーション
def test_invalid_crop_is_rejected():
    image_id = upload()
    res = client.post("/api/preview", json={
        "image_id": image_id,
        "crop": {"left": 0.6, "top": 0.1, "right": 0.2, "bottom": 0.5},
    })
    assert res.status_code == 422


def test_max_width_below_min_width_is_rejected():
    image_id = upload()
    res = client.post("/api/preview", json={
        "image_id": image_id, "min_width": 3.0, "max_width": 1.0,
    })
    assert res.status_code == 422


# ---------------------------------------------------------------------- STL
def test_stl_download():
    image_id = upload()
    res = client.post("/api/stl", json={
        "image_id": image_id, "shape": "rectangle", "aspect": 1.4,
        "diameter": 150, "lines": 30, "quality": "draft",
        "filename": "テスト作品",
    })
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "model/stl"
    cd = res.headers["content-disposition"]
    # 非ASCIIのファイル名はUTF-8エンコードで、ASCIIフォールバックも併記される
    assert "filename=" in cd and "filename*=UTF-8''" in cd
    assert len(res.content) > 1000

    import trimesh

    mesh = trimesh.load(io.BytesIO(res.content), file_type="stl")
    assert mesh.volume > 0
    assert mesh.is_watertight


def test_stl_filename_is_sanitized():
    image_id = upload()
    res = client.post("/api/stl", json={
        "image_id": image_id, "diameter": 100, "lines": 20, "quality": "draft",
        "filename": "../../evil name/../x",
    })
    cd = res.headers["content-disposition"]
    assert "../" not in cd.split("filename*=")[0]


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{'OK' if failures == 0 else f'{failures} failed'}")
    sys.exit(1 if failures else 0)
