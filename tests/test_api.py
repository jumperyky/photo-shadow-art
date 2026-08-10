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
    res = client.post("/api/preview", json={"mode": "shadow_art", "image_id": image_id, "diameter": 150})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["image"].startswith("data:image/png;base64,")
    raw = base64.b64decode(body["image"].split(",", 1)[1])
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert body["size"]["within_print_limit"] is True


def test_preview_rectangle_uses_aspect():
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "shadow_art", "image_id": image_id, "shape": "rectangle", "aspect": 2.0,
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
        "mode": "shadow_art", "image_id": image_id, "shape": "circle", "aspect": 2.0, "diameter": 150,
    })
    size = res.json()["size"]
    assert size["outer_width_mm"] == size["outer_height_mm"]


# ------------------------------------------------------- サイズ上限 (1800mm)
def test_large_size_within_limit_has_no_warnings():
    """1800mm以内なら警告もエラーも出さずに通ること(要件)"""
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "shadow_art", "image_id": image_id, "shape": "square", "diameter": 1700,
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
        "mode": "shadow_art", "image_id": image_id, "diameter": 1800, "frame_width": 0,
        "lines": 60, "min_width": 8, "max_width": 20,
    })
    assert res.status_code == 200, res.text
    assert res.json()["warnings"] == []


def test_diameter_over_limit_is_rejected_by_validation():
    image_id = upload()
    res = client.post("/api/preview", json={"mode": "shadow_art", "image_id": image_id, "diameter": 2500})
    assert res.status_code == 422


def test_outer_size_over_limit_warns_but_succeeds():
    """枠を含めて1800mmを超えた場合は、生成はできるが警告が付くこと"""
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "shadow_art", "image_id": image_id, "diameter": 1750, "frame_width": 60,
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
        "mode": "shadow_art", "image_id": image_id, "auto_face": True, "diameter": 150,
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["applied_crop"] is None
    assert any("中央クロップ" in n for n in body["notices"])


def test_manual_crop_wins_over_auto_face():
    image_id = upload()
    crop = {"left": 0.1, "top": 0.1, "right": 0.6, "bottom": 0.6}
    res = client.post("/api/preview", json={
        "mode": "shadow_art", "image_id": image_id, "auto_face": True, "crop": crop, "diameter": 150,
    })
    assert res.json()["applied_crop"] == crop


# ------------------------------------------------------------------ バリデーション
def test_invalid_crop_is_rejected():
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "shadow_art", "image_id": image_id,
        "crop": {"left": 0.6, "top": 0.1, "right": 0.2, "bottom": 0.5},
    })
    assert res.status_code == 422


def test_max_width_below_min_width_is_rejected():
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "shadow_art", "image_id": image_id, "min_width": 3.0, "max_width": 1.0,
    })
    assert res.status_code == 422


# ---------------------------------------------------------------------- STL
def test_stl_download():
    image_id = upload()
    res = client.post("/api/stl", json={
        "mode": "shadow_art", "image_id": image_id, "shape": "rectangle", "aspect": 1.4,
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
        "mode": "shadow_art", "image_id": image_id, "diameter": 100, "lines": 20, "quality": "draft",
        "filename": "../../evil name/../x",
    })
    cd = res.headers["content-disposition"]
    assert "../" not in cd.split("filename*=")[0]


# ---------------------------------------------------------------------------
# リソフェイン
# ---------------------------------------------------------------------------
def test_config_lists_all_modes():
    cfg = client.get("/api/config").json()
    ids = [m["id"] for m in cfg["modes"]]
    assert ids == ["shadow_art", "lithophane", "keychain"]
    for m in cfg["modes"]:
        assert m["label"] and m["description"] and m["defaults"]


def test_mode_is_required():
    """
    mode を省略したリクエストは 422 で弾かれること。
    どちらの方式かを取り違えて別物を生成するより、明示させるほうが安全。
    """
    image_id = upload()
    res = client.post("/api/preview", json={"image_id": image_id, "diameter": 150})
    assert res.status_code == 422
    assert "mode" in res.text


def test_unknown_mode_is_rejected():
    image_id = upload()
    res = client.post("/api/preview", json={"mode": "hologram", "image_id": image_id})
    assert res.status_code == 422


