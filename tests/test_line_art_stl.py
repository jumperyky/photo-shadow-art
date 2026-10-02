#!/usr/bin/env python3
"""
line_art_stl.py の回帰テスト。

    python3 -m pytest tests/ -q
    (pytest が無い環境では)  python3 tests/test_line_art_stl.py

重点は「--aspect != 1 のとき線が枠の角まで届かない」バグの回帰防止。
"""

import math
import sys
from pathlib import Path

import numpy as np
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import line_art_stl as la  # noqa: E402


SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "test_silhouette.png"


# ---------------------------------------------------------------------------
# 生成範囲(角まで届くか)
# ---------------------------------------------------------------------------
def test_cover_radius_matches_hypot():
    R = 75.0
    assert la.shape_cover_radius("circle", R) == R
    assert la.shape_cover_radius("hexagon", R) == R
    assert math.isclose(la.shape_cover_radius("square", R, 1.0), R * math.sqrt(2))
    for aspect in (0.5, 1.0, 1.6, 2.5):
        assert math.isclose(
            la.shape_cover_radius("rectangle", R, aspect),
            R * math.hypot(1.0, aspect),
        )


def _solid_coverage(shape, R, aspect, num_lines, angle_deg):
    """線を隙間なく太らせた状態の被覆範囲を返す(生成範囲の検証用)"""
    arr = np.zeros((16, 16))  # 全部黒 = 常に最大線幅
    pitch = la.compute_pitch(num_lines, R)
    cover_r = la.shape_cover_radius(shape, R, aspect)
    Rx, Ry = (R, R * aspect) if shape in ("square", "rectangle") else (R, R)
    polys = la.build_line_polygons(
        arr, Rx, Ry, cover_r, pitch, angle_deg,
        pitch / 2.0, pitch / 2.0, samples_per_line=64,
    )
    return unary_union(polys)


def test_lines_reach_every_corner():
    """
    どの shape / aspect / angle でも、線の生成範囲が枠全体を覆っていること。
    修正前は aspect > 1 の rectangle で角が欠けていた。
    """
    R = 75.0
    cases = [
        ("square", 1.0), ("rectangle", 1.6), ("rectangle", 2.5),
        ("rectangle", 0.5), ("circle", 1.0), ("hexagon", 1.0),
    ]
    for shape, aspect in cases:
        shape_poly = la.make_shape_polygon(shape, R, aspect)
        for angle in (0.0, 20.0, 45.0, 90.0, 137.0):
            covered = _solid_coverage(shape, R, aspect, 48, angle)
            missing = shape_poly.difference(covered)
            assert missing.area < shape_poly.area * 1e-6, (
                f"{shape} aspect={aspect} angle={angle}: "
                f"未被覆 {missing.area:.3f}mm^2"
            )


def test_pitch_is_independent_of_aspect():
    """線の密度(ピッチ)は aspect に依存しない = --lines の意味が変わらない"""
    R = 75.0
    assert la.compute_pitch(48, R) == la.compute_pitch(48, R)
    # 従来の定義 (2*R*1.3)/(n-1) を維持していること
    assert math.isclose(la.compute_pitch(48, R), (2 * R * 1.3) / 47)


def test_line_count_grows_with_aspect():
    """aspect を大きくすると、同じピッチのまま線の本数が自動的に増えること"""
    a1 = la.build_artwork(SAMPLE, shape="rectangle", aspect=1.0, diameter=150,
                          num_lines=48, samples_per_line=64)
    a2 = la.build_artwork(SAMPLE, shape="rectangle", aspect=2.0, diameter=150,
                          num_lines=48, samples_per_line=64)
    assert a2.line_count > a1.line_count
    assert math.isclose(a1.pitch, a2.pitch)


