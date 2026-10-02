#!/usr/bin/env python3
"""
lithophane_stl.py
写真をリソフェイン(lithophane)として3Dプリント用STLに変換するスクリプト。

リソフェインは「暗い部分ほど厚くして光を遮る」ことで、裏から照らすと
写真が浮かび上がる仕組み。線幅で濃淡を表現する line_art_stl.py とは
別方式で、こちらは連続階調が出せるかわりに必ず背面から光を当てる必要がある。

使い方:
    python3 lithophane_stl.py photo.jpg output.stl --width 100
    python3 lithophane_stl.py photo.jpg output.stl --width 120 --curve 60
    python3 lithophane_stl.py photo.jpg output.stl --width 100 --side-supports

このモジュールはCLIとしてもライブラリとしても使える。
Web API(backend/)からは主に以下を呼ぶ:
    - build_lithophane()       … 厚みマップの生成のみ(プレビュー用・高速)
    - render_preview_image()   … 裏から照らしたときの見え方をシミュレートした画像
    - build_mesh()             … 厚みマップからメッシュを組む
    - generate_stl()           … STLの書き出しまで

座標系(印刷時の向き):
    X = 横幅、Z = 高さ(上)、Y = 厚み方向
  リソフェインは「立てて印刷」するのが定番なので、板が XZ 平面に立つ向きで
  出力する。スライサーに読み込んでそのまま置ける。
"""

import argparse
import math
from dataclasses import dataclass, field

import numpy as np
import trimesh

from photo_common import (  # noqa: F401
    MAX_PRINT_SIZE_MM,
    FaceDetectionUnavailable,
    check_print_size,
    detect_face_crop_box,
    load_grayscale,
    open_image,
)

# プレビューで使う吸収係数(1/mm)。白PLAを裏から照らしたときの
# 減衰の目安。見た目のシミュレーション用で、造形結果には影響しない。
PREVIEW_ATTENUATION = 1.6

# 面数がこれを超えると警告する(STLが数百MBになるのを防ぐ)
FACE_COUNT_WARN = 2_000_000

# 分割数の上限(横方向)。縦方向は縦長画像のためにこの4倍まで許す。
DEFAULT_MAX_SAMPLES = 1200

# --- サイドサポート(立てて印刷するときの揺れ止め) ---------------------------
# 板の左右に、板と直交する三角形のフィンを立てる。フィンは板から SUPPORT_GAP
# だけ離し、細いタブだけでつなぐので、印刷後はフィンを倒せばタブが折れて外れる。
# 寸法は 0.4mm ノズル・レイヤー高 0.1〜0.2mm を想定した決め打ち。
SUPPORT_GAP = 0.5            # 板の側面とフィンの隙間(mm)。狭いと面で融着する
SUPPORT_FIN_THICKNESS = 0.8  # フィンの厚み(mm)。壁2本ぶん
SUPPORT_FIN_TOP = 4.0        # フィン上端の奥行き(mm)
SUPPORT_BASE_RATIO = 0.3     # フィン下端の奥行き = 板の高さ × この比率
SUPPORT_BASE_RANGE = (15.0, 80.0)
SUPPORT_FOOT_WIDTH = 5.0     # フィンの外側に広げる足(ベッドへの定着用)の幅(mm)
SUPPORT_FOOT_HEIGHT = 0.4
SUPPORT_TAB_PITCH = 8.0      # タブの縦方向の間隔(mm)
SUPPORT_TAB_WIDTH = 0.5      # タブの厚み方向の幅(mm)。線1本ぶん
SUPPORT_TAB_ROOT = 1.6       # タブの高さ: フィン側(mm)
SUPPORT_TAB_TIP = 0.4        # タブの高さ: 板に埋まる先端(mm)。板側を細くして、そこで折れるようにする
SUPPORT_TAB_EMBED = 0.2      # タブを板・フィンに食い込ませる量(mm)