def test_lithophane_preview():
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "lithophane", "image_id": image_id, "width": 100,
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "lithophane"
    assert body["image"].startswith("data:image/png;base64,")
    size = body["size"]
    assert size["design_width_mm"] == 100.0
    # 600x800 の画像なので高さは 133.33mm
    assert abs(size["design_height_mm"] - 133.33) < 0.1
    assert size["min_thickness_mm"] == 0.6
    assert size["max_thickness_mm"] == 3.0
    assert size["grid"] and size["face_count"] > 0
    assert size["radius_mm"] is None      # 平板


def test_lithophane_preview_reports_export_grid_not_preview_grid():
    """
    プレビューは分割数を抑えて高速に作るが、UIに出す格子と三角形数は
    STL出力時の値であること(でないとファイルサイズの目安にならない)。
    """
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "lithophane", "image_id": image_id, "width": 100,
        "samples": 900, "preview_size": 400,
    })
    size = res.json()["size"]
    assert size["grid"].startswith("900 x "), size["grid"]


def test_lithophane_projected_grid_matches_actual_export():
    """
    UIに見せる格子・三角形数が、実際にSTLを出力したときと一致すること。
    修正前は極端な縦長クロップで nz のクランプ(4800)が見積もりに入っておらず、
    「1200 x 7579」のように実際(1200 x 4800)より大きく表示されていた。
    """
    image_id = upload()
    sliver = {"left": 0.5, "top": 0.0, "right": 0.501, "bottom": 1.0}
    prev = client.post("/api/preview", json={
        "mode": "lithophane", "image_id": image_id, "crop": sliver,
        "samples": 1200,
    }).json()

    import lithophane_stl as lp
    from app import storage
    path = storage.get_path(image_id)
    litho = lp.build_lithophane(str(path), samples=1200,
                                crop_box=(0.5, 0.0, 0.501, 1.0))
    assert prev["size"]["grid"] == f"{litho.samples_x} x {litho.samples_z}"
    assert prev["size"]["face_count"] == litho.face_count


def test_lithophane_curved_reports_radius():
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "lithophane", "image_id": image_id, "width": 120, "curve": 60,
    })
    size = res.json()["size"]
    import math
    assert abs(size["radius_mm"] - 120 / math.radians(60)) < 0.05
    # 湾曲させると幅は弦まで縮み、奥行きが出る
    assert size["outer_width_mm"] < 120
    assert size["outer_depth_mm"] > 3.0


def test_lithophane_thickness_validation():
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "lithophane", "image_id": image_id,
        "min_thickness": 3.0, "max_thickness": 1.0,
    })
    assert res.status_code == 422


def test_lithophane_width_over_limit_is_rejected():
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "lithophane", "image_id": image_id, "width": 2500,
    })
    assert res.status_code == 422


def test_lithophane_auto_face_falls_back():
    res_up = client.post(
        "/api/upload",
        files={"file": ("s.png", (REPO / "samples" / "test_silhouette.png").read_bytes(),
                        "image/png")},
    )
    image_id = res_up.json()["image_id"]
    res = client.post("/api/preview", json={
        "mode": "lithophane", "image_id": image_id, "auto_face": True,
    })
    assert res.status_code == 200, res.text
    assert any("画像全体" in n for n in res.json()["notices"])


def test_lithophane_stl_is_printable():
    image_id = upload()
    res = client.post("/api/stl", json={
        "mode": "lithophane", "image_id": image_id, "width": 80,
        "samples": 120, "quality": "draft", "curve": 45,
        "filename": "リソ作品",
    })
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "model/stl"
    assert res.headers["x-mode"] == "lithophane"
    cd = res.headers["content-disposition"]
    assert 'filename="lithophane.stl"' in cd and "filename*=UTF-8''" in cd

    import trimesh

    mesh = trimesh.load(io.BytesIO(res.content), file_type="stl")
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    assert mesh.volume > 0


