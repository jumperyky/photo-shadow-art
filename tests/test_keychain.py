#!/usr/bin/env python3
"""
keychain_stl.py の回帰テスト。

    python3 -m pytest tests/test_keychain.py -q
    (pytest が無い環境では)  python3 tests/test_keychain.py

重点は「レジンだまりが必ず出来ていること」と「リング穴が本物の穴であること」。
どちらもこのモードの存在理由そのもので、壊れると気づきにくい。

メッシュ生成には manifold3d が要る。入っていない環境ではそのグループだけ
スキップし、2D・厚みマップのテストは通るようにしてある。
"""

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import keychain_stl as kc  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "test_face.png"
HAS_BOOLEAN = kc.boolean_available()

SHAPES = ["circle", "square", "rectangle", "hexagon", 5, 3]


def ramp_image(w=200, h=200):
    """左から右へ 黒→白。左が厚くなるはずなので鏡像判定に使う。"""
    g = np.tile(np.linspace(0, 255, w, dtype=np.uint8)[None, :], (h, 1))
    return Image.fromarray(g, "L")


def _skip_without_boolean():
    if HAS_BOOLEAN:
        return False
    try:
        import pytest
        pytest.skip("manifold3d が無いのでメッシュ生成をスキップ")
    except ImportError:
        pass
    return True


# ---------------------------------------------------------------------------
# 2D 外形
# ---------------------------------------------------------------------------
def test_body_is_single_polygon_with_one_hole():
    """外形が1つの塊で、穴はリング穴の1個だけであること"""
    for shape in SHAPES:
        body = kc.build_body(shape, 25.0)
        assert body.body.geom_type == "Polygon", f"{shape}: 塊が分かれている"
        assert len(body.body.interiors) == 1, \
            f"{shape}: 穴が {len(body.body.interiors)} 個ある(1個であるべき)"


def test_frame_surrounds_the_design_area():
    """枠が画像部を完全に囲み、画像部と重ならないこと"""
    for shape in SHAPES:
        body = kc.build_body(shape, 25.0, frame_width=3.0)
        ring = body.body.difference(body.inner)
        assert body.outer.contains(body.inner), f"{shape}: 枠が画像部を囲んでいない"
        assert ring.intersection(body.inner).area < 1e-9, f"{shape}: 枠が画像部に食い込んでいる"


def test_body_is_x_symmetric():
    """
    左右対称であること。

    build_mesh は厚み配列を列反転して使う(写真が鏡像にならないように)。
    外形が左右対称でないとタブの位置がずれるので、この前提が崩れたら
    _body_prism の鏡像処理を見直す必要がある。
    """
    for shape in SHAPES:
        b = kc.build_body(shape, 25.0).body.bounds
        assert math.isclose(b[0], -b[2], abs_tol=1e-9), f"{shape}: 左右非対称"