def grid_shape(src_w, src_h, samples, max_samples=DEFAULT_MAX_SAMPLES):
    """
    画像サイズと指定分割数から実際の格子 (nx, nz) を決める。
    build_lithophane と、UI向けの見積もり(backend)の両方がこれを使う。
    見積もりロジックを複製すると、極端な縦長クロップ等でクランプの有無が
    食い違い、表示される三角形数が実際と合わなくなる。
    """
    nx = int(np.clip(int(samples), 8, int(max_samples)))
    nz = int(round(nx * src_h / max(1, src_w)))
    nz = int(np.clip(nz, 8, int(max_samples) * 4))
    return nx, nz


def face_count_for(nx, nz):
    """build_mesh() が生成する三角形の数(格子サイズから決まる)"""
    return 4 * (nx - 1) * (nz - 1) + 4 * ((nx - 1) + (nz - 1))


# ---------------------------------------------------------------------------
# 厚みマップの生成
# ---------------------------------------------------------------------------
@dataclass
class Lithophane:
    """リソフェインの厚みマップ。プレビューにもメッシュ化にもこれを使う。"""
    thickness: np.ndarray       # (nz, nx) 各格子点の厚み(mm)。行0が上端。
    width_mm: float             # 横幅(湾曲させる場合は弧の長さ)
    height_mm: float            # 高さ
    min_thickness: float
    max_thickness: float
    curve_deg: float            # 0 なら平板
    src_size: tuple = (1, 1)    # サンプリング元画像の (幅, 高さ) px
    warnings: list = field(default_factory=list)
    side_supports: bool = False  # 左右に揺れ止めのフィンを付ける(平板のみ)

    @property
    def samples_x(self) -> int:
        return self.thickness.shape[1]

    @property
    def samples_z(self) -> int:
        return self.thickness.shape[0]

    def grid_for_samples(self, samples, max_samples=DEFAULT_MAX_SAMPLES):
        """
        この画像を分割数 samples で出力したときの格子 (nx, nz)。
        プレビューは粗い格子で作るため、UIにはこちらの値を見せる。
        """
        w, h = self.src_size
        return grid_shape(w, h, samples, max_samples)

    @property
    def radius_mm(self) -> float:
        """湾曲させた場合の内側の半径(平板なら 0)"""
        if self.curve_deg <= 0:
            return 0.0
        return self.width_mm / math.radians(self.curve_deg)

    @property
    def face_count(self) -> int:
        """build_mesh() が生成する三角形の数"""
        return face_count_for(self.samples_x, self.samples_z)

    @property
    def has_side_supports(self) -> bool:
        """
        実際にサイドサポートを付けるか。湾曲させた板はそれ自体が自立するうえ、
        側面が斜めを向いてフィンを沿わせられないので、平板のときだけ付ける。
        """
        return self.side_supports and self.curve_deg <= 0

    def footprint(self):
        """
        造形時に占める外形 (幅, 高さ, 奥行き) を mm で返す。
        湾曲させると幅は弦の長さに縮み、そのぶん奥行きが出る。
        サイドサポートを付けるとフィンのぶん幅と奥行きが増える。
        """
        if self.has_side_supports:
            lay = _support_layout(self)
            y_lo = min(0.0, lay["fin_y"][0])
            y_hi = max(self.max_thickness, lay["fin_y"][1])
            return (self.width_mm + 2.0 * lay["reach"], self.height_mm,
                    y_hi - y_lo)
        if self.curve_deg <= 0:
            return self.width_mm, self.height_mm, self.max_thickness
        R = self.radius_mm
        half = math.radians(self.curve_deg) / 2.0
        outer = R + self.max_thickness

        # 幅: X = r*sin(φ) の最大値の2倍。中心角が180度以上なら外周の直径。
        width = 2.0 * outer * math.sin(min(half, math.pi / 2))

        # 奥行き: Y = r*cos(φ) - R の範囲。最大は中央の外面(=max_thickness)。
        # 最小は端で、cos(half) が正なら内面(半径R)、負なら外面(半径outer)が
        # より深く沈む。180度超で外面側を取らないと数mm過小評価になる。
        cos_half = math.cos(half)
        min_y = (R if cos_half >= 0 else outer) * cos_half - R
        depth = self.max_thickness - min_y
        return width, self.height_mm, max(depth, self.max_thickness)