def test_lithophane_quality_changes_resolution():
    """品質設定で分割数が変わること"""
    image_id = upload()
    sizes = {}
    for q in ("draft", "normal"):
        res = client.post("/api/stl", json={
            "mode": "lithophane", "image_id": image_id, "width": 80,
            "samples": 160, "quality": q,
        })
        assert res.status_code == 200, res.text
        sizes[q] = len(res.content)
    assert sizes["normal"] > sizes["draft"] * 1.5, sizes


def test_shadow_art_and_lithophane_share_the_same_crop():
    """同じクロップを両方式に渡しても、それぞれ正しく反映されること"""
    image_id = upload()
    crop = {"left": 0.2, "top": 0.1, "right": 0.8, "bottom": 0.7}
    for mode in ("shadow_art", "lithophane"):
        res = client.post("/api/preview", json={
            "mode": mode, "image_id": image_id, "crop": crop,
        })
        assert res.status_code == 200, res.text
        assert res.json()["applied_crop"] == crop

    # リソフェインはクロップの比率がそのまま板の比率になる
    res = client.post("/api/preview", json={
        "mode": "lithophane", "image_id": image_id, "crop": crop, "width": 120,
    })
    size = res.json()["size"]
    # 元画像 600x800 → クロップ後 360 x 480 → 比率 4:3
    assert abs(size["design_height_mm"] - 160.0) < 0.5, size


# ---------------------------------------------------------------------------
# 3Dプレビュー用メッシュ
# ---------------------------------------------------------------------------
def _decode_mesh(content: bytes):
    """frontend/lib/mesh.ts と同じ手順でデコードする"""
    import struct

    import numpy as np

    hdr = struct.calcsize("<4sIII")
    magic, version, n_vert, n_index = struct.unpack_from("<4sIII", content, 0)
    assert magic == b"PSAM", magic
    assert version == 1
    assert len(content) == hdr + n_vert * 12 + n_index * 4, "サイズがヘッダと合わない"
    pos = np.frombuffer(content, dtype="<f4", count=n_vert * 3,
                        offset=hdr).reshape(-1, 3)
    idx = np.frombuffer(content, dtype="<u4", count=n_index, offset=hdr + n_vert * 12)
    return pos, idx


def test_mesh_shadow_art():
    image_id = upload()
    res = client.post("/api/mesh", json={
        "mode": "shadow_art", "image_id": image_id, "diameter": 150,
    })
    assert res.status_code == 200, res.text
    assert res.headers["x-mode"] == "shadow_art"
    pos, idx = _decode_mesh(res.content)
    assert len(pos) == int(res.headers["x-vertex-count"])
    assert len(idx) // 3 == int(res.headers["x-face-count"])
    assert idx.max() < len(pos), "インデックスが頂点数を超えている"


def test_mesh_is_centered_and_sits_on_bed():
    """
    ブラウザ側で座標を触らずに済むよう、XYは中心・Zは底面0で返すこと。
    ここがずれると3Dビューアでモデルが画面外に飛ぶ。
    """
    import numpy as np

    image_id = upload()
    for body in [
        {"mode": "shadow_art", "diameter": 150},
        {"mode": "shadow_art", "shape": "rectangle", "aspect": 1.6, "diameter": 150},
        {"mode": "lithophane", "width": 100},
        {"mode": "lithophane", "width": 100, "curve": 90},
    ]:
        res = client.post("/api/mesh", json={"image_id": image_id, **body})
        assert res.status_code == 200, res.text
        pos, _ = _decode_mesh(res.content)
        lo, hi = pos.min(axis=0), pos.max(axis=0)
        assert abs(lo[0] + hi[0]) < 1e-3, f"{body}: X中心がずれている"
        assert abs(lo[1] + hi[1]) < 1e-3, f"{body}: Y中心がずれている"
        assert abs(lo[2]) < 1e-4, f"{body}: Z底面が0でない"
        assert np.all(hi - lo > 0), f"{body}: 潰れている"


