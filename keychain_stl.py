#!/usr/bin/env python3
"""
写真を「レジンコーティング前提のリソフェイン・キーホルダー」STLに変換する。

    python3 keychain_stl.py photo.jpg out.stl --shape circle --diameter 50
    python3 keychain_stl.py photo.jpg out.stl --shape hexagon --auto-face

仕組み:
  - 画像を形状(円/四角/六角形/n角形)にクリップしたリソフェインを作り、
    周囲に一定幅の枠、上部にキーホルダーのリングを通すタブを付ける。
  - **枠を凹凸より高くして「レジンだまり」を作る**のが要。透明レジンを
    流して硬化させると表面が平らになり、凹凸が壊れず引っ掛かりもなくなる。
    枠厚 = 最大厚み + レジンだまりの深さ。

座標系は lithophane_stl と同じ: X=幅、Y=厚み、Z=高さ(上)。立てて印刷する。

ジオメトリの作り方(この順序に意味がある):
  1. 2Dで外形を組む(shapely)。枠は line_art_stl の関数をそのまま使う。
  2. 外形のbboxを覆う「厚みマップ」を作る。形状の内側は写真由来の厚み、
     外側(枠・タブ)は枠厚で一定。
  3. lithophane_stl.build_mesh() を**無改造で**呼んで矩形スラブを作る。
  4. 外形を押し出したプリズムでブーリアン積を取る。リング穴も同時に空く。

なぜスラブを作ってから切り抜くのか:
  lithophane_stl のメッシュ生成は矩形格子を前提にしている
  (_grid_faces にマスクが無く、側面は4本のスライス決め打ち)。格子を直接
  クリップするには境界ループ探索を書く必要があり、バグの温床になる。
  「一度矩形で作ってから切る」ほうが既存コードを一切変えずに済む。
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field

import numpy as np
import shapely
import trimesh
from shapely.affinity import scale as shapely_scale
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

import lithophane_stl as lp
import line_art_stl as la
import photo_common as pc
from photo_common import detect_face_crop_box, load_grayscale

# --- 形状まわりの定数 -------------------------------------------------------
# タブを枠にどれだけ食い込ませるか(mm)。完全に外接させると接合部が細くなる。
TAB_OVERLAP_MM = 2.0
# プリズムを厚み方向にはみ出させる量(mm)。スラブの表裏と同一平面になるのを
# 避けるため。同一平面の面同士はブーリアンが最も苦手とする入力。
Y_MARGIN_MM = 1.0
# スラブbboxを外形より広げる量の下限(mm)。プリズム側面がスラブ側面と
# 同一平面になる縮退を避ける。
PAD_MIN_MM = 1.0

# --- 警告のしきい値 ---------------------------------------------------------
DEFAULT_NOZZLE_MM = 0.4       # 一般的なノズル径
# 印刷できる横解像度の下限。これを下回ると顔の細部が潰れる。
# 0.4mmノズルなら 45mm 相当。ノズルを細くすれば同じpx数を小さいサイズで得られる。
MIN_PRINTABLE_PX = 110
MIN_WELL_DEPTH_MM = 0.4       # これ未満はレジンが溜まらない
MIN_HOLE_DIAMETER_MM = 2.5    # これ未満はリングが通らない
MIN_RING_MARGIN_MM = 2.0      # 穴の上の肉厚。層間剥離方向に効くので余裕を持つ

DEFAULT_MAX_SAMPLES = 800


class BooleanUnavailable(RuntimeError):
    """3Dブーリアンのエンジンが無い(manifold3d 未インストール)"""


def boolean_available() -> bool:
    """manifold エンジンが使えるか。使えなければキーホルダーは生成できない。"""
    try:
        import manifold3d  # noqa: F401
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------------------
# 2D 外形
# ---------------------------------------------------------------------------
@dataclass
class KeychainBody:
    """キーホルダーの2D外形。すべて設計座標系(原点中心)の shapely ポリゴン。"""
    inner: Polygon          # 画像部(写真が入る範囲)
    outer: Polygon          # 画像部+枠
    body: Polygon           # 画像部+枠+タブ から リング穴 を抜いたもの
    hole_center: tuple
    hole_radius: float
    tab_radius: float


def build_body(shape, r, aspect=1.0, frame_width=3.0, hole_diameter=3.5,
               ring_margin=2.5, tab_overlap=TAB_OVERLAP_MM) -> KeychainBody:
    """
    2Dの外形を組む。

    枠は line_art_stl.make_frame_ring() の buffer をそのまま使う。幅がどこでも
    一定になる(相似拡大だと長方形やn角形で幅が不均一になる)という性質が
    そのまま効いてほしいので、ここで別実装しない。
    """
    inner = la.make_shape_polygon(shape, r, aspect)
    _frame_ring, outer = la.make_frame_ring(inner, frame_width)

    tab_r = hole_diameter / 2.0 + ring_margin
    # タブは枠の上端から少し食い込ませる。食い込ませないと接合部が点になる。
    cy = outer.bounds[3] + tab_r - min(tab_overlap, tab_r * 0.6)
    center = (0.0, cy)

    tab = Point(center).buffer(tab_r, quad_segs=64)
    hole = Point(center).buffer(hole_diameter / 2.0, quad_segs=48)
    body = unary_union([outer, tab]).difference(hole)

    if body.geom_type != "Polygon":
        raise RuntimeError(
            "外形が1つの塊になりませんでした。枠の幅かタブの大きさを見直してください。")

    return KeychainBody(inner=inner, outer=outer, body=body,
                        hole_center=center, hole_radius=hole_diameter / 2.0,
                        tab_radius=tab_r)


# ---------------------------------------------------------------------------
# 本体
# ---------------------------------------------------------------------------
@dataclass
class Keychain:
    """
    キーホルダー1個分のデータ。メッシュ化の前段まで。

    slab は「bboxを覆う矩形の厚みマップ」を持つ Lithophane。
    **slab.footprint() と slab.face_count は使わないこと。** どちらも矩形前提の
    値で、切り抜き後の実物とは一致しない。外形寸法は下のプロパティを使う。
    """
    slab: lp.Lithophane          # 合成した厚みマップ(矩形)
    relief: np.ndarray           # 画像部だけの厚み(プレビューの正規化用)
    mask: np.ndarray             # 画像部かどうか (nz, nx)
    body: KeychainBody
    bbox: tuple                  # パディング後の (minx, miny, maxx, maxy)
    frame_thickness: float
    well_depth: float
    relief_min: float
    relief_max: float
    nozzle: float = DEFAULT_NOZZLE_MM
    warnings: list = field(default_factory=list)

    # --- 実物の寸法(切り抜き後) ---
    @property
    def outer_width(self) -> float:
        b = self.body.body.bounds
        return b[2] - b[0]

    @property
    def outer_height(self) -> float:
        b = self.body.body.bounds
        return b[3] - b[1]

    @property
    def design_width(self) -> float:
        b = self.body.inner.bounds
        return b[2] - b[0]

    @property
    def design_height(self) -> float:
        b = self.body.inner.bounds
        return b[3] - b[1]

    def footprint(self):
        """造形時に占める外形 (幅, 高さ, 奥行き) mm"""
        return self.outer_width, self.outer_height, self.frame_thickness

    @property
    def grid_px(self) -> int:
        """画像部に乗っている格子の列数。メッシュの細かさ(印刷の細かさではない)。"""
        nz, nx = self.slab.thickness.shape
        minx, _miny, maxx, _maxy = self.bbox
        return int(round(nx * self.design_width / (maxx - minx)))

    @property
    def printable_px(self) -> int:
        """
        実際に印刷できる横方向の解像度。

        立てて印刷するので、横は押出し幅(≒ノズル径)、縦はレイヤー高で決まる。
        格子をいくら細かくしてもこの値は増えない(ファイルが重くなるだけ)。
        ノズルを細くするか、作品を大きくするしか上げる方法はない。
        """
        return int(self.design_width / self.nozzle)

    @property
    def resin_volume_ml(self) -> float:
        """レジンだまりを満たすのに必要な量(ml)。混ぜる量の目安。"""
        nz, nx = self.slab.thickness.shape
        minx, miny, maxx, maxy = self.bbox
        cell = ((maxx - minx) / max(nx - 1, 1)) * ((maxy - miny) / max(nz - 1, 1))
        gap = np.clip(self.frame_thickness - self.slab.thickness, 0.0, None)
        return float((gap * self.mask).sum() * cell / 1000.0)

    @property
    def face_count_estimate(self) -> int:
        """
        切り抜き後の三角形数の見積もり。ブーリアンを通すまで正確には出ないので
        面積比で概算する。UIには「約」として出すこと。
        """
        nz, nx = self.slab.thickness.shape
        minx, miny, maxx, maxy = self.bbox
        bbox_area = (maxx - minx) * (maxy - miny)
        ratio = self.body.body.area / bbox_area if bbox_area > 0 else 1.0
        grid = 4 * max(nx - 1, 0) * max(nz - 1, 0) * ratio
        rim = 4 * len(self.body.body.exterior.coords)
        return int(grid + rim)

    def grid_for_samples(self, samples, max_samples=DEFAULT_MAX_SAMPLES):
        minx, miny, maxx, maxy = self.bbox
        return lp.grid_shape(maxx - minx, maxy - miny, samples, max_samples)


# ---------------------------------------------------------------------------
# 警告
# ---------------------------------------------------------------------------
def check_keychain_safety(design_width_mm, grid_px, printable_px, nozzle,
                          frame_thickness, max_thickness, hole_diameter,
                          ring_margin):
    """造形上まずい設定を日本語で警告する(他モジュールと同じくリストを返す)。"""
    warnings = []

    if printable_px < MIN_PRINTABLE_PX:
        need = MIN_PRINTABLE_PX * nozzle
        warnings.append(
            f"警告: デザイン部 {design_width_mm:.0f}mm・ノズル {nozzle}mm では"
            f"印刷できる横解像度が約{printable_px}ピクセル相当しかなく、"
            f"顔の細部が潰れます。"
            f"デザイン部を{need:.0f}mm以上にするか、細いノズルを使ってください"
            f"(立てて印刷するため横方向はノズル径で頭打ちになります)。"
        )

    if grid_px > 0 and design_width_mm / grid_px > nozzle:
        warnings.append(
            f"警告: 分割数が粗く、格子の間隔 "
            f"{design_width_mm / grid_px:.2f}mm がノズル径 {nozzle}mm を"
            f"上回っています。分割数を上げると精細になります。"
        )

    well = frame_thickness - max_thickness
    if well <= 0:
        warnings.append(
            "警告: 枠が凹凸より高くありません。レジンを流してもダムが無いため"
            "流れ落ちてしまいます。レジンだまりの深さを0より大きくしてください。"
        )
    elif well < MIN_WELL_DEPTH_MM:
        warnings.append(
            f"警告: レジンだまりが {well:.2f}mm と浅く、"
            f"レジンが溜まりにくく凹凸の保護も不十分です。"
            f"{MIN_WELL_DEPTH_MM}mm以上を推奨します。"
        )

    if hole_diameter < MIN_HOLE_DIAMETER_MM:
        warnings.append(
            f"警告: リング穴が {hole_diameter:.1f}mm と小さく、"
            f"一般的なキーホルダーのリングが通りません。"
            f"{MIN_HOLE_DIAMETER_MM}mm以上を推奨します。"
        )

    if ring_margin < MIN_RING_MARGIN_MM:
        warnings.append(
            f"警告: 穴の上の肉厚が {ring_margin:.1f}mm しかありません。"
            f"立てて印刷するとこの部分は積層方向に引っ張られる(層間剥離しやすい)"
            f"ため、{MIN_RING_MARGIN_MM + 0.5:.1f}mm以上を推奨します。"
        )

    return warnings


# ---------------------------------------------------------------------------
# 生成
# ---------------------------------------------------------------------------
def build_keychain(image, shape="circle", diameter=50.0, aspect=1.0,
                   frame_width=3.0, min_thickness=0.6, max_thickness=2.4,
                   well_depth=0.6, frame_thickness=None,
                   hole_diameter=3.5, ring_margin=2.5, samples=320, gamma=0.8,
                   positive=False, equalize=False, crop_box=None,
                   auto_face=False, face_margin=0.6,
                   nozzle=DEFAULT_NOZZLE_MM,
                   max_samples=DEFAULT_MAX_SAMPLES) -> Keychain:
    """
    画像とパラメータから厚みマップまでを作る。メッシュ化は含まないので、
    プレビュー用途ではこれだけ呼べばよい。

    frame_thickness を明示すると well_depth より優先される(CLI用)。
    APIからは well_depth だけを見せて、枠が凹凸より低くなる設定を作れなくする。
    """
    if max_thickness < min_thickness:
        raise ValueError("最大厚みは最小厚み以上にしてください。")
    if diameter <= 0:
        raise ValueError("サイズは0より大きくしてください。")
    if ring_margin <= 0:
        raise ValueError("穴の上の肉厚は0より大きくしてください。")

    if frame_thickness is None:
        frame_thickness = max_thickness + well_depth
    well_depth = frame_thickness - max_thickness

    # 円・多角形は等方なので aspect は 1 に正規化する。
    # ここを揃えないと、画像だけ aspect でクロップされて枠は等方のまま、
    # という食い違いが起きて像が歪む(line_art_stl.build_artwork と同じ理由)。
    if shape not in ("square", "rectangle"):
        aspect = 1.0

    R = float(diameter) / 2.0
    body = build_body(shape, R, aspect, frame_width, hole_diameter, ring_margin)

    if auto_face and crop_box is None:
        crop_box = detect_face_crop_box(image, margin=face_margin, aspect=aspect)

    arr = load_grayscale(image, crop_box=crop_box, gamma=gamma,
                         equalize=equalize, aspect=aspect)

    # --- 格子。外形bboxを少し広げて張る ---
    # パディングしないと、プリズムの側面がスラブの側面と同一平面になり
    # ブーリアンの縮退入力になる。3セル分の余裕を持たせる。
    bminx, bminy, bmaxx, bmaxy = body.body.bounds
    pad = max(PAD_MIN_MM, 3.0 * (bmaxx - bminx) / max(samples - 1, 1))
    minx, miny = bminx - pad, bminy - pad
    maxx, maxy = bmaxx + pad, bmaxy + pad
    W, H = maxx - minx, maxy - miny

    nx, nz = lp.grid_shape(W, H, samples, max_samples)
    # 行0が上端(画像順)。lithophane_stl.build_mesh の [::-1, ::-1] が
    # これを前提に上下と左右を直してくれる。
    U, V = np.meshgrid(minx + np.linspace(0.0, W, nx),
                       maxy - np.linspace(0.0, H, nz))

    inside = shapely.contains_xy(body.inner, U, V)

    # 画像は [-Rx, Rx] x [-Ry, Ry] に貼る。シャドウアートと同じ規則にすることで
    # フロントの cropAspect() / cropOutline() がそのまま正しく効く。
    Rx, Ry = (R, R * aspect) if shape in ("square", "rectangle") else (R, R)
    brightness = la.sample_bilinear(arr, U, V, Rx, Ry)

    level = brightness if positive else (1.0 - brightness)
    relief = min_thickness + (max_thickness - min_thickness) * level
    thickness = np.where(inside, relief, frame_thickness)

    slab = lp.Lithophane(
        thickness=thickness, width_mm=W, height_mm=H,
        min_thickness=min_thickness, max_thickness=frame_thickness,
        curve_deg=0.0, src_size=(W, H),
    )

    kc = Keychain(slab=slab, relief=relief, mask=inside, body=body,
                  bbox=(minx, miny, maxx, maxy),
                  frame_thickness=frame_thickness, well_depth=well_depth,
                  relief_min=min_thickness, relief_max=max_thickness,
                  nozzle=nozzle)

    kc.warnings = check_keychain_safety(
        kc.design_width, kc.grid_px, kc.printable_px, nozzle,
        frame_thickness, max_thickness, hole_diameter, ring_margin)
    kc.warnings += lp.check_thickness_safety(min_thickness, max_thickness)
    kc.warnings += pc.check_print_size(*kc.footprint())

    if kc.face_count_estimate > lp.FACE_COUNT_WARN:
        kc.warnings.append(
            f"警告: 分割数が多く、三角形が約{kc.face_count_estimate/1e6:.1f}M個に"
            f"なります。STLが重くなるので分割数を下げることを検討してください。"
        )
    return kc


def _body_prism(kc: Keychain) -> trimesh.Trimesh:
    """
    外形を厚み方向(+Y)に押し出したプリズム。スラブを切り抜くのに使う。

    座標の対応がややこしいので順を追う:
      - build_mesh は厚み配列を [::-1, ::-1] して使う。列の反転は「+Y側から
        up=+Z で見たとき写真が鏡像にならないように」入っている。その結果
        設計座標の x は world では反転して現れる。
        → プリズム側も同じだけ鏡像にしておく必要がある。
        (今の形状はすべて x=0 対称なので実質no-opだが、将来非対称な
         タブを足したときに黙って壊れないよう明示的に入れてある)
      - extrude_polygon は +Z に押し出す。X軸まわり +90° 回すと
        (x,y,z) -> (x,-z,y) となり、設計のyが+Zへ、押し出しが -Y..0 に入る。
        -90° にするとタブが下に来るので符号に注意。
      - 最後に平行移動でスラブ(正の象限)に合わせる。
    """
    minx, miny, maxx, maxy = kc.bbox
    height = kc.frame_thickness + 2.0 * Y_MARGIN_MM

    mirrored = shapely_scale(kc.body.body, xfact=-1.0, origin=(0, 0))
    prism = trimesh.creation.extrude_polygon(mirrored, height)
    prism.apply_transform(
        trimesh.transformations.rotation_matrix(math.pi / 2.0, [1, 0, 0]))
    # 厚み方向は表裏に Y_MARGIN ずつはみ出させる(同一平面を避ける)
    prism.apply_translation([maxx, kc.frame_thickness + Y_MARGIN_MM, -miny])
    return prism


def build_mesh(kc: Keychain, validate=False) -> trimesh.Trimesh:
    """
    厚みマップを矩形スラブにしてから、外形プリズムで切り抜く。

    切り口は必ず「枠の平坦部」を通る(外形の外周は常に枠厚一定の領域にある)。
    平面同士の素直な交差になるので、ブーリアンとしては最も easy な入力。

    validate=True は is_watertight を呼ぶが、30万面で1秒以上かかるので
    リクエスト経路では使わないこと(テストからのみ)。
    """
    if not boolean_available():
        raise BooleanUnavailable(
            "キーホルダーの生成には manifold3d が必要です。"
            "`pip install -r requirements.txt` を実行してください。"
        )

    slab = lp.build_mesh(kc.slab)
    prism = _body_prism(kc)
    mesh = trimesh.boolean.intersection([slab, prism], engine="manifold")

    if mesh is None or len(mesh.faces) == 0:
        raise RuntimeError("形状の切り抜きに失敗しました。パラメータを見直してください。")
    if mesh.volume <= 0:
        raise RuntimeError("生成されたメッシュの体積が正になりません。")

    if validate:
        if not mesh.is_winding_consistent:
            raise RuntimeError("メッシュの面の向きが揃っていません。")
        if not mesh.is_watertight:
            raise RuntimeError("メッシュが水密になっていません。")
    return mesh


# ---------------------------------------------------------------------------
# プレビュー
# ---------------------------------------------------------------------------
def _poly_mask(geom, size, to_px):
    """ポリゴンを塗りつぶした L マスクを返す。内周(穴)は0に戻す。"""
    from PIL import Image, ImageDraw

    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    geoms = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for g in geoms:
        if g.is_empty:
            continue
        d.polygon([to_px(p) for p in g.exterior.coords], fill=255)
        for interior in g.interiors:
            d.polygon([to_px(p) for p in interior.coords], fill=0)
    return m


def render_preview_image(kc: Keychain, size=760, tint=(255, 244, 224),
                         frame_color=(232, 230, 224), bg=(24, 26, 30),
                         attenuation=lp.PREVIEW_ATTENUATION, supersample=3):
    """
    裏から光を当てたときの見え方 + 枠 + リング穴 を合成した RGBA 画像を返す。

    外形の外側とリング穴は**透明**にする。キーホルダーは形そのものが見どころ
    なので、背景色の四角で囲むと形が読み取りにくい(UI側は市松模様の上に
    載せるので、透明にすると輪郭がはっきり見える)。

    **マスク合成で組むこと。** line_art_stl のように「外形を塗ってから内周を
    背景色で塗り戻す」流儀をそのまま持ち込むと、枠の内周(=画像部)まで塗り
    潰してしまう。層ごとにマスクを作って貼る。
    """
    from PIL import Image

    minx, miny, maxx, maxy = kc.bbox
    W, H = maxx - minx, maxy - miny
    if W >= H:
        px, py = int(size), max(1, int(round(size * H / W)))
    else:
        py, px = int(size), max(1, int(round(size * W / H)))
    # PILのポリゴンはアンチエイリアスされないので、拡大して描いてから縮小する
    sx, sy = px * supersample, py * supersample

    def to_px(p):
        return ((p[0] - minx) / W * sx, (maxy - p[1]) / H * sy)

    # --- 画像部: 透過シミュレーション ---
    # 正規化は「凹凸の取りうる範囲」で行う。枠厚まで含めると枠のぶんだけ
    # レンジが広がり、写真のコントラストが不当に潰れる。
    trans = np.exp(-attenuation * kc.relief)
    hi = math.exp(-attenuation * kc.relief_min)
    lo = math.exp(-attenuation * kc.relief_max)
    if hi - lo < 1e-12:
        norm = np.full_like(trans, 0.5)
    else:
        norm = np.clip((trans - lo) / (hi - lo), 0.0, 1.0)
    # ここまでリニア光量。画面はsRGB(≒2.2乗)応答なので表示用に符号化する
    norm = norm ** (1.0 / 2.2)
    rgb = np.clip(norm[..., None] * np.asarray(tint, dtype=np.float64), 0, 255)
    litho = Image.fromarray(rgb.astype(np.uint8), "RGB").resize((sx, sy), Image.LANCZOS)

    out = Image.new("RGBA", (sx, sy), (*bg, 0))
    out.paste(litho.convert("RGBA"), (0, 0),
              _poly_mask(kc.body.inner, (sx, sy), to_px))
    out.paste(Image.new("RGBA", (sx, sy), (*frame_color, 255)), (0, 0),
              _poly_mask(kc.body.body.difference(kc.body.inner), (sx, sy), to_px))
    return out.resize((px, py), Image.LANCZOS)


def save_preview_png(kc, path, size=760):
    render_preview_image(kc, size=size).save(path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def generate_stl(image_path, output_path, shape="circle", diameter=50.0,
                 aspect=1.0, frame_width=3.0, min_thickness=0.6,
                 max_thickness=2.4, well_depth=0.6, hole_diameter=3.5,
                 ring_margin=2.5, samples=320, gamma=0.8, positive=False,
                 equalize=False, crop_box=None, auto_face=False,
                 face_margin=0.6, nozzle=DEFAULT_NOZZLE_MM,
                 preview_path=None, verbose=True):
    kc = build_keychain(
        image_path, shape=shape, diameter=diameter, aspect=aspect,
        frame_width=frame_width, min_thickness=min_thickness,
        max_thickness=max_thickness, well_depth=well_depth,
        hole_diameter=hole_diameter, ring_margin=ring_margin, samples=samples,
        gamma=gamma, positive=positive, equalize=equalize, crop_box=crop_box,
        auto_face=auto_face, face_margin=face_margin, nozzle=nozzle,
    )
    if verbose:
        for w in kc.warnings:
            print(w)

    mesh = build_mesh(kc)
    if preview_path:
        save_preview_png(kc, preview_path)
    if output_path:
        mesh.export(output_path)
    if verbose:
        w, h, d = kc.footprint()
        print(f"外形 {w:.1f} x {h:.1f} x {d:.2f} mm / "
              f"三角形 {len(mesh.faces)} / レジン約 {kc.resin_volume_ml:.1f} ml / "
              f"印刷できる横解像度 約{kc.printable_px}px")
    return mesh


def main():
    ap = argparse.ArgumentParser(
        description="写真をレジンコーティング前提のリソフェイン・キーホルダーに変換")
    ap.add_argument("image", help="入力画像パス")
    ap.add_argument("output", help="出力STLパス")
    ap.add_argument("--shape", choices=["circle", "hexagon", "square", "rectangle"],
                    default="circle", help="外形の形")
    ap.add_argument("--sides", type=int, default=None,
                    help="任意のn角形にする(--shapeより優先)")
    ap.add_argument("--diameter", type=float, default=50.0,
                    help="デザイン部の直径(mm)。50mm以上を推奨")
    ap.add_argument("--aspect", type=float, default=1.0,
                    help="square/rectangle のときの 高さ÷幅")
    ap.add_argument("--frame-width", type=float, default=3.0, help="枠の幅(mm)")
    ap.add_argument("--min-thickness", type=float, default=0.6, help="明部の厚み(mm)")
    ap.add_argument("--max-thickness", type=float, default=2.4, help="暗部の厚み(mm)")
    ap.add_argument("--well-depth", type=float, default=0.6,
                    help="レジンだまりの深さ(mm)。枠厚 = 最大厚み + この値")
    ap.add_argument("--hole-diameter", type=float, default=3.5, help="リング穴の径(mm)")
    ap.add_argument("--ring-margin", type=float, default=2.5, help="穴の上の肉厚(mm)")
    ap.add_argument("--samples", type=int, default=320, help="横方向の分割数")
    ap.add_argument("--gamma", type=float, default=0.8)
    ap.add_argument("--positive", action="store_true", help="明るい所を厚くする")
    ap.add_argument("--equalize", action="store_true", help="ヒストグラム均等化")
    ap.add_argument("--crop", type=float, nargs=4, metavar=("L", "T", "R", "B"),
                    default=None, help="0..1 の相対クロップ範囲")
    ap.add_argument("--auto-face", action="store_true", help="顔を検出して自動クロップ")
    ap.add_argument("--face-margin", type=float, default=0.6)
    ap.add_argument("--nozzle", type=float, default=DEFAULT_NOZZLE_MM,
                    help="ノズル径(mm)。印刷できる横解像度の判定に使う")
    ap.add_argument("--preview", default=None, help="プレビューPNGの出力先")
    args = ap.parse_args()

    if not boolean_available():
        print("エラー: manifold3d が入っていません。"
              "`pip install -r requirements.txt` を実行してください。", file=sys.stderr)
        return 1

    generate_stl(
        args.image, args.output,
        shape=args.sides if args.sides else args.shape,
        diameter=args.diameter, aspect=args.aspect, frame_width=args.frame_width,
        min_thickness=args.min_thickness, max_thickness=args.max_thickness,
        well_depth=args.well_depth, hole_diameter=args.hole_diameter,
        ring_margin=args.ring_margin, samples=args.samples, gamma=args.gamma,
        positive=args.positive, equalize=args.equalize,
        crop_box=tuple(args.crop) if args.crop else None,
        auto_face=args.auto_face, face_margin=args.face_margin,
        nozzle=args.nozzle, preview_path=args.preview,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