def check_thickness_safety(min_thickness, max_thickness,
                           min_floor=0.4, max_ceiling=6.0):
    """
    厚みの設定が印刷・見え方の観点で妥当かを確認する。
    - 最小厚みが薄すぎると穴が開いたり反ったりする
    - 最大厚みが厚すぎると光が通らず暗部が潰れる
    """
    warnings = []
    if min_thickness < min_floor:
        warnings.append(
            f"警告: 最小厚み({min_thickness}mm)が薄すぎます。"
            f"穴が開いたり反ったりする恐れがあるため、{min_floor}mm 以上を推奨します。"
        )
    if max_thickness > max_ceiling:
        warnings.append(
            f"警告: 最大厚み({max_thickness}mm)が厚すぎます。"
            f"光がほとんど通らず暗部が黒く潰れる恐れがあるため、"
            f"{max_ceiling}mm 以下を推奨します。"
        )
    if max_thickness - min_thickness < 0.6:
        warnings.append(
            f"警告: 最小厚みと最大厚みの差({max_thickness - min_thickness:.2f}mm)が"
            f"小さすぎます。明暗の差が出ないため、0.6mm 以上の差を推奨します。"
        )
    return warnings


def build_lithophane(image, width_mm=100.0, min_thickness=0.6,
                     max_thickness=3.0, samples=400, gamma=0.8,
                     positive=False, equalize=False, crop_box=None,
                     auto_face=False, face_margin=0.6, curve_deg=0.0,
                     max_samples=1200, side_supports=False):
    """
    画像から厚みマップを生成する。メッシュ化を伴わないので、
    プレビュー用途ではこれだけを呼べばよい。

    width_mm:  仕上がりの横幅(mm)。湾曲させる場合は弧の長さ。
    samples:   横方向の分割数。高さ方向は画像の比率から自動で決まる。
    gamma:     1未満で暗部の階調が強調される(リソフェインでは 0.8 前後が定番)。
    positive:  True で「明るいところを厚く」する(レリーフ向き)。
               既定は False =「暗いところを厚く」(裏から照らす通常のリソフェイン)。
    side_supports: True で左右に折り取り式の揺れ止めフィンを付ける(平板のみ)。
    """
    if max_thickness < min_thickness:
        raise ValueError("最大厚みは最小厚み以上にしてください。")

    if auto_face and crop_box is None:
        # リソフェインは比率が自由なので、顔検出も元画像の比率に寄せる
        crop_box = detect_face_crop_box(image, margin=face_margin, aspect=1.0)

    # aspect=None: クロップ後の比率をそのまま使う(枠に合わせた切り詰めをしない)
    arr = load_grayscale(image, crop_box=crop_box, gamma=gamma,
                         equalize=equalize, aspect=None)

    src_h, src_w = arr.shape
    nx, nz = grid_shape(src_w, src_h, samples, max_samples)

    # 格子点の位置で画像をサンプリングする(端を含む)
    xs = np.linspace(0, src_w - 1, nx)
    zs = np.linspace(0, src_h - 1, nz)
    brightness = _sample_grid(arr, xs, zs)

    # 0=薄い, 1=厚い
    level = brightness if positive else (1.0 - brightness)
    thickness = min_thickness + (max_thickness - min_thickness) * level

    height_mm = width_mm * src_h / src_w

    warnings = check_thickness_safety(min_thickness, max_thickness)

    litho = Lithophane(
        thickness=thickness,
        width_mm=float(width_mm),
        height_mm=float(height_mm),
        min_thickness=float(min_thickness),
        max_thickness=float(max_thickness),
        curve_deg=float(curve_deg),
        src_size=(src_w, src_h),
        warnings=warnings,
        side_supports=bool(side_supports),
    )

    fw, fh, fd = litho.footprint()
    warnings += check_print_size(fw, fh, fd)

    if litho.face_count > FACE_COUNT_WARN:
        warnings.append(
            f"警告: 分割数が多く、三角形が約{litho.face_count/1e6:.1f}M個になります。"
            f"STLが数百MBになりスライサーが重くなる恐れがあります。"
            f"分割数を下げることを検討してください。"
        )

    return litho