def test_mesh_orientation_per_mode():
    """
    印刷時の置き方が保たれること。
      シャドウアート: 寝た板 → 厚み(Z)が最も薄い
      リソフェイン  : 立った板 → 厚み(Y)が最も薄い
    ここが崩れると3Dビューアの初期カメラ向きが噛み合わなくなる。
    """
    image_id = upload()

    pos, _ = _decode_mesh(client.post("/api/mesh", json={
        "mode": "shadow_art", "image_id": image_id, "diameter": 150,
        "thickness": 2.0, "frame_thickness": 2.0,
    }).content)
    span = pos.max(axis=0) - pos.min(axis=0)
    assert span[2] < span[0] and span[2] < span[1], f"シャドウアートの向き {span}"
    assert abs(span[2] - 2.0) < 1e-3

    pos, _ = _decode_mesh(client.post("/api/mesh", json={
        "mode": "lithophane", "image_id": image_id, "width": 100,
        "max_thickness": 3.0,
    }).content)
    span = pos.max(axis=0) - pos.min(axis=0)
    assert span[1] < span[0] and span[1] < span[2], f"リソフェインの向き {span}"
    assert abs(span[1] - 3.0) < 1e-3


def test_mesh_is_much_lighter_than_stl():
    """3Dプレビュー用メッシュがSTLよりはるかに軽いこと(対話的に使えるように)"""
    image_id = upload()
    mesh = client.post("/api/mesh", json={
        "mode": "lithophane", "image_id": image_id, "width": 100, "samples": 400,
    })
    stl = client.post("/api/stl", json={
        "mode": "lithophane", "image_id": image_id, "width": 100, "samples": 400,
        "quality": "normal",
    })
    assert mesh.status_code == 200 and stl.status_code == 200
    assert len(mesh.content) < len(stl.content) / 10, (
        f"メッシュ {len(mesh.content)} / STL {len(stl.content)}"
    )


def test_mesh_respects_user_samples_as_upper_bound():
    """ユーザーが分割数を下げたら、プレビューもそれ以上には細かくしないこと"""
    image_id = upload()
    coarse = client.post("/api/mesh", json={
        "mode": "lithophane", "image_id": image_id, "samples": 40,
    })
    default = client.post("/api/mesh", json={
        "mode": "lithophane", "image_id": image_id, "samples": 400,
    })
    assert int(coarse.headers["x-face-count"]) < int(default.headers["x-face-count"])


def test_mesh_detail_levels():
    image_id = upload()
    counts = {}
    for detail in ("low", "medium"):
        res = client.post("/api/mesh", json={
            "mode": "lithophane", "image_id": image_id, "mesh_detail": detail,
        })
        assert res.status_code == 200, res.text
        counts[detail] = int(res.headers["x-face-count"])
    assert counts["low"] < counts["medium"], counts


def test_mesh_requires_mode():
    image_id = upload()
    assert client.post("/api/mesh", json={"image_id": image_id}).status_code == 422


# --------------------------------------------------------------- 表示色
def _preview_pixels(image_id, **extra):
    """プレビューPNGをデコードして (画像, 色ヒストグラム) を返す"""
    from PIL import Image as PILImage

    body = {"mode": "shadow_art", "image_id": image_id, "diameter": 150}
    body.update(extra)
    res = client.post("/api/preview", json=body)
    assert res.status_code == 200, res.text
    raw = base64.b64decode(res.json()["image"].split(",", 1)[1])
    img = PILImage.open(io.BytesIO(raw)).convert("RGB")
    # (件数, 色) の降順。先頭2色が背景色と線の色になる。
    return img, sorted(img.getcolors(maxcolors=1 << 24), reverse=True)


def test_preview_uses_requested_filament_color():
    """指定した色が実際に線の色として出ていること"""
    image_id = upload()
    _, colors = _preview_pixels(image_id, filament_color="#c0392b")
    top = {c for _, c in colors[:2]}
    assert (0xC0, 0x39, 0x2B) in top, colors[:4]


def test_preview_default_filament_is_near_black():
    image_id = upload()
    _, colors = _preview_pixels(image_id)
    top = {c for _, c in colors[:2]}
    assert (20, 20, 20) in top, colors[:4]


