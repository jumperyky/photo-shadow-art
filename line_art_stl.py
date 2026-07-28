#!/usr/bin/env python3
"""
line_art_stl.py
写真を「線の太さで濃淡を表現するタイプ」の3Dプリント用ライン・アート
(円形/六角形フレーム、線幅を明暗で変調するタイプのリソフェイン変種)に変換し、
STLファイルとして書き出すスクリプト。

使い方:
    python3 line_art_stl.py photo.jpg output.stl --shape hexagon --diameter 120

主なパラメータは下の argparse 定義を参照。
"""

import argparse
import numpy as np
from PIL import Image, ImageOps
from shapely.geometry import Polygon
from shapely.ops import unary_union
import trimesh


# ---------------------------------------------------------------------------
# 画像の読み込みと前処理
# ---------------------------------------------------------------------------
def load_grayscale(image_path, crop_box=None, invert=False, autocontrast=True,
                    gamma=1.0, equalize=False):
    """画像を読み込み、正方形にクロップしてグレースケール配列(0=黒,1=白)を返す"""
    img = Image.open(image_path).convert("L")

    if crop_box is not None:
        # crop_box = (left, top, right, bottom) 0..1 の相対座標
        w, h = img.size
        l, t, r, b = crop_box
        img = img.crop((int(l * w), int(t * h), int(r * w), int(b * h)))

    # 中央を正方形にクロップ(円/六角形の枠に合わせるため)
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    if equalize:
        img = ImageOps.equalize(img)
    if autocontrast:
        img = ImageOps.autocontrast(img, cutoff=1)
    if invert:
        img = ImageOps.invert(img)

    arr = np.asarray(img, dtype=np.float64) / 255.0  # 0=黒,1=白
    if gamma != 1.0:
        arr = arr ** gamma
    return arr  # shape (H, W)


def sample_bilinear(arr, xs, ys, R):
    """
    arr: (H,W) 0=黒,1=白 の輝度配列
    xs, ys: mm座標 (-R..R) の配列 (同shape)
    範囲外は白(1.0=線なし)として扱う
    """
    H, W = arr.shape
    px = (xs + R) / (2 * R) * (W - 1)
    py = (R - ys) / (2 * R) * (H - 1)  # 画像は上が y=+R

    out_of_range = (px < 0) | (px > W - 1) | (py < 0) | (py > H - 1)
    px_c = np.clip(px, 0, W - 1)
    py_c = np.clip(py, 0, H - 1)

    x0 = np.floor(px_c).astype(int)
    x1 = np.clip(x0 + 1, 0, W - 1)
    y0 = np.floor(py_c).astype(int)
    y1 = np.clip(y0 + 1, 0, H - 1)

    fx = px_c - x0
    fy = py_c - y0

    v00 = arr[y0, x0]
    v10 = arr[y0, x1]
    v01 = arr[y1, x0]
    v11 = arr[y1, x1]

    val = (v00 * (1 - fx) * (1 - fy) + v10 * fx * (1 - fy) +
           v01 * (1 - fx) * fy + v11 * fx * fy)
    val = np.where(out_of_range, 1.0, val)
    return val


# ---------------------------------------------------------------------------
# 枠の形状 (円 / 六角形)
# ---------------------------------------------------------------------------
def to_polygonal(geom):
    """GeometryCollection等からPolygon/MultiPolygon成分だけを取り出す"""
    from shapely.geometry import MultiPolygon
    if geom.is_empty:
        return geom
    if geom.geom_type == "Polygon":
        return geom
    if geom.geom_type == "MultiPolygon":
        return geom
    if geom.geom_type == "GeometryCollection":
        polys = [g for g in geom.geoms if g.geom_type == "Polygon"]
        if not polys:
            return Polygon()
        if len(polys) == 1:
            return polys[0]
        return MultiPolygon(polys)
    return Polygon()


def extrude_any(geom, height):
    """Polygon / MultiPolygon どちらでも押し出してtrimeshを1つ返す"""
    if geom.is_empty:
        return None
    if geom.geom_type == "Polygon":
        polys = [geom]
    elif geom.geom_type == "MultiPolygon":
        polys = list(geom.geoms)
    else:
        return None
    meshes = []
    for p in polys:
        if p.is_empty or p.area <= 0:
            continue
        meshes.append(trimesh.creation.extrude_polygon(p, height))
    if not meshes:
        return None
    if len(meshes) == 1:
        return meshes[0]
    return trimesh.util.concatenate(meshes)