def _sample_grid(arr, xs, zs):
    """arr(H,W) を xs(列座標) × zs(行座標) の格子でバイリニア補間する"""
    H, W = arr.shape
    x0 = np.clip(np.floor(xs).astype(int), 0, W - 1)
    x1 = np.clip(x0 + 1, 0, W - 1)
    z0 = np.clip(np.floor(zs).astype(int), 0, H - 1)
    z1 = np.clip(z0 + 1, 0, H - 1)
    fx = (xs - x0)[None, :]
    fz = (zs - z0)[:, None]

    v00 = arr[np.ix_(z0, x0)]
    v01 = arr[np.ix_(z0, x1)]
    v10 = arr[np.ix_(z1, x0)]
    v11 = arr[np.ix_(z1, x1)]

    top = v00 * (1 - fx) + v01 * fx
    bot = v10 * (1 - fx) + v11 * fx
    return top * (1 - fz) + bot * fz


# ---------------------------------------------------------------------------
# メッシュの生成
# ---------------------------------------------------------------------------
def _surface_points(litho, radial_offset):
    """
    格子点の3D座標を返す。radial_offset は厚み方向のオフセット(mm)。
      平板  … Y = radial_offset
      湾曲  … 半径 R + radial_offset の円筒面上
    戻り値: (nz, nx, 3)

    行・列のインデックスが増えると Z・X も増える向きで並べる。
    面の巻き方(_grid_faces / _wall_faces)がこの前提に依存しているので、
    ここを反転させてはいけない。画像の上下は build_mesh 側で合わせる。
    """
    nz, nx = litho.thickness.shape
    u = np.linspace(0.0, litho.width_mm, nx)[None, :]
    z = np.linspace(0.0, litho.height_mm, nz)[:, None]

    off = np.asarray(radial_offset, dtype=np.float64)
    if off.ndim == 0:
        off = np.full((nz, nx), float(off))

    if litho.curve_deg <= 0:
        x = np.broadcast_to(u, (nz, nx))
        y = off
    else:
        R = litho.radius_mm
        phi = (u - litho.width_mm / 2.0) / R          # -θ/2 .. +θ/2
        r = R + off
        x = r * np.sin(phi)
        # 中心(φ=0)で内側の面が Y=0 になるよう平行移動
        y = r * np.cos(phi) - R

    zz = np.broadcast_to(z, (nz, nx))
    return np.stack([np.broadcast_to(x, (nz, nx)), y, zz], axis=-1)


def _grid_faces(idx, flip=False):
    """
    (nz, nx) の頂点インデックス格子から四角形→三角形の面リストを作る。
    flip=False のとき、外向き法線が「厚みが増す方向」を向く巻き方になる。
    """
    a = idx[:-1, :-1].ravel()
    b = idx[:-1, 1:].ravel()
    c = idx[1:, 1:].ravel()
    d = idx[1:, :-1].ravel()
    if flip:
        return np.concatenate([
            np.stack([a, b, c], axis=1),
            np.stack([a, c, d], axis=1),
        ])
    return np.concatenate([
        np.stack([a, c, b], axis=1),
        np.stack([a, d, c], axis=1),
    ])


def _wall_faces(inner_line, outer_line, flip=False):
    """
    境界に沿った1列分の内側/外側の頂点インデックスから側面を作る。
    inner_line, outer_line: 同じ長さの1次元インデックス列。
    """
    i0, i1 = inner_line[:-1], inner_line[1:]
    o0, o1 = outer_line[:-1], outer_line[1:]
    if flip:
        return np.concatenate([
            np.stack([i0, o0, o1], axis=1),
            np.stack([i0, o1, i1], axis=1),
        ])
    return np.concatenate([
        np.stack([i0, o1, o0], axis=1),
        np.stack([i0, i1, o1], axis=1),
    ])