def test_preview_backdrop_flips_for_light_filament():
    """明るいフィラメントでは背景が暗い側に切り替わり、線が埋もれないこと"""
    from app.main import PREVIEW_BACKDROP_DARK, PREVIEW_BACKDROP_LIGHT

    image_id = upload()
    _, dark_fil = _preview_pixels(image_id, filament_color="#141414")
    _, light_fil = _preview_pixels(image_id, filament_color="#f2f0ea")

    assert PREVIEW_BACKDROP_LIGHT in {c for _, c in dark_fil[:2]}
    assert PREVIEW_BACKDROP_DARK in {c for _, c in light_fil[:2]}


def test_preview_rejects_bad_filament_color():
    image_id = upload()
    for bad in ["red", "#fff", "141414", "#12345g", "#1234567"]:
        res = client.post("/api/preview", json={
            "mode": "shadow_art", "image_id": image_id, "filament_color": bad,
        })
        assert res.status_code == 422, f"{bad} -> {res.status_code}"


def test_filament_color_does_not_change_geometry():
    """色は見た目だけの設定で、造形サイズや線の本数に影響しないこと"""
    image_id = upload()
    base = {"mode": "shadow_art", "image_id": image_id, "diameter": 150}
    a = client.post("/api/preview", json={**base, "filament_color": "#141414"}).json()
    b = client.post("/api/preview", json={**base, "filament_color": "#2c6fb5"}).json()
    assert a["size"] == b["size"]
    assert a["image"] != b["image"]


def test_lithophane_tint_follows_filament_hue():
    """リソフェインは色相だけを反映し、暗い色でも真っ黒にはならないこと"""
    from PIL import Image as PILImage

    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "lithophane", "image_id": image_id,
        "width": 80, "samples": 80, "filament_color": "#2c6fb5",
    })
    assert res.status_code == 200, res.text
    raw = base64.b64decode(res.json()["image"].split(",", 1)[1])
    img = PILImage.open(io.BytesIO(raw)).convert("RGB")
    # サンプル画像は暗部が多いので平均では判定できない。最も明るい部分
    # (=光がよく透ける薄い箇所)の色で見る。
    r, g, b = (ch[1] for ch in img.getextrema())
    assert b > g > r, (r, g, b)   # 青みが出ている
    assert b > 150, (r, g, b)     # 明るさは残っていて潰れていない


def test_lithophane_warns_about_dark_filament():
    image_id = upload()
    body = {"mode": "lithophane", "image_id": image_id, "width": 80, "samples": 80}
    dark = client.post("/api/preview", json={**body, "filament_color": "#141414"}).json()
    light = client.post("/api/preview", json={**body, "filament_color": "#f2f0ea"}).json()
    assert any("光をほとんど通しません" in n for n in dark["notices"])
    assert not any("光をほとんど通しません" in n for n in light["notices"])


def test_mesh_ignores_filament_color():
    """3Dの色はブラウザ側で塗るので、メッシュには色を送らない"""
    image_id = upload()
    res = client.post("/api/mesh", json={
        "mode": "shadow_art", "image_id": image_id, "filament_color": "#c0392b",
    })
    assert res.status_code == 200, res.text
    plain = client.post("/api/mesh", json={"mode": "shadow_art", "image_id": image_id})
    assert res.content == plain.content


# --------------------------------------------------------------- キーホルダー
def _keychain_available():
    import keychain_stl
    return keychain_stl.boolean_available()


def test_keychain_preview():
    """プレビューはブーリアンを通さないので、常に動くこと"""
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "keychain", "image_id": image_id, "shape": "hexagon",
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "keychain"
    assert body["image"].startswith("data:image/png;base64,")
    size = body["size"]
    # キーホルダー専用のフィールドが埋まっていること
    assert size["frame_thickness_mm"] == 3.0        # 最大厚み2.4 + だまり0.6
    assert size["well_depth_mm"] == 0.6
    assert size["hole_diameter_mm"] == 3.5
    assert size["resin_volume_ml"] > 0
    # 六角形は幅が √3*r なので 43.3mm。/ 0.4mmノズル = 108px
    assert size["printable_px"] == 108
    assert size["grid_px"] > 0