def make_shape_polygon(shape, r, aspect=1.0):
    """
    shape: 'circle' / 'hexagon' / 'square' / 'rectangle' / 整数(n角形の頂点数)
    r: 基準半径(四角の場合は半幅)
    aspect: 'square'/'rectangle' のときの 高さ/幅 比率
    形状を後から自由に切り替えられるよう、ここに追加すれば他は変更不要。
    """
    if shape in ("square", "rectangle"):
        from shapely.geometry import box
        h = r * aspect
        return box(-r, -h, r, h)
    if shape == "circle":
        n = 240
    elif shape == "hexagon":
        n = 6
    elif isinstance(shape, int):
        n = shape
    else:
        raise ValueError(f"unknown shape: {shape}")
    offset = np.pi / 6 if shape == "hexagon" else np.pi / 2
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False) + offset
    pts = np.column_stack([r * np.cos(theta), r * np.sin(theta)])
    return Polygon(pts)


# ---------------------------------------------------------------------------
# ライン(線幅が明暗で変化するストライプ)を生成
# ---------------------------------------------------------------------------
def build_line_polygons(arr, R, num_lines, angle_deg, min_hw, max_hw,
                         samples_per_line=400):
    angle = np.radians(angle_deg)
    cos_a, sin_a = np.cos(angle), np.sin(angle)

    L = R * 1.5  # 線方向の半長(枠の外まで余裕を持たせて、後でクリップする)
    v_centers = np.linspace(-R * 1.3, R * 1.3, num_lines)
    u_vals = np.linspace(-L, L, samples_per_line)

    polygons = []
    for v in v_centers:
        # サンプリング点 (u方向に一列)。まず中心線上の点でその位置の明暗を取得
        x_line = u_vals * cos_a - v * sin_a
        y_line = u_vals * sin_a + v * cos_a
        brightness = sample_bilinear(arr, x_line, y_line, R)
        darkness = 1.0 - brightness  # 0=白(線なし側),1=黒(太い)
        half_w = min_hw + (max_hw - min_hw) * darkness

        # 上端・下端の座標 (v方向にオフセット)
        top_x = u_vals * cos_a - (v + half_w) * sin_a
        top_y = u_vals * sin_a + (v + half_w) * cos_a
        bot_x = u_vals * cos_a - (v - half_w) * sin_a
        bot_y = u_vals * sin_a + (v - half_w) * cos_a

        coords = list(zip(top_x, top_y)) + list(zip(bot_x[::-1], bot_y[::-1]))
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        polygons.append(poly)
    return polygons


# ---------------------------------------------------------------------------
# メイン処理: 画像 -> STL
# ---------------------------------------------------------------------------
def check_line_width_safety(num_lines, r_extent, min_line_width, max_line_width,
                             min_gap_ratio=0.25, min_width_floor=0.4):
    """
    ピッチに対して線の太さが適切かをチェックする。
    - 最大太さの時にも隙間(gap)が pitch の min_gap_ratio 以上残っているか
      (太すぎ+近すぎだと影絵効果が失われる)
    - 最小太さが min_width_floor 以上あるか(細すぎると造形が安定しない)
    問題があれば日本語の警告メッセージを返す(問題なければ空リスト)。
    """
    pitch = (2 * r_extent * 1.3) / max(1, (num_lines - 1))
    warnings = []
    if max_line_width > pitch * (1 - min_gap_ratio):
        safe_max = pitch * (1 - min_gap_ratio)
        warnings.append(
            f"警告: 現在のピッチ({pitch:.2f}mm)に対して最大線幅({max_line_width}mm)が太すぎます。"
            f"隙間が狭くなりすぎて陰影効果が失われる/線同士がくっつく恐れがあります。"
            f"--max-width を {safe_max:.2f}mm 以下にするか、--lines を減らしてピッチを広げてください。"
        )
    if min_line_width < min_width_floor:
        warnings.append(
            f"警告: 最小線幅({min_line_width}mm)が細すぎる可能性があります。"
            f"造形が安定しない/ちぎれる恐れがあるため、{min_width_floor}mm 以上を推奨します。"
        )
    return warnings, pitch


def generate_stl(image_path, output_path, shape="hexagon", diameter=120.0,
                  aspect=1.0, num_lines=70, angle_deg=20.0, min_line_width=0.35,
                  max_line_width=2.6, thickness=2.0, frame_width=8.0,
                  frame_thickness=2.0, gamma=1.0, invert=False,
                  equalize=False, crop_box=None, preview_path=None):

    R = diameter / 2.0

    warnings, pitch = check_line_width_safety(num_lines, R, min_line_width, max_line_width)
    for w in warnings:
        print(w)

    arr = load_grayscale(image_path, crop_box=crop_box, invert=invert,
                          gamma=gamma, equalize=equalize)

    shape_poly = make_shape_polygon(shape, R, aspect)

    line_polys_raw = build_line_polygons(
        arr, R, num_lines, angle_deg, min_line_width / 2.0, max_line_width / 2.0
    )

    # 枠の内側でクリップ
    clipped = []
    for p in line_polys_raw:
        c = p.intersection(shape_poly)
        if c.is_empty:
            continue
        if c.geom_type == "Polygon":
            clipped.append(c)
        elif c.geom_type == "MultiPolygon":
            clipped.extend(list(c.geoms))

    lines_area = to_polygonal(unary_union(clipped))

    # 外枠(フレームのリング)
    outer_poly = make_shape_polygon(shape, R + frame_width, aspect)
    frame_ring = to_polygonal(outer_poly.difference(shape_poly))

    if preview_path:
        save_preview_png(lines_area, frame_ring, R + frame_width, preview_path)

    # --- 3Dメッシュ化 ---
    meshes = []

    lines_mesh = extrude_any(lines_area, thickness)
    if lines_mesh is not None:
        meshes.append(lines_mesh)

    frame_mesh = extrude_any(frame_ring, frame_thickness)
    if frame_mesh is not None:
        meshes.append(frame_mesh)

    if not meshes:
        raise RuntimeError("生成されたジオメトリが空です。パラメータを見直してください。")

    combined = trimesh.util.concatenate(meshes)
    combined.merge_vertices()

    combined.export(output_path)
    return combined