# ---------------------------------------------------------------------------
# サイドサポート(立てて印刷するときの揺れ止め)
# ---------------------------------------------------------------------------
def _support_layout(litho):
    """
    サイドサポートの寸法を決める。footprint() と build_side_supports() の
    両方がこれを使う(外形の見積もりと実メッシュが食い違わないように)。

    タブは板の側面のうち、どの高さでも必ず中身が詰まっている範囲
    (裏面から min_thickness まで)に収める。側面の厚みは画像の端の列で
    変わるので、ここからはみ出すと明るい行でタブが宙に浮く。
    """
    H = litho.height_mm

    tab_w = min(SUPPORT_TAB_WIDTH, litho.min_thickness * 0.85)
    # 裏面寄りに置く(折り跡が絵柄の面に出ない)。裏面とは同一平面にしない。
    tab_y0 = min(0.05, (litho.min_thickness - tab_w) / 2.0)
    center = tab_y0 + tab_w / 2.0

    base = float(np.clip(H * SUPPORT_BASE_RATIO, *SUPPORT_BASE_RANGE))

    # 揺れは上端ほど大きいので、最上段のタブはフィンの上端ぎりぎりに置く
    z_lo = min(3.0, H * 0.25)
    z_hi = H - SUPPORT_TAB_ROOT / 2.0 - 0.2
    if z_hi <= z_lo:
        tab_z = np.array([H / 2.0])
    else:
        n = max(2, int(math.ceil((z_hi - z_lo) / SUPPORT_TAB_PITCH)) + 1)
        tab_z = np.linspace(z_lo, z_hi, n)

    return {
        "fin_y": (center - base / 2.0, center + base / 2.0),
        "fin_top_y": (center - SUPPORT_FIN_TOP / 2.0,
                      center + SUPPORT_FIN_TOP / 2.0),
        "tab_y": (tab_y0, tab_y0 + tab_w),
        "tab_z": tab_z,
        # 板の側面から外側へ張り出す量(片側)
        "reach": SUPPORT_GAP + SUPPORT_FIN_THICKNESS + SUPPORT_FOOT_WIDTH,
    }


def _convex_prism(profile, axis, lo, hi):
    """
    凸多角形 profile を axis 方向に lo..hi で押し出した水密なプリズムを返す。
    profile は axis 以外の2軸(番号の小さい順)の座標。頂点の回り方はどちらでも
    よく、最後に体積の符号で外向きに揃える(左右で鏡像にしても裏返らない)。
    """
    pts = np.asarray(profile, dtype=np.float64)
    n = len(pts)
    plane = [a for a in range(3) if a != axis]
    verts = np.zeros((2 * n, 3))
    verts[:n, plane] = pts
    verts[n:, plane] = pts
    verts[:n, axis] = min(lo, hi)
    verts[n:, axis] = max(lo, hi)

    faces = []
    for i in range(1, n - 1):
        faces.append((0, i, i + 1))
        faces.append((n, n + i + 1, n + i))
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, n + i, n + j))
        faces.append((i, n + j, j))

    mesh = trimesh.Trimesh(vertices=verts, faces=np.asarray(faces),
                           process=False)
    if mesh.volume < 0:
        mesh.invert()
    return mesh


