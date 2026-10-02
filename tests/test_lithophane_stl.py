#!/usr/bin/env python3
"""
lithophane_stl.py の回帰テスト。

    python3 -m pytest tests/test_lithophane_stl.py -q
    (pytest が無い環境では)  python3 tests/test_lithophane_stl.py

重点はメッシュの健全性(水密・面の向き・寸法)と、厚みマッピングの正しさ。
"""

import collections
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lithophane_stl as lp  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "test_face.png"


def ramp_image(w=256, h=128):
    """左から右へ 黒→白 の連続階調。階調マッピングの検証用。"""
    g = np.tile(np.linspace(0, 255, w, dtype=np.uint8)[None, :], (h, 1))
    return Image.fromarray(g, "L")


# ---------------------------------------------------------------------------
# 厚みマッピング
# ---------------------------------------------------------------------------
def test_thickness_spans_requested_range():
    lit = lp.build_lithophane(ramp_image(), width_mm=100, samples=64,
                              min_thickness=0.6, max_thickness=3.0, gamma=1.0)
    assert math.isclose(lit.thickness.min(), 0.6, abs_tol=1e-6)
    assert math.isclose(lit.thickness.max(), 3.0, abs_tol=1e-6)


def test_dark_is_thick_by_default():
    """既定(裏から照らす)では暗い所ほど厚いこと"""
    lit = lp.build_lithophane(ramp_image(), width_mm=100, samples=64, gamma=1.0)
    row = lit.thickness[lit.samples_z // 2]
    assert row[0] > row[-1], "左(黒)が右(白)より厚くない"
    # 単調に薄くなる
    assert np.all(np.diff(row) <= 1e-9)


def test_positive_inverts_thickness():
    """--positive で明るい所が厚くなること"""
    lit = lp.build_lithophane(ramp_image(), width_mm=100, samples=64,
                              gamma=1.0, positive=True)
    row = lit.thickness[lit.samples_z // 2]
    assert row[0] < row[-1], "positive でも左(黒)のほうが厚い"


def test_gamma_below_one_thins_midtones():
    """gamma<1 で中間調が薄くなる(=明るく抜ける)こと"""
    mid = []
    for g in (1.0, 0.5):
        lit = lp.build_lithophane(ramp_image(), width_mm=100, samples=64, gamma=g)
        row = lit.thickness[lit.samples_z // 2]
        mid.append(row[len(row) // 2])
    assert mid[1] < mid[0], f"gamma=0.5 の中間調が薄くなっていない {mid}"


def test_max_below_min_is_rejected():
    try:
        lp.build_lithophane(SAMPLE, min_thickness=3.0, max_thickness=1.0, samples=32)
    except ValueError:
        return
    raise AssertionError("最大厚み<最小厚み が通ってしまった")


# ---------------------------------------------------------------------------
# 寸法
# ---------------------------------------------------------------------------
def test_height_follows_image_aspect():
    lit = lp.build_lithophane(ramp_image(w=200, h=100), width_mm=100, samples=64)
    assert math.isclose(lit.height_mm, 50.0, rel_tol=1e-6)


def test_flat_footprint_and_bounds():
    lit = lp.build_lithophane(ramp_image(w=200, h=100), width_mm=100, samples=64,
                              min_thickness=0.6, max_thickness=3.0)
    fw, fh, fd = lit.footprint()
    assert math.isclose(fw, 100.0, rel_tol=1e-6)
    assert math.isclose(fh, 50.0, rel_tol=1e-6)
    assert math.isclose(fd, 3.0, rel_tol=1e-6)

    mesh = lp.build_mesh(lit, validate=True)
    span = mesh.bounds[1] - mesh.bounds[0]
    assert math.isclose(span[0], 100.0, rel_tol=1e-6)   # X = 幅
    assert math.isclose(span[1], 3.0, rel_tol=1e-6)     # Y = 厚み
    assert math.isclose(span[2], 50.0, rel_tol=1e-6)    # Z = 高さ


def test_curved_radius_matches_arc_length():
    """湾曲時、弧の長さが width と一致すること(R = W / θ)"""
    for deg in (30.0, 60.0, 120.0, 180.0):
        lit = lp.build_lithophane(ramp_image(), width_mm=120, samples=48,
                                  curve_deg=deg)
        expected_r = 120.0 / math.radians(deg)
        assert math.isclose(lit.radius_mm, expected_r, rel_tol=1e-9)
        # 弧長 = R * θ が width に戻る
        assert math.isclose(lit.radius_mm * math.radians(deg), 120.0, rel_tol=1e-9)


def test_footprint_matches_actual_mesh_bounds():
    """
    footprint() の値が実メッシュのバウンディングボックスと一致すること。
    修正前は 180度超の湾曲で、外周端の沈み込みを内面半径で計算していたため
    奥行きが最大3mm過小だった(350度で 42.2mm と報告、実際は 45.2mm)。
    """
    for deg in (0.0, 60.0, 180.0, 270.0, 350.0):
        lit = lp.build_lithophane(SAMPLE, width_mm=120, samples=60, curve_deg=deg)
        mesh = lp.build_mesh(lit)
        span = mesh.bounds[1] - mesh.bounds[0]
        fw, fh, fd = lit.footprint()
        # 格子の離散化誤差ぶんだけ緩める(footprint >= 実測 になるのが正)
        assert fw >= span[0] - 1e-6 and fw - span[0] < 0.2, \
            f"deg={deg}: 幅 footprint={fw:.2f} 実測={span[0]:.2f}"
        assert fd >= span[1] - 1e-6 and fd - span[1] < 0.2, \
            f"deg={deg}: 奥行き footprint={fd:.2f} 実測={span[1]:.2f}"
        assert math.isclose(fh, span[2], rel_tol=1e-6)


def test_curved_is_narrower_than_flat():
    """湾曲させると占有する幅は弦の長さまで縮み、そのぶん奥行きが出ること"""
    flat = lp.build_lithophane(ramp_image(), width_mm=120, samples=48, curve_deg=0)
    curved = lp.build_lithophane(ramp_image(), width_mm=120, samples=48, curve_deg=90)
    fw0, _, fd0 = flat.footprint()
    fw1, _, fd1 = curved.footprint()
    assert fw1 < fw0
    assert fd1 > fd0


# ---------------------------------------------------------------------------
# メッシュの健全性
# ---------------------------------------------------------------------------
def _mesh_report(mesh):
    counts = collections.Counter(map(tuple, mesh.edges_sorted))
    return {
        "open": sum(1 for v in counts.values() if v == 1),
        "nonmanifold": sum(1 for v in counts.values() if v > 2),
    }


def test_mesh_is_printable_for_all_shapes():
    """平板・湾曲・positive のいずれでも水密で面の向きが揃っていること"""
    cases = [
        ("平板", dict(curve_deg=0.0)),
        ("湾曲30", dict(curve_deg=30.0)),
        ("湾曲90", dict(curve_deg=90.0)),
        ("湾曲180", dict(curve_deg=180.0)),
        ("湾曲330", dict(curve_deg=330.0)),
        ("positive", dict(positive=True)),
    ]
    for label, kw in cases:
        lit = lp.build_lithophane(SAMPLE, width_mm=100, samples=60, **kw)
        mesh = lp.build_mesh(lit, validate=True)  # 検証込み。問題があれば送出される
        rep = _mesh_report(mesh)
        assert rep["open"] == 0, f"{label}: 開いた辺 {rep['open']}"
        assert rep["nonmanifold"] == 0, f"{label}: 非多様体の辺 {rep['nonmanifold']}"
        assert mesh.is_watertight, f"{label}: watertight でない"
        assert mesh.is_winding_consistent, f"{label}: 面の向きが揃っていない"
        assert mesh.volume > 0, f"{label}: 体積が正でない"


def test_normals_point_outward():
    """外向き法線であること(体積が正 かつ 表面の法線が+Y側)"""
    lit = lp.build_lithophane(ramp_image(), width_mm=100, samples=40)
    mesh = lp.build_mesh(lit, validate=True)
    # 厚みが最大の点(=最も+Y側に出ている点)の近くの面は +Y を向くはず
    top = mesh.face_normals[mesh.triangles_center[:, 1] > lit.max_thickness * 0.9]
    assert len(top) > 0
    assert top[:, 1].mean() > 0.5


def test_outer_surface_is_not_mirrored():
    """
    凹凸のある面(表面, +Y)は「+Y側から、up=+Zで見る」のが正しい鑑賞方向
    (README/3Dビューアの前提)。このとき画面の右はワールド座標の -X になる
    (three.js Matrix4.lookAt: xAxis = up × (eye-target)
     = (0,0,1) × (0,1,0) = (-1,0,0))。

    ramp_image() は左が黒(=既定で厚い)、右が白(=薄い)。よって表面を
    正しい向きから見たとき、画面の右(=ワールドXが小さい側)には
    「画像の右端=薄い」が来るはずで、画面の左(Xが大きい側)には
    「画像の左端=厚い」が来るはずである。ここが入れ替わっていれば
    鏡写しになっている。
    """
    lit = lp.build_lithophane(ramp_image(w=64, h=32), width_mm=100.0,
                              min_thickness=0.6, max_thickness=3.0, samples=64)
    mesh = lp.build_mesh(lit)
    nz, nx = lit.thickness.shape
    outer = mesh.vertices[nz * nx:].reshape(nz, nx, 3)

    thickness_at_x0 = outer[:, 0, 1].mean()     # x=0   (画面の右)
    thickness_at_xmax = outer[:, -1, 1].mean()  # x=幅 (画面の左)

    assert math.isclose(thickness_at_x0, lit.min_thickness, abs_tol=1e-6)
    assert math.isclose(thickness_at_xmax, lit.max_thickness, abs_tol=1e-6)


def test_face_count_matches_prediction():
    """UIに表示する三角形数の見積もりが実際と一致すること"""
    for samples in (32, 80):
        lit = lp.build_lithophane(SAMPLE, width_mm=100, samples=samples)
        mesh = lp.build_mesh(lit)
        assert lit.face_count == len(mesh.faces), \
            f"samples={samples}: 予測 {lit.face_count} != 実際 {len(mesh.faces)}"


def test_samples_is_clamped():
    lit = lp.build_lithophane(SAMPLE, samples=5)
    assert lit.samples_x >= 8
    lit = lp.build_lithophane(SAMPLE, samples=99999, max_samples=200)
    assert lit.samples_x == 200


# ---------------------------------------------------------------------------
# サイドサポート(揺れ止め)
# ---------------------------------------------------------------------------
def _supported(**kw):
    """左端が厚く右端が薄い板。左右で側面の厚みが違う状態で確かめる。"""
    kw = {"width_mm": 100.0, "samples": 48, "min_thickness": 0.6,
          "max_thickness": 3.0, **kw}
    return lp.build_lithophane(ramp_image(w=96, h=128), side_supports=True, **kw)


def test_side_supports_are_off_by_default():
    lit = lp.build_lithophane(ramp_image(), width_mm=100, samples=48)
    assert not lit.has_side_supports
    assert lp.build_side_supports(lit) is None
    assert len(lp.build_mesh(lit).faces) == lit.face_count


def test_side_supports_stand_on_both_sides_and_keep_the_plate_intact():
    lit = _supported()
    plain = lp.build_mesh(lp.build_lithophane(
        ramp_image(w=96, h=128), width_mm=100.0, samples=48))
    mesh = lp.build_mesh(lit, validate=True)

    # 板そのものには手を入れていない(先頭に元のメッシュがそのまま入っている)
    assert np.array_equal(mesh.faces[:len(plain.faces)], plain.faces)
    assert np.allclose(mesh.vertices[:len(plain.vertices)], plain.vertices)

    # 左右どちらにも張り出し、高さは変わらず、ベッド(Z=0)に接地している
    lo, hi = mesh.bounds
    assert lo[0] < -1.0 and hi[0] > lit.width_mm + 1.0
    assert math.isclose(-lo[0], hi[0] - lit.width_mm, abs_tol=1e-9), "左右非対称"
    assert math.isclose(lo[2], 0.0, abs_tol=1e-9)
    assert math.isclose(hi[2], lit.height_mm, rel_tol=1e-9)

    # シェルを足しても、開いた辺・非多様体の辺ができない
    rep = _mesh_report(mesh)
    assert rep == {"open": 0, "nonmanifold": 0}, rep
    assert mesh.is_winding_consistent


def test_side_supports_footprint_matches_mesh_bounds():
    for width in (40.0, 100.0, 400.0):
        lit = _supported(width_mm=width)
        span = np.ptp(lp.build_mesh(lit).bounds, axis=0)
        fw, fh, fd = lit.footprint()
        assert math.isclose(fw, span[0], abs_tol=1e-6), (width, fw, span[0])
        assert math.isclose(fd, span[1], abs_tol=1e-6), (width, fd, span[1])
        assert math.isclose(fh, span[2], abs_tol=1e-6), (width, fh, span[2])
        # フィンは板の厚みより十分に奥行きがある(揺れ止めとして効く)
        assert fd >= 15.0


def test_side_supports_touch_the_plate_only_through_tabs():
    """
    フィンは板から離れていて、板に届くのはタブの先端だけであること。
    面で接すると融着して剥がせなくなる。また、タブは板のいちばん薄い所の
    内側に収まっていること(はみ出すと明るい側の端でタブが宙に浮く)。
    """
    lit = _supported()
    sup = lp.build_side_supports(lit)
    v = sup.vertices
    W = lit.width_mm

    near = v[(v[:, 0] > -lp.SUPPORT_GAP + 1e-9)
             & (v[:, 0] < W + lp.SUPPORT_GAP - 1e-9)]
    assert len(near) > 0, "タブが板に届いていない"
    # 隙間より内側にある頂点は、すべて板の中に埋まったタブの先端
    assert ((near[:, 0] > 0) & (near[:, 0] < W)).all(), \
        "フィンが板の側面に面で接している"
    depth = np.minimum(near[:, 0], W - near[:, 0])
    assert np.allclose(depth, lp.SUPPORT_TAB_EMBED)
    assert near[:, 1].min() > 0.0
    assert near[:, 1].max() < lit.thickness.min()

    # 左右の両方にタブがある
    assert (near[:, 0] < W / 2).any() and (near[:, 0] > W / 2).any()


def test_side_support_tabs_reach_the_top():
    """揺れがいちばん大きいのは上端なので、最上段のタブは上端のすぐ下にあること"""
    for h in (64, 128, 400):
        lit = lp.build_lithophane(ramp_image(w=96, h=h), width_mm=100.0,
                                  samples=32, side_supports=True)
        tab_z = lp._support_layout(lit)["tab_z"]
        assert lit.height_mm - tab_z.max() < 2.0
        assert tab_z.min() > 0.0
        assert np.diff(tab_z).max() <= lp.SUPPORT_TAB_PITCH + 1e-9


def test_side_supports_survive_a_very_thin_plate():
    """最小厚みが極端に薄くても、タブが板の厚みからはみ出さないこと"""
    lit = _supported(min_thickness=0.2, max_thickness=1.0)
    y0, y1 = lp._support_layout(lit)["tab_y"]
    assert 0.0 < y0 < y1 < 0.2
    assert _mesh_report(lp.build_mesh(lit)) == {"open": 0, "nonmanifold": 0}


def test_side_supports_are_skipped_when_curved():
    """湾曲させた板は自立するので、指定されていても付けないこと"""
    flat = lp.build_lithophane(ramp_image(), width_mm=100, samples=48, curve_deg=60)
    lit = lp.build_lithophane(ramp_image(), width_mm=100, samples=48, curve_deg=60,
                              side_supports=True)
    assert lit.side_supports and not lit.has_side_supports
    assert lit.footprint() == flat.footprint()
    assert len(lp.build_mesh(lit).faces) == lit.face_count


def test_convex_prism_faces_outward_either_way_round():
    """左右で鏡像にしたときに頂点の回り方が逆になっても裏返らないこと"""
    square = [(0.0, 0.0), (2.0, 0.0), (2.0, 3.0), (0.0, 3.0)]
    for profile in (square, square[::-1]):
        for axis in (0, 1, 2):
            m = lp._convex_prism(profile, axis=axis, lo=5.0, hi=1.0)
            assert m.is_watertight and m.is_winding_consistent
            assert math.isclose(m.volume, 24.0, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# ノズル径
# ---------------------------------------------------------------------------
def test_samples_follow_the_nozzle():
    """格子がノズルより粗くならないよう引き上げ、細かいぶんには触らないこと"""
    # 0.4mm・幅100mm は 250 で足りるので、既定の 400 はそのまま(下げない)
    assert lp.samples_for_nozzle(400, 100.0, 0.4) == 400
    # 0.2mm に替えると 500 必要
    assert lp.samples_for_nozzle(400, 100.0, 0.2) == 500
    assert lp.samples_for_nozzle(100, 100.0, 0.4) == 250
    # すでに足りていれば変えない
    assert lp.samples_for_nozzle(800, 100.0, 0.2) == 800
    # 浮動小数の誤差で1つ多くならない(50 / 0.4 = 125 ちょうど)
    assert lp.samples_needed_for_nozzle(50.0, 0.4) == 125


def test_samples_are_not_raised_past_the_cap():
    """勝手に100MB級のSTLを作らないこと。超えるぶんは警告で知らせる。"""
    assert lp.samples_needed_for_nozzle(200.0, 0.2) == 1000
    assert lp.samples_for_nozzle(400, 200.0, 0.2) == lp.AUTO_SAMPLES_CAP
    # 利用者が自分で上げたぶんは尊重する
    assert lp.samples_for_nozzle(1000, 200.0, 0.2) == 1000

    lit = lp.build_lithophane(ramp_image(), width_mm=200, nozzle=0.2,
                              samples=lp.AUTO_SAMPLES_CAP)
    assert any("ノズル径" in w for w in lit.warnings), lit.warnings


def test_fitted_samples_leave_no_grid_warning():
    for width, nozzle in ((100.0, 0.4), (100.0, 0.2), (60.0, 0.2), (240.0, 0.4)):
        samples = lp.samples_for_nozzle(100, width, nozzle)
        lit = lp.build_lithophane(ramp_image(), width_mm=width, nozzle=nozzle,
                                  samples=samples)
        assert not any("ノズル径" in w for w in lit.warnings), (width, nozzle)
        assert lit.width_mm / lit.samples_x <= nozzle + 1e-9

    coarse = lp.build_lithophane(ramp_image(), width_mm=100, nozzle=0.2,
                                 samples=400)
    assert any("ノズル径" in w for w in coarse.warnings)


def test_nozzle_does_not_change_the_shape():
    """ノズル径は判定にだけ使う。同じ分割数なら厚みマップは完全に同じ。"""
    a = lp.build_lithophane(SAMPLE, width_mm=100, samples=80, nozzle=0.4)
    b = lp.build_lithophane(SAMPLE, width_mm=100, samples=80, nozzle=0.2)
    assert np.array_equal(a.thickness, b.thickness)
    assert a.footprint() == b.footprint()
    assert (a.printable_px, b.printable_px) == (250, 500)


def test_generate_stl_fits_samples_to_the_nozzle():
    """CLI経由では、細いノズルを指定すると格子が自動で細かくなること"""
    kw = dict(width_mm=30.0, samples=100, verbose=False)
    coarse = lp.generate_stl(SAMPLE, None, nozzle=0.4, **kw)
    fine = lp.generate_stl(SAMPLE, None, nozzle=0.2, **kw)
    src_w, src_h = lp.open_image(SAMPLE).size
    assert len(coarse.faces) == lp.face_count_for(
        *lp.grid_shape(src_w, src_h, 100))
    assert len(fine.faces) == lp.face_count_for(
        *lp.grid_shape(src_w, src_h, 150))


# ---------------------------------------------------------------------------
# 警告
# ---------------------------------------------------------------------------
def test_thickness_warnings():
    assert lp.check_thickness_safety(0.6, 3.0) == []
    assert any("薄すぎ" in w for w in lp.check_thickness_safety(0.2, 3.0))
    assert any("厚すぎ" in w for w in lp.check_thickness_safety(0.6, 9.0))
    assert any("差" in w for w in lp.check_thickness_safety(1.0, 1.2))


def test_no_size_warning_within_print_limit():
    """外形が1800mm以内なら警告を出さないこと(要件)"""
    # 横長 2:1 の画像 → 1700 x 850mm。どの辺も上限内。
    lit = lp.build_lithophane(ramp_image(w=200, h=100), width_mm=1700, samples=32,
                              min_thickness=1.0, max_thickness=4.0)
    fw, fh, fd = lit.footprint()
    assert max(fw, fh, fd) <= lp.MAX_PRINT_SIZE_MM
    assert not any("最大造形サイズ" in w for w in lit.warnings), lit.warnings


def test_size_warning_over_print_limit():
    """縦横どちらが超えても警告すること"""
    # 高さが超える(縦長画像)
    tall = lp.build_lithophane(ramp_image(w=100, h=200), width_mm=1500, samples=32)
    assert any("最大造形サイズ" in w for w in tall.warnings)
    # 幅が超える(横長画像)
    wide = lp.build_lithophane(ramp_image(w=200, h=100), width_mm=1900, samples=32)
    assert any("最大造形サイズ" in w for w in wide.warnings)


def test_curved_depth_counts_toward_print_limit():
    """湾曲させたときの奥行きも上限判定に入ること"""
    lit = lp.build_lithophane(ramp_image(w=200, h=100), width_mm=1700, samples=32,
                              curve_deg=180)
    fw, fh, fd = lit.footprint()
    # 半円に曲げると奥行きは半径ぶん出る
    assert fd > 500, f"奥行きが小さすぎる {fd}"


# ---------------------------------------------------------------------------
# プレビュー
# ---------------------------------------------------------------------------
def test_preview_matches_aspect_and_polarity():
    """プレビューが実寸比率で、薄い所ほど明るいこと"""
    lit = lp.build_lithophane(ramp_image(w=200, h=100), width_mm=100, samples=64,
                              gamma=1.0)
    img = lp.render_preview_image(lit, size=200)
    w, h = img.size
    assert abs((h / w) - (lit.height_mm / lit.width_mm)) < 0.03

    arr = np.asarray(img.convert("L"), dtype=float)
    row = arr[h // 2]
    assert row[0] < row[-1], "黒(厚い)側が明るくなっている"


def test_preview_reacts_to_gamma():
    """ガンマを変えるとプレビューが実際に変わること"""
    imgs = []
    for g in (1.0, 0.5):
        lit = lp.build_lithophane(ramp_image(), width_mm=100, samples=64, gamma=g)
        imgs.append(np.asarray(lp.render_preview_image(lit, size=128).convert("L"),
                               dtype=float))
    assert imgs[1].mean() > imgs[0].mean() + 5, "gamma を下げても明るくならない"


def test_thickness_map_renders():
    lit = lp.build_lithophane(SAMPLE, width_mm=100, samples=40)
    img = lp.render_thickness_map(lit, size=120)
    assert img.mode == "L" and max(img.size) == 120


# ---------------------------------------------------------------------------
# STL書き出し
# ---------------------------------------------------------------------------
def test_generate_stl_roundtrip(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "x.stl"
        mesh = lp.generate_stl(SAMPLE, str(out), width_mm=80, samples=48,
                               curve_deg=45, verbose=False)
        assert out.exists() and out.stat().st_size > 1000
        assert mesh.is_watertight

        import trimesh

        loaded = trimesh.load(str(out))
        assert len(loaded.faces) == len(mesh.faces)


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