def save_preview_png(lines_area, frame_ring, half_extent, path, size=900,
                      bg=(222, 201, 158), fg=(20, 20, 20)):
    """
    3D化する前の2D形状を簡易プレビューPNGとして保存(確認用)。
    PILで逐次描画する: 各ポリゴンについて「外形を塗る→自分の穴を背景色で塗り戻す」を
    その場で行うため、描画順に依存する不具合(前段の穴が後段の図形を隠す等)が起きない。
    """
    from PIL import Image, ImageDraw

    ext = half_extent * 1.05
    W = H = int(size)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    def to_px(pt):
        x, y = pt
        return ((x + ext) / (2 * ext) * W, (ext - y) / (2 * ext) * H)

    def draw_poly(poly):
        if poly is None or poly.is_empty:
            return
        geoms = list(poly.geoms) if poly.geom_type in ("MultiPolygon", "GeometryCollection") else [poly]
        for g in geoms:
            if g.is_empty or g.geom_type != "Polygon":
                continue
            draw.polygon([to_px(p) for p in g.exterior.coords], fill=fg)
            for interior in g.interiors:
                draw.polygon([to_px(p) for p in interior.coords], fill=bg)

    draw_poly(frame_ring)
    draw_poly(lines_area)
    img.save(path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="写真をライン・アート3DプリントSTLに変換")
    ap.add_argument("image", help="入力画像パス")
    ap.add_argument("output", help="出力STLパス")
    ap.add_argument("--shape", choices=["circle", "hexagon", "square", "rectangle"],
                     default="square", help="外枠の形状(六角形/円/四角/長方形)")
    ap.add_argument("--sides", type=int, default=None,
                     help="任意のn角形にしたい場合の頂点数(指定すると--shapeより優先)")
    ap.add_argument("--aspect", type=float, default=1.0,
                     help="square/rectangleのときの 高さ/幅 比率")
    ap.add_argument("--diameter", type=float, default=150.0,
                     help="内側デザイン部分の直径、または四角の場合は幅(mm)")
    ap.add_argument("--lines", type=int, default=48, help="線の本数")
    ap.add_argument("--angle", type=float, default=20.0, help="線の角度(度)")
    ap.add_argument("--min-width", type=float, default=0.5, help="最小線幅(mm)")
    ap.add_argument("--max-width", type=float, default=2.9, help="最大線幅(mm)")
    ap.add_argument("--thickness", type=float, default=2.0, help="押し出し厚み(mm)")
    ap.add_argument("--frame-width", type=float, default=8.0, help="外枠の幅(mm)")
    ap.add_argument("--frame-thickness", type=float, default=2.0, help="外枠の厚み(mm)")
    ap.add_argument("--gamma", type=float, default=1.0, help="明暗のコントラスト調整(>1で暗部強調)")
    ap.add_argument("--invert", action="store_true", help="明暗反転")
    ap.add_argument("--equalize", action="store_true", help="ヒストグラム均等化")
    ap.add_argument("--crop", type=float, nargs=4, metavar=("L", "T", "R", "B"),
                     help="相対クロップ範囲 0..1 (例 顔中心に寄せる場合など)")
    ap.add_argument("--preview", help="2Dプレビューpng出力パス(任意)")
    args = ap.parse_args()

    shape = args.sides if args.sides else args.shape
    generate_stl(
        args.image, args.output, shape=shape, diameter=args.diameter,
        aspect=args.aspect, num_lines=args.lines, angle_deg=args.angle,
        min_line_width=args.min_width, max_line_width=args.max_width,
        thickness=args.thickness, frame_width=args.frame_width,
        frame_thickness=args.frame_thickness, gamma=args.gamma,
        invert=args.invert, equalize=args.equalize,
        crop_box=tuple(args.crop) if args.crop else None,
        preview_path=args.preview,
    )
    print(f"書き出し完了: {args.output}")


if __name__ == "__main__":
    main()