def build_side_supports(litho):
    """
    板の左右に立てる揺れ止め(フィン + 足 + タブ)のメッシュを返す。
    サポートを付けない設定なら None。

    上から見ると板とフィンで「エ」の字になり、板の弱い向き(厚み方向)の
    揺れをフィンの面内剛性で受ける。フィンと板は SUPPORT_GAP だけ離れていて、
    つないでいるのは板側が細いくさび形のタブだけなので、フィンを板の面の
    ほうへ倒すとタブが板の際で折れて外れる。

    各部品は閉じた別々のシェルで、重ねて置いてあるだけ(ブーリアンはしない)。
    タブの先端は板の中に SUPPORT_TAB_EMBED だけ埋めてある。スライサーは
    重なったシェルを和集合として扱うので、印刷時には一体になる。
    板のメッシュに手を入れないので、分割数が多くても時間もメモリも増えない。
    """
    if not litho.has_side_supports:
        return None

    lay = _support_layout(litho)
    H = litho.height_mm
    (fy0, fy1), (ty0, ty1) = lay["fin_y"], lay["fin_top_y"]
    tab_y0, tab_y1 = lay["tab_y"]

    fin_in = SUPPORT_GAP
    fin_out = SUPPORT_GAP + SUPPORT_FIN_THICKNESS

    parts = []
    # side: 外向きの符号。-1 が左端(x=0)、+1 が右端(x=幅)。
    for edge, side in ((0.0, -1.0), (litho.width_mm, 1.0)):
        def x(d, edge=edge, side=side):
            """板の側面から外向きに d(mm) の位置。負なら板の中。"""
            return edge + side * d

        parts.append(_convex_prism(
            [(fy0, 0.0), (fy1, 0.0), (ty1, H), (ty0, H)],
            axis=0, lo=x(fin_in), hi=x(fin_out)))

        parts.append(_convex_prism(
            [(fy0, 0.0), (fy1, 0.0),
             (fy1, SUPPORT_FOOT_HEIGHT), (fy0, SUPPORT_FOOT_HEIGHT)],
            axis=0, lo=x(fin_out - SUPPORT_TAB_EMBED), hi=x(lay["reach"])))

        x_tip = x(-SUPPORT_TAB_EMBED)
        x_root = x(fin_in + SUPPORT_TAB_EMBED)
        for zc in lay["tab_z"]:
            parts.append(_convex_prism(
                [(x_tip, zc - SUPPORT_TAB_TIP / 2.0),
                 (x_root, zc - SUPPORT_TAB_ROOT / 2.0),
                 (x_root, zc + SUPPORT_TAB_ROOT / 2.0),
                 (x_tip, zc + SUPPORT_TAB_TIP / 2.0)],
                axis=1, lo=tab_y0, hi=tab_y1))

    return trimesh.util.concatenate(parts)


def build_mesh(litho, validate=False):
    """
    厚みマップから水密(watertight)なメッシュを組む。

    内側(裏面)は厚み0のなめらかな面、外側(表面)が厚みぶん盛り上がった面。
    平板なら裏面が平ら、湾曲させると裏面が円筒面になる。

    面の向きと水密性は格子の組み方だけで決まり、画像の内容には依存しない
    (厚みは常に正なので内外が入れ替わることもない)。そのため通常は検証を
    行わない。validate=True で明示的に確認できる。大きなメッシュでは
    検証に数秒かかるので、回帰テストからのみ有効にしている。

    litho.has_side_supports のときは、揺れ止めのフィンを別シェルとして足す
    (build_side_supports 参照)。検証の対象は板だけ。
    """
    nz, nx = litho.thickness.shape

    # thickness は行0が画像の上端。_surface_points は行が増えるとZが増える
    # (=行0が下端)並びなので、ここで上下を合わせる。
    #
    # 列も左右反転させている。凹凸のある面(outer, +Y)を意図した鑑賞側
    # ([up=+Z]で+Y側から見る)から見ると、up×zaxisの向きの都合で
    # 画面の右がワールド座標の-Xになる。列インデックスをそのまま+Xに
    # 使うと(=反転しないと)、写真の左端が画面の右に来て鏡写しになる。
    # ここで列を反転させ、位置(x=u(col))は_surface_points側のまま変えず、
    # 「どの列の厚みをどの位置に置くか」だけを入れ替えることで、
    # 面の巻き方(_grid_faces/_wall_faces)には一切影響を与えずに直せる。
    thickness_bottom_up = litho.thickness[::-1, ::-1]

    inner = _surface_points(litho, 0.0)
    outer = _surface_points(litho, thickness_bottom_up)

    verts = np.concatenate([inner.reshape(-1, 3), outer.reshape(-1, 3)])
    n = nz * nx
    inner_idx = np.arange(n).reshape(nz, nx)
    outer_idx = (np.arange(n) + n).reshape(nz, nx)

    faces = [
        _grid_faces(outer_idx, flip=False),   # 表面: 外向き
        _grid_faces(inner_idx, flip=True),    # 裏面: 内向き(=外から見て外向き)
        # 4辺の側面(行が増える=上へ、列が増える=右へ)
        _wall_faces(inner_idx[:, 0], outer_idx[:, 0], flip=False),    # 左端 (-X)
        _wall_faces(inner_idx[:, -1], outer_idx[:, -1], flip=True),   # 右端 (+X)
        _wall_faces(inner_idx[0, :], outer_idx[0, :], flip=True),     # 下端 (-Z)
        _wall_faces(inner_idx[-1, :], outer_idx[-1, :], flip=False),  # 上端 (+Z)
    ]

    mesh = trimesh.Trimesh(vertices=verts,
                           faces=np.concatenate(faces),
                           process=False)
    mesh.merge_vertices()

    if validate:
        if not mesh.is_winding_consistent:
            raise RuntimeError("メッシュの面の向きが揃っていません。")
        if not mesh.is_watertight:
            raise RuntimeError("メッシュが水密になっていません。")
        if mesh.volume <= 0:
            raise RuntimeError("メッシュの表裏が反転しています。")

    supports = build_side_supports(litho)
    if supports is not None:
        # 板とは別シェルのまま足す。ここで merge_vertices してはいけない
        # (シェルどうしがつながって非多様体になる)。
        mesh = trimesh.util.concatenate([mesh, supports])
    return mesh