# ---------------------------------------------------------------------------
# 画像マッピング
# ---------------------------------------------------------------------------
def test_frame_width_is_uniform_for_rectangles():
    """
    枠の幅は aspect に関わらず一定であること。
    修正前は aspect=2 のとき上下の枠が左右の2倍の太さになっていた。
    """
    R, fw = 75.0, 10.0
    for aspect in (1.0, 1.6, 2.5):
        art = la.build_artwork(SAMPLE, shape="rectangle", aspect=aspect,
                               diameter=2 * R, frame_width=fw,
                               num_lines=16, samples_per_line=32)
        assert math.isclose(art.outer_width, 2 * R + 2 * fw, rel_tol=1e-6)
        assert math.isclose(art.outer_height, 2 * R * aspect + 2 * fw, rel_tol=1e-6)


def test_frame_ring_has_no_holes_in_design_area():
    """枠のリングがデザイン部を覆ってしまっていないこと"""
    R, fw = 75.0, 8.0
    for shape, aspect in [("square", 1.0), ("rectangle", 1.8),
                          ("circle", 1.0), ("hexagon", 1.0)]:
        art = la.build_artwork(SAMPLE, shape=shape, aspect=aspect,
                               diameter=2 * R, frame_width=fw,
                               num_lines=16, samples_per_line=32)
        design = la.make_shape_polygon(shape, R, aspect)
        assert art.frame_ring.intersection(design).area < design.area * 1e-6


def test_design_size_comes_from_real_geometry():
    """デザイン部の寸法は直径からの推定ではなく実際の形状から取ること"""
    art = la.build_artwork(SAMPLE, shape="hexagon", diameter=150, frame_width=8,
                           num_lines=16, samples_per_line=32)
    # 頂点が上下にある六角形なので、高さ=直径、幅=直径*cos(30°)
    assert math.isclose(art.design_height, 150.0, rel_tol=1e-6)
    assert math.isclose(art.design_width, 150.0 * math.cos(math.pi / 6), rel_tol=1e-6)

    rect = la.build_artwork(SAMPLE, shape="rectangle", aspect=1.6, diameter=150,
                            frame_width=8, num_lines=16, samples_per_line=32)
    assert math.isclose(rect.design_width, 150.0, rel_tol=1e-6)
    assert math.isclose(rect.design_height, 240.0, rel_tol=1e-6)


def test_zero_frame_width_is_allowed():
    art = la.build_artwork(SAMPLE, shape="circle", diameter=150, frame_width=0,
                           num_lines=16, samples_per_line=32)
    assert art.frame_ring.is_empty
    assert math.isclose(art.outer_width, 150.0, rel_tol=1e-3)


def test_isotropic_shapes_ignore_aspect():
    """
    円・六角形・n角形では aspect 指定が無視されること。
    修正前はCLI経由で --shape circle --aspect 2 のように渡すと、
    画像だけ 2:1 でクロップされて枠は等方のままなので像が歪んでいた。
    """
    for shape in ("circle", "hexagon", 8):
        a1 = la.build_artwork(SAMPLE, shape=shape, diameter=150, aspect=1.0,
                              num_lines=24, samples_per_line=64)
        a2 = la.build_artwork(SAMPLE, shape=shape, diameter=150, aspect=2.0,
                              num_lines=24, samples_per_line=64)
        assert math.isclose(a1.lines_area.area, a2.lines_area.area,
                            rel_tol=1e-9), f"{shape}: aspect指定で結果が変わった"


def test_grayscale_crop_matches_aspect():
    """読み込んだ画像の縦横比が枠の比率と一致すること(以前は常に正方形だった)"""
    for aspect in (0.5, 1.0, 1.75):
        arr = la.load_grayscale(SAMPLE, aspect=aspect)
        h, w = arr.shape
        assert abs(h / w - aspect) < 0.02, f"aspect={aspect} -> {h}/{w}"


def test_sample_bilinear_respects_separate_extents():
    """Rx と Ry が別々に効いていること"""
    arr = np.zeros((10, 10))
    arr[0, :] = 1.0  # 画像の一番上の行だけ白
    # y=+Ry が画像の上端に対応する
    top = la.sample_bilinear(arr, np.array([0.0]), np.array([100.0]), 50.0, 100.0)
    mid = la.sample_bilinear(arr, np.array([0.0]), np.array([0.0]), 50.0, 100.0)
    assert top[0] > 0.9 and mid[0] < 0.1
    # 範囲外は白扱い
    out = la.sample_bilinear(arr, np.array([0.0]), np.array([150.0]), 50.0, 100.0)
    assert out[0] == 1.0