def test_tab_is_above_the_frame():
    """リング穴が枠より上にあり、タブが本体と繋がっていること"""
    for shape in SHAPES:
        body = kc.build_body(shape, 25.0)
        cx, cy = body.hole_center
        assert cy - body.hole_radius > body.outer.bounds[3] - 1e-6 or \
            cy > body.outer.bounds[3], f"{shape}: 穴が枠に食い込んでいる"
        assert math.isclose(cx, 0.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# 厚みマップ
# ---------------------------------------------------------------------------
def test_resin_well_invariant():
    """
    このモードの存在理由。枠は必ず凹凸より高く、その差がレジンだまりになる。
    ここが崩れるとレジンが流れ落ちて機能しない。
    """
    k = kc.build_keychain(SAMPLE, diameter=50.0, min_thickness=0.6,
                          max_thickness=2.4, well_depth=0.6)
    assert math.isclose(k.frame_thickness, 3.0, abs_tol=1e-9)
    assert math.isclose(k.well_depth, 0.6, abs_tol=1e-9)
    # 枠・タブは一定の厚み
    assert np.allclose(k.slab.thickness[~k.mask], k.frame_thickness)
    # 画像部は最大厚みを超えない = 必ず枠より低い
    assert k.slab.thickness[k.mask].max() <= 2.4 + 1e-9
    assert k.slab.thickness[k.mask].min() >= 0.6 - 1e-9


def test_mask_is_column_symmetric():
    """
    形状マスクが左右対称であること。

    build_mesh の [::-1, ::-1] は列も反転する。マスクが左右対称だからこそ
    枠とタブがワールド座標で正しい位置に来る。非対称な形状を足すときは
    _body_prism の鏡像処理と合わせて見直すこと。
    """
    for shape in ("circle", "hexagon", "square"):
        k = kc.build_keychain(SAMPLE, shape=shape, samples=120)
        assert np.array_equal(k.mask, k.mask[:, ::-1]), f"{shape}: マスクが左右非対称"


def test_slab_is_watertight():
    """切り抜く前のスラブが水密であること(ブーリアン不要なので常に走らせる)"""
    import lithophane_stl as lp
    k = kc.build_keychain(SAMPLE, samples=120)
    mesh = lp.build_mesh(k.slab, validate=True)   # 問題があれば送出される
    assert mesh.is_watertight


def test_positive_inverts_the_relief():
    k1 = kc.build_keychain(SAMPLE, samples=100, positive=False)
    k2 = kc.build_keychain(SAMPLE, samples=100, positive=True)
    assert k1.relief[k1.mask].mean() != k2.relief[k2.mask].mean()


def test_odd_polygon_is_handled():
    """奇数角形は原点対称でない。直径からの計算に頼っていないこと"""
    poly = kc.build_keychain(SAMPLE, shape=5, samples=100)
    assert poly.mask.any(), "5角形のマスクが空"
    assert poly.design_width > 0 and poly.design_height > 0
    # 5角形の外接矩形は上下非対称になる(頂点が上、辺が下)
    b = poly.body.inner.bounds
    assert not math.isclose(abs(b[1]), abs(b[3]), rel_tol=1e-2), \
        "5角形なら画像部が上下非対称のはず"


def test_design_size_comes_from_the_shape():
    """六角形は幅が √3*r になる。直径をそのまま返していないこと"""
    k = kc.build_keychain(SAMPLE, shape="hexagon", diameter=50.0, samples=100)
    assert math.isclose(k.design_width, 25.0 * math.sqrt(3), rel_tol=1e-3)
    assert math.isclose(k.design_height, 50.0, rel_tol=1e-3)


def test_outer_size_includes_frame_and_tab():
    k = kc.build_keychain(SAMPLE, shape="square", diameter=50.0,
                          frame_width=3.0, samples=100)
    assert math.isclose(k.outer_width, 50.0 + 3.0 * 2, rel_tol=1e-3)
    # 高さはタブのぶん外形より大きい
    assert k.outer_height > 50.0 + 3.0 * 2


def test_resin_volume_is_reasonable():
    k = kc.build_keychain(SAMPLE, diameter=50.0, samples=200)
    # 50mm円・平均1.5mm程度 → 数ml のオーダー
    assert 0.5 < k.resin_volume_ml < 10.0, k.resin_volume_ml


# ---------------------------------------------------------------------------
# 警告
# ---------------------------------------------------------------------------
def test_defaults_produce_no_warnings():
    """既定値でいきなり警告が出ないこと(一番よく効く回帰テスト)"""
    k = kc.build_keychain(SAMPLE, shape="square")
    assert k.warnings == [], k.warnings


def test_small_size_warns():
    k = kc.build_keychain(SAMPLE, shape="square", diameter=30.0)
    assert any("解像度" in w for w in k.warnings), k.warnings


def test_printable_px_follows_the_nozzle():
    """
    印刷できる横解像度はノズル径で決まる。格子(grid_px)とは別物。
    分割数をいくら上げても printable_px は増えない。
    """
    a = kc.build_keychain(SAMPLE, shape="square", diameter=50.0,
                          nozzle=0.4, samples=200)
    b = kc.build_keychain(SAMPLE, shape="square", diameter=50.0,
                          nozzle=0.2, samples=200)
    assert a.printable_px == 125 and b.printable_px == 250
    # 分割数を倍にしても印刷解像度は変わらない
    c = kc.build_keychain(SAMPLE, shape="square", diameter=50.0,
                          nozzle=0.4, samples=400)
    assert c.printable_px == a.printable_px
    assert c.grid_px > a.grid_px


def test_fine_nozzle_lifts_the_size_warning():
    """細いノズルなら小さくても解像度が足りるので警告が消えること"""
    coarse = kc.build_keychain(SAMPLE, shape="square", diameter=30.0, nozzle=0.4)
    fine = kc.build_keychain(SAMPLE, shape="square", diameter=30.0, nozzle=0.2)
    assert any("解像度" in w for w in coarse.warnings)
    assert not any("解像度" in w for w in fine.warnings), fine.warnings


def test_flat_frame_warns():
    """枠が凹凸より高くない = レジンだまりが無い"""
    k = kc.build_keychain(SAMPLE, shape="square", max_thickness=2.4,
                          frame_thickness=2.4)
    assert any("ダム" in w or "レジンだまり" in w for w in k.warnings), k.warnings


def test_small_hole_warns():
    k = kc.build_keychain(SAMPLE, shape="square", hole_diameter=1.5)
    assert any("リング" in w for w in k.warnings), k.warnings


def test_thin_ring_margin_warns():
    k = kc.build_keychain(SAMPLE, shape="square", ring_margin=1.0)
    assert any("肉厚" in w for w in k.warnings), k.warnings


def test_bad_thickness_is_rejected():
    try:
        kc.build_keychain(SAMPLE, min_thickness=3.0, max_thickness=1.0)
    except ValueError:
        return
    raise AssertionError("最大厚み < 最小厚み が通ってしまった")


# ---------------------------------------------------------------------------
# メッシュ(manifold3d が必要)
# ---------------------------------------------------------------------------
def test_mesh_is_printable_for_all_shapes():
    if _skip_without_boolean():
        return
    for shape in SHAPES:
        k = kc.build_keychain(SAMPLE, shape=shape, samples=120)
        mesh = kc.build_mesh(k, validate=True)     # 検証込み
        assert mesh.is_watertight, f"{shape}: watertight でない"
        assert mesh.is_winding_consistent, f"{shape}: 面の向きが揃っていない"
        assert mesh.volume > 0, f"{shape}: 体積が正でない"


def test_ring_hole_is_actually_a_hole():
    """
    euler_number が 0 = 種数1 = 貫通穴が1つ。
    2 なら穴が塞がっている(=リングが通らない)。
    """
    if _skip_without_boolean():
        return
    for shape in ("circle", "hexagon", "square"):
        k = kc.build_keychain(SAMPLE, shape=shape, samples=120)
        mesh = kc.build_mesh(k)
        assert mesh.euler_number == 0, \
            f"{shape}: euler={mesh.euler_number} 穴が塞がっている可能性"


def test_mesh_bounds_match_reported_size():
    if _skip_without_boolean():
        return
    for shape in ("circle", "hexagon", "square"):
        k = kc.build_keychain(SAMPLE, shape=shape, samples=120)
        mesh = kc.build_mesh(k)
        lo, hi = mesh.bounds
        assert math.isclose(hi[0] - lo[0], k.outer_width, rel_tol=2e-3), shape
        assert math.isclose(hi[2] - lo[2], k.outer_height, rel_tol=2e-3), shape
        assert math.isclose(hi[1] - lo[1], k.frame_thickness, rel_tol=2e-3), shape


def test_well_exists_in_the_mesh():
    """メッシュ上でも、画像部が枠より低い『池』になっていること"""
    if _skip_without_boolean():
        return
    k = kc.build_keychain(SAMPLE, shape="circle", diameter=50.0, samples=160)
    mesh = kc.build_mesh(k)
    v = mesh.vertices
    # 全体の最大は枠の高さ
    assert math.isclose(v[:, 1].max(), k.frame_thickness, abs_tol=1e-3)
    # 中心付近(画像部)は最大厚みまでしか無い
    cx = (mesh.bounds[0][0] + mesh.bounds[1][0]) / 2
    cz = (mesh.bounds[0][2] + mesh.bounds[1][2]) / 2
    near = (np.abs(v[:, 0] - cx) < 10.0) & (np.abs(v[:, 2] - cz) < 10.0)
    assert v[near, 1].max() <= k.relief_max + 1e-3, "画像部が枠より高い"


def test_outer_surface_is_not_mirrored():
    """
    写真が左右反転していないこと。

    ramp_image は左が黒=厚い。凹凸面(+Y)を up=+Z で見ると画面右はワールド -X
    なので、ワールドXが大きい側の方が厚くなるのが正しい。
    """
    if _skip_without_boolean():
        return
    k = kc.build_keychain(ramp_image(), shape="square", diameter=50.0,
                          samples=160, gamma=1.0)
    mesh = kc.build_mesh(k)
    v = mesh.vertices
    lo, hi = mesh.bounds
    cx = (lo[0] + hi[0]) / 2
    cz = (lo[2] + hi[2]) / 2
    # 枠を除くため、画像部の内側だけ見る
    inside = ((np.abs(v[:, 0] - cx) < 18.0) & (np.abs(v[:, 2] - cz) < 18.0)
              & (v[:, 1] < k.frame_thickness - 1e-6))
    sub = v[inside]
    low_x = sub[sub[:, 0] < cx - 7.0, 1].max()
    high_x = sub[sub[:, 0] > cx + 7.0, 1].max()
    assert high_x > low_x, \
        f"鏡像になっている (X小={low_x:.2f} X大={high_x:.2f})"


def test_generate_stl_roundtrip(tmp_path=None):
    if _skip_without_boolean():
        return
    import tempfile
    import trimesh
    d = Path(tmp_path) if tmp_path else Path(tempfile.mkdtemp())
    out = d / "kc.stl"
    kc.generate_stl(SAMPLE, str(out), samples=100, verbose=False)
    assert out.exists() and out.stat().st_size > 0
    reloaded = trimesh.load(str(out))
    assert len(reloaded.faces) > 0


# ---------------------------------------------------------------------------
# プレビュー
# ---------------------------------------------------------------------------
def test_preview_matches_bbox_aspect():
    k = kc.build_keychain(SAMPLE, shape="circle", samples=120)
    img = kc.render_preview_image(k, size=400)
    minx, miny, maxx, maxy = k.bbox
    expected = (maxx - minx) / (maxy - miny)
    assert math.isclose(img.width / img.height, expected, rel_tol=0.02)


def test_preview_has_frame_and_relief():
    """枠(明るい)と画像部(階調あり)と背景が別々に描かれていること"""
    k = kc.build_keychain(SAMPLE, shape="circle", samples=120)
    a = np.asarray(kc.render_preview_image(k, size=400).convert("RGB"))
    # 四隅は背景(外形の外)
    assert a[2, 2].max() < 60, "四隅が背景になっていない"
    # 画像部に階調がある
    h, w, _ = a.shape
    mid = a[h // 3: 2 * h // 3, w // 3: 2 * w // 3]
    assert mid.max() - mid.min() > 60, "画像部に階調が出ていない"


def test_preview_reacts_to_gamma():
    k1 = kc.build_keychain(SAMPLE, samples=120, gamma=0.5)
    k2 = kc.build_keychain(SAMPLE, samples=120, gamma=1.5)
    m1 = np.asarray(kc.render_preview_image(k1, size=300)).mean()
    m2 = np.asarray(kc.render_preview_image(k2, size=300)).mean()
    assert not math.isclose(m1, m2, rel_tol=1e-3)


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
            print(f"FAIL {name}: {exc}")
    print("\n" + ("OK" if failures == 0 else f"{failures} failed"))
    sys.exit(1 if failures else 0)