# ---------------------------------------------------------------------------
# プレビュー
# ---------------------------------------------------------------------------
def render_preview_image(litho, size=760, attenuation=PREVIEW_ATTENUATION,
                         tint=(255, 244, 224)):
    """
    裏から光を当てたときの見え方をシミュレートした画像を返す。

    厚み t の透過光を Beer-Lambert 則 exp(-k*t) で近似し、
    実際に取りうる範囲(最小厚み〜最大厚み)で正規化して表示する。
    「どこが白飛びし、どこが黒潰れするか」がそのまま見えるので、
    ガンマや厚みの追い込みに使える。
    """
    from PIL import Image

    t = litho.thickness
    trans = np.exp(-attenuation * t)

    # 取りうる範囲で正規化(パラメータを変えたときの差が分かるように)
    hi = math.exp(-attenuation * litho.min_thickness)
    lo = math.exp(-attenuation * litho.max_thickness)
    if hi - lo < 1e-12:
        norm = np.full_like(trans, 0.5)
    else:
        norm = (trans - lo) / (hi - lo)
    norm = np.clip(norm, 0.0, 1.0)

    # ここまでは物理量(リニアな光量)。画面はsRGB(≒2.2乗)応答なので、
    # そのままピクセル値にすると実物よりずっと暗く見える。表示用に符号化する。
    norm = norm ** (1.0 / 2.2)

    rgb = (norm[..., None] * np.asarray(tint, dtype=np.float64)[None, None, :])
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")

    # 実寸の縦横比に合わせて拡大(長辺が size になる)
    w_mm, h_mm = litho.width_mm, litho.height_mm
    if w_mm >= h_mm:
        out_w = int(size)
        out_h = max(1, int(round(size * h_mm / w_mm)))
    else:
        out_h = int(size)
        out_w = max(1, int(round(size * w_mm / h_mm)))
    return img.resize((out_w, out_h), Image.LANCZOS)


def render_thickness_map(litho, size=760):
    """厚みそのものをグレースケールで見る(白=厚い)。デバッグ用。"""
    from PIL import Image

    t = litho.thickness
    span = litho.max_thickness - litho.min_thickness
    norm = (t - litho.min_thickness) / span if span > 1e-12 else np.zeros_like(t)
    img = Image.fromarray((np.clip(norm, 0, 1) * 255).astype(np.uint8), mode="L")
    w_mm, h_mm = litho.width_mm, litho.height_mm
    if w_mm >= h_mm:
        out_w, out_h = int(size), max(1, int(round(size * h_mm / w_mm)))
    else:
        out_h, out_w = int(size), max(1, int(round(size * w_mm / h_mm)))
    return img.resize((out_w, out_h), Image.LANCZOS)


def save_preview_png(litho, path, size=760):
    render_preview_image(litho, size=size).save(path)