def test_keychain_is_not_routed_to_shadow_art():
    """
    分岐の取り違え検出。/api/preview は shadow_art を if、/api/mesh と /api/stl は
    lithophane を if にしていた名残があるので、新モードが黙って別モードとして
    処理されないことを固定する。
    """
    image_id = upload()
    for path, extra in (("/api/preview", {}),
                        ("/api/mesh", {"mesh_detail": "low"}),
                        ("/api/stl", {"quality": "draft"})):
        if path != "/api/preview" and not _keychain_available():
            continue
        res = client.post(path, json={"mode": "keychain", "image_id": image_id, **extra})
        assert res.status_code == 200, f"{path}: {res.text[:200]}"
        if path == "/api/preview":
            assert res.json()["mode"] == "keychain"
        else:
            assert res.headers.get("X-Mode") == "keychain", path


def test_keychain_well_depth_must_be_positive():
    """UIから『枠が凹凸より低い』設定を作れないこと"""
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "keychain", "image_id": image_id, "well_depth": 0,
    })
    assert res.status_code == 422


def test_keychain_rejects_bad_params():
    image_id = upload()
    for bad in ({"max_thickness": 0.3, "min_thickness": 2.0},
                {"ring_margin": 0},
                {"hole_diameter": 0},
                {"samples": 5}):
        res = client.post("/api/preview", json={
            "mode": "keychain", "image_id": image_id, **bad})
        assert res.status_code == 422, f"{bad} -> {res.status_code}"


def test_keychain_small_size_warns():
    image_id = upload()
    res = client.post("/api/preview", json={
        "mode": "keychain", "image_id": image_id, "shape": "square",
        "diameter": 30,
    })
    assert any("解像度" in w for w in res.json()["warnings"])


def test_keychain_fine_nozzle_lifts_the_size_warning():
    """
    細いノズルなら同じサイズでも解像度が足りる。
    警告のしきい値がノズル径に追従していることを固定する。
    """
    image_id = upload()
    body = {"mode": "keychain", "image_id": image_id, "shape": "square",
            "diameter": 30}
    coarse = client.post("/api/preview", json={**body, "nozzle": 0.4}).json()
    fine = client.post("/api/preview", json={**body, "nozzle": 0.2}).json()
    assert coarse["size"]["printable_px"] == 75
    assert fine["size"]["printable_px"] == 150
    assert any("解像度" in w for w in coarse["warnings"])
    assert not any("解像度" in w for w in fine["warnings"])


def test_keychain_nozzle_does_not_change_geometry():
    """ノズル径は判定にだけ使い、形状は一切変えないこと"""
    image_id = upload()
    body = {"mode": "keychain", "image_id": image_id, "shape": "square"}
    a = client.post("/api/preview", json={**body, "nozzle": 0.4}).json()["size"]
    b = client.post("/api/preview", json={**body, "nozzle": 0.2}).json()["size"]
    for key in ("outer_width_mm", "outer_height_mm", "outer_depth_mm",
                "design_width_mm", "frame_thickness_mm", "resin_volume_ml",
                "face_count", "grid_px"):
        assert a[key] == b[key], key
    assert a["printable_px"] != b["printable_px"]


def test_keychain_mesh_and_stl():
    if not _keychain_available():
        return
    image_id = upload()
    res = client.post("/api/mesh", json={
        "mode": "keychain", "image_id": image_id, "mesh_detail": "low"})
    assert res.status_code == 200, res.text
    pos, _idx = _decode_mesh(res.content)
    lo, hi = pos.min(axis=0), pos.max(axis=0)
    # 他モードと同じくXY中心・Z底面0で返ること
    assert abs(lo[0] + hi[0]) < 1e-3 and abs(lo[1] + hi[1]) < 1e-3
    assert abs(lo[2]) < 1e-4

    res = client.post("/api/stl", json={
        "mode": "keychain", "image_id": image_id, "quality": "draft"})
    assert res.status_code == 200, res.text
    assert b"keychain" in res.headers["Content-Disposition"].encode()


def test_keychain_color_does_not_change_geometry():
    image_id = upload()
    base = {"mode": "keychain", "image_id": image_id}
    a = client.post("/api/preview", json={**base, "filament_color": "#141414"}).json()
    b = client.post("/api/preview", json={**base, "filament_color": "#2c6fb5"}).json()
    assert a["size"] == b["size"]
    assert a["image"] != b["image"]


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
