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
    warnings: list = field(default_factory=list)

    @property
    def samples_x(self) -> int:
        return self.thickness.shape[1]

    @property
    def samples_z(self) -> int:
        return self.thickness.shape[0]

    @property
    def radius_mm(self) -> float:
        """湾曲させた場合の内側の半径(平板なら 0)"""
        if self.curve_deg <= 0:
            return 0.0
        return self.width_mm / math.radians(self.curve_deg)

    @property
    def face_count(self) -> int:
        """build_mesh() が生成する三角形の数"""
        nx, nz = self.samples_x, self.samples_z
        return 4 * (nx - 1) * (nz - 1) + 4 * ((nx - 1) + (nz - 1))

    def footprint(self):
        """
        造形時に占める外形 (幅, 高さ, 奥行き) を mm で返す。
        湾曲させると幅は弦の長さに縮み、そのぶん奥行きが出る。
        """
        if self.curve_deg <= 0:
            return self.width_mm, self.height_mm, self.max_thickness
        R = self.radius_mm
        half = math.radians(self.curve_deg) / 2.0
        outer = R + self.max_thickness
        # 弦の幅。中心角が180度を超えると外周の直径が効いてくる
        if self.curve_deg >= 180.0:
            width = 2.0 * outer
        else:
            width = 2.0 * outer * math.sin(min(half, math.pi / 2))
        depth = outer - R * math.cos(half) if self.curve_deg < 360 else 2 * outer
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
                     max_samples=1200):
    """
    画像から厚みマップを生成する。メッシュ化を伴わないので、
    プレビュー用途ではこれだけを呼べばよい。

    width_mm:  仕上がりの横幅(mm)。湾曲させる場合は弧の長さ。
    samples:   横方向の分割数。高さ方向は画像の比率から自動で決まる。
    gamma:     1未満で暗部の階調が強調される(リソフェインでは 0.8 前後が定番)。
    positive:  True で「明るいところを厚く」する(レリーフ向き)。
               既定は False =「暗いところを厚く」(裏から照らす通常のリソフェイン)。
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
    nx = int(np.clip(int(samples), 8, int(max_samples)))
    # 縦横比を保ったまま高さ方向の分割数を決める
    nz = int(round(nx * src_h / src_w))
    nz = int(np.clip(nz, 8, int(max_samples) * 4))

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
        warnings=warnings,
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


def build_mesh(litho, validate=False):
    """
    厚みマップから水密(watertight)なメッシュを組む。

    内側(裏面)は厚み0のなめらかな面、外側(表面)が厚みぶん盛り上がった面。
    平板なら裏面が平ら、湾曲させると裏面が円筒面になる。

    面の向きと水密性は格子の組み方だけで決まり、画像の内容には依存しない
    (厚みは常に正なので内外が入れ替わることもない)。そのため通常は検証を
    行わない。validate=True で明示的に確認できる。大きなメッシュでは
    検証に数秒かかるので、回帰テストからのみ有効にしている。
    """
    nz, nx = litho.thickness.shape

    # thickness は行0が画像の上端。_surface_points は行が増えるとZが増える
    # (=行0が下端)並びなので、ここで上下を合わせる。
    thickness_bottom_up = litho.thickness[::-1]

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
                 verbose=True):
    litho = build_lithophane(
        image_path, width_mm=width_mm, min_thickness=min_thickness,
        max_thickness=max_thickness, samples=samples, gamma=gamma,
        positive=positive, equalize=equalize, crop_box=crop_box,
        auto_face=auto_face, face_margin=face_margin, curve_deg=curve_deg,
    )

    if verbose:
        for w in litho.warnings:
            print(w)

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
        preview_path=args.preview,
    )
    print(f"書き出し完了: {args.output}  "
          f"(三角形 {len(mesh.faces):,} / watertight={mesh.is_watertight})")


if __name__ == "__main__":
    main()