# ---------------------------------------------------------------------------
# STL書き出し
# ---------------------------------------------------------------------------
def generate_stl(image_path, output_path, width_mm=100.0, min_thickness=0.6,
                 max_thickness=3.0, samples=400, gamma=0.8, positive=False,
                 equalize=False, crop_box=None, auto_face=False,
                 face_margin=0.6, curve_deg=0.0, preview_path=None,
                 verbose=True, side_supports=False):
    litho = build_lithophane(
        image_path, width_mm=width_mm, min_thickness=min_thickness,
        max_thickness=max_thickness, samples=samples, gamma=gamma,
        positive=positive, equalize=equalize, crop_box=crop_box,
        auto_face=auto_face, face_margin=face_margin, curve_deg=curve_deg,
        side_supports=side_supports,
    )

    if verbose:
        for w in litho.warnings:
            print(w)
        if side_supports and not litho.has_side_supports:
            print("注意: 湾曲させた板は自立するため、サイドサポートは付けません。")

    if preview_path:
        save_preview_png(litho, preview_path)

    mesh = build_mesh(litho)
    if output_path is not None:
        mesh.export(output_path)
    return mesh


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="写真をリソフェイン(厚みで濃淡を表現)の3DプリントSTLに変換")
    ap.add_argument("image", help="入力画像パス")
    ap.add_argument("output", help="出力STLパス")
    ap.add_argument("--width", type=float, default=100.0,
                    help="仕上がりの横幅(mm)。--curve 指定時は弧の長さ")
    ap.add_argument("--min-thickness", type=float, default=0.6,
                    help="明部の厚み(mm)")
    ap.add_argument("--max-thickness", type=float, default=3.0,
                    help="暗部の厚み(mm)")
    ap.add_argument("--samples", type=int, default=400,
                    help="横方向の分割数(精細さ↔ファイルサイズ)")
    ap.add_argument("--curve", type=float, default=0.0,
                    help="円弧状に湾曲させる中心角(度)。0で平板")
    ap.add_argument("--side-supports", action="store_true",
                    help="左右に折り取り式の揺れ止めフィンを付ける(平板のみ)")
    ap.add_argument("--gamma", type=float, default=0.8,
                    help="1未満で暗部の階調を強調")
    ap.add_argument("--positive", action="store_true",
                    help="明るい所を厚くする(レリーフ向き)")
    ap.add_argument("--equalize", action="store_true", help="ヒストグラム均等化")
    ap.add_argument("--crop", type=float, nargs=4, metavar=("L", "T", "R", "B"),
                    help="相対クロップ範囲 0..1")
    ap.add_argument("--auto-face", action="store_true",
                    help="OpenCVの顔検出で自動クロップする(--crop 指定時はそちらを優先)")
    ap.add_argument("--face-margin", type=float, default=0.6,
                    help="--auto-face のとき顔の周囲に取る余白(顔幅に対する比率)")
    ap.add_argument("--preview", help="プレビューpng出力パス(裏から照らした見え方)")
    args = ap.parse_args()

    crop_box = tuple(args.crop) if args.crop else None
    auto_face = args.auto_face
    if crop_box is not None and auto_face:
        print("注意: --crop が指定されているため --auto-face は無視します。")
        auto_face = False

    if auto_face:
        try:
            detected = detect_face_crop_box(args.image, margin=args.face_margin,
                                            aspect=1.0)
            if detected is None:
                print("注意: 顔を検出できませんでした。画像全体を使用します。")
            else:
                l, t, r, b = detected
                print(f"顔検出クロップ: L={l:.3f} T={t:.3f} R={r:.3f} B={b:.3f}")
        except FaceDetectionUnavailable as exc:
            print(f"注意: {exc} 画像全体を使用します。")
            detected = None
        crop_box = detected
        auto_face = False

    mesh = generate_stl(
        args.image, args.output, width_mm=args.width,
        min_thickness=args.min_thickness, max_thickness=args.max_thickness,
        samples=args.samples, gamma=args.gamma, positive=args.positive,
        equalize=args.equalize, crop_box=crop_box, auto_face=auto_face,
        face_margin=args.face_margin, curve_deg=args.curve,
        preview_path=args.preview, side_supports=args.side_supports,
    )
    print(f"書き出し完了: {args.output}  "
          f"(三角形 {len(mesh.faces):,} / watertight={mesh.is_watertight})")


if __name__ == "__main__":
    main()