# ---------------------------------------------------------------------------
# サイズ上限(1800mm まで警告なし)
# ---------------------------------------------------------------------------
def test_no_warning_up_to_max_print_size():
    assert la.check_print_size(1800.0, 1800.0) == []
    assert la.check_print_size(1799.9, 10.0) == []
    assert len(la.check_print_size(1801.0, 10.0)) == 1


def test_large_diameter_has_no_size_warning():
    art = la.build_artwork(SAMPLE, shape="square", diameter=1700.0,
                           frame_width=40.0, num_lines=60,
                           min_line_width=5.0, max_line_width=30.0,
                           samples_per_line=64)
    assert not any("最大造形サイズ" in w for w in art.warnings)
    assert art.outer_width <= la.MAX_PRINT_SIZE_MM


# ---------------------------------------------------------------------------
# 線幅の安全性チェック
# ---------------------------------------------------------------------------
def test_line_width_safety():
    assert la.check_line_width_safety(4.0, 0.5, 2.9) == []
    assert any("太すぎ" in w for w in la.check_line_width_safety(2.0, 0.5, 1.9))
    assert any("細すぎ" in w for w in la.check_line_width_safety(10.0, 0.1, 2.0))


# ---------------------------------------------------------------------------
# 顔検出
# ---------------------------------------------------------------------------
def test_face_crop_box_shape_and_bounds():
    """検出できる/できないに関わらず、返り値が仕様通りであること"""
    try:
        box = la.detect_face_crop_box(SAMPLE, margin=0.5, aspect=1.4)
    except la.FaceDetectionUnavailable:
        return  # OpenCV未導入の環境ではスキップ
    if box is None:
        return  # テスト画像に顔が無い場合
    l, t, r, b = box
    assert 0.0 <= l < r <= 1.0 and 0.0 <= t < b <= 1.0


def test_face_is_actually_detected():
    """合成顔画像で実際に顔が検出されること(検出パイプラインの生存確認)"""
    img = synthetic_face()
    try:
        faces, (W, H) = la.detect_faces(img)
    except la.FaceDetectionUnavailable:
        return
    assert faces, "合成顔画像で顔が1つも検出されなかった"
    x, y, w, h = faces[0]
    assert 0 <= x < W and 0 <= y < H and w > 0 and h > 0


def test_face_crop_box_respects_aspect():
    """合成した顔画像でクロップ比率が aspect に一致すること"""
    img = synthetic_face()
    for aspect in (0.8, 1.0, 1.5):
        try:
            box = la.detect_face_crop_box(img, margin=0.4, aspect=aspect)
        except la.FaceDetectionUnavailable:
            return
        assert box is not None
        l, t, r, b = box
        W, H = img.size
        got = ((b - t) * H) / ((r - l) * W)
        assert abs(got - aspect) < 0.05, f"aspect {aspect} のはずが {got:.3f}"


def test_face_crop_box_centers_on_face():
    """クロップ範囲が顔をきちんと含んでいること"""
    img = synthetic_face()
    try:
        faces, (W, H) = la.detect_faces(img)
        box = la.detect_face_crop_box(img, margin=0.5, aspect=1.0)
    except la.FaceDetectionUnavailable:
        return
    assert faces and box
    l, t, r, b = box
    x, y, w, h = faces[0]
    assert l * W <= x and r * W >= x + w, "顔が左右にはみ出している"
    assert t * H <= y and b * H >= y + h, "顔が上下にはみ出している"


def synthetic_face(W=600, H=800):
    """
    顔検出のテスト用に、Haar分類器が反応する明暗構造
    (明るい額・頬/暗い眉・目・口/明るい鼻筋)を持つ合成顔画像を作る。
    実在の人物写真ではない。
    """
    from PIL import Image, ImageDraw, ImageFilter
    img = Image.new("L", (W, H), 150)
    d = ImageDraw.Draw(img)
    cx, cy, fw, fh = W // 2, int(H * 0.45), 190, 250

    d.ellipse((cx - fw // 2, cy - fh // 2, cx + fw // 2, cy + fh // 2), fill=205)
    d.ellipse((cx - fw // 2 + 10, cy - fh // 2 + 5, cx + fw // 2 - 10, cy - 30), fill=215)
    d.rectangle((cx - 70, cy - 58, cx - 18, cy - 46), fill=60)   # 左眉
    d.rectangle((cx + 18, cy - 58, cx + 70, cy - 46), fill=60)   # 右眉
    d.ellipse((cx - 66, cy - 38, cx - 24, cy - 14), fill=55)     # 左目
    d.ellipse((cx + 24, cy - 38, cx + 66, cy - 14), fill=55)     # 右目
    d.ellipse((cx - 80, cy - 5, cx - 20, cy + 55), fill=222)     # 左頬
    d.ellipse((cx + 20, cy - 5, cx + 80, cy + 55), fill=222)     # 右頬
    d.rectangle((cx - 9, cy - 40, cx + 9, cy + 25), fill=225)    # 鼻筋
    d.ellipse((cx - 16, cy + 18, cx + 16, cy + 38), fill=175)    # 鼻先
    d.ellipse((cx - 38, cy + 62, cx + 38, cy + 86), fill=95)     # 口
    d.rectangle((cx - 38, cy + 72, cx + 38, cy + 76), fill=70)
    d.ellipse((cx - fw // 2 + 15, cy + fh // 2 - 45,
               cx + fw // 2 - 15, cy + fh // 2 + 5), fill=185)   # 顎の影
    return img.filter(ImageFilter.GaussianBlur(3))


# ---------------------------------------------------------------------------
# 生成物
# ---------------------------------------------------------------------------
def test_mesh_is_manifold_when_thicknesses_match():
    """
    厚みが同じなら、線と枠の境界が非多様体エッジにならないこと。
    (別々に押し出して concatenate すると4面が1辺を共有してしまう)
    """
    import collections

    for shape, aspect in [("circle", 1.0), ("hexagon", 1.0),
                          ("square", 1.0), ("rectangle", 1.6)]:
        mesh = la.generate_stl(SAMPLE, None, shape=shape, aspect=aspect,
                               diameter=150, num_lines=32, thickness=2.0,
                               frame_thickness=2.0, samples_per_line=80,
                               verbose=False)
        counts = collections.Counter(map(tuple, mesh.edges_sorted))
        open_edges = sum(1 for v in counts.values() if v == 1)
        nonmanifold = sum(1 for v in counts.values() if v > 2)
        assert open_edges == 0, f"{shape}: 開いた辺が {open_edges} 本"
        assert nonmanifold == 0, f"{shape}: 非多様体の辺が {nonmanifold} 本"
        assert mesh.is_watertight, f"{shape}: watertight でない"


def test_mesh_still_builds_with_different_thicknesses():
    """厚みが異なる場合(線と枠に段差をつける場合)も生成できること"""
    mesh = la.generate_stl(SAMPLE, None, shape="circle", diameter=150,
                           num_lines=24, thickness=2.0, frame_thickness=4.0,
                           samples_per_line=64, verbose=False)
    assert mesh.volume > 0
    assert mesh.bounds[1][2] == 4.0  # 枠の厚みぶん高くなっている


def test_generate_stl_watertight_ish():
    mesh = la.generate_stl(SAMPLE, None, shape="rectangle", aspect=1.4,
                           diameter=150, num_lines=32, samples_per_line=80,
                           verbose=False)
    assert len(mesh.faces) > 0
    assert mesh.volume > 0


def test_preview_image_matches_outer_aspect():
    art = la.build_artwork(SAMPLE, shape="rectangle", aspect=2.0, diameter=150,
                           num_lines=32, samples_per_line=64)
    img = la.render_preview_image(art, size=400)
    w, h = img.size
    assert abs((h / w) - (art.outer_height / art.outer_width)) < 0.02


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
