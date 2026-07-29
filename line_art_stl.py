#!/usr/bin/env python3
"""
line_art_stl.py
写真を「線の太さで濃淡を表現するタイプ」の3Dプリント用ライン・アート
(円形/六角形フレーム、線幅を明暗で変調するタイプのリソフェイン変種)に変換し、
STLファイルとして書き出すスクリプト。

使い方:
    python3 line_art_stl.py photo.jpg output.stl --shape hexagon --diameter 120
    python3 line_art_stl.py photo.jpg output.stl --shape rectangle --aspect 1.4 --auto-face

主なパラメータは下の argparse 定義を参照。

このモジュールはCLIとしてもライブラリとしても使える。
Web API(backend/)からは主に以下を呼ぶ:
    - build_artwork()          … 2Dジオメトリ(線+枠)の生成のみ(プレビュー用・高速)
    - render_preview_image()   … build_artwork() の結果をPIL Imageに描画
    - generate_stl()           … STLの書き出しまで
    - detect_face_crop_box()   … 顔検出による自動クロップ範囲の算出
"""

import argparse
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from shapely.geometry import Polygon
from shapely.ops import unary_union
import trimesh


# 3Dプリンタの最大造形サイズ(mm)。ここを超える場合のみ注意喚起する。
MAX_PRINT_SIZE_MM = 1800.0

# ピッチの基準スパン係数。--lines は「この基準スパンに何本入るか」で
# ピッチ(線の密度)を決める。実際の線の本数は形状を覆うまで自動的に増える。
PITCH_REFERENCE = 1.3


# ---------------------------------------------------------------------------
# 画像の読み込みと前処理
# ---------------------------------------------------------------------------
def _open_image(image):
    """パス / PIL.Image / numpy配列 のいずれを渡してもPIL Imageを返す"""
    if isinstance(image, Image.Image):
        return image
    if isinstance(image, np.ndarray):
        return Image.fromarray(image)
    return Image.open(image)


def center_crop_to_aspect(img, aspect=1.0):
    """
    画像の中央を 高さ/幅 = aspect の比率に切り出す。
    従来は常に正方形にクロップしていたため、--aspect != 1 のとき
    画像が縦横に引き伸ばされていた。ここで枠と同じ比率に揃える。
    """
    w, h = img.size
    if w <= 0 or h <= 0:
        return img
    target_h = w * aspect
    if target_h <= h:
        new_w, new_h = w, target_h
    else:
        new_w, new_h = h / aspect, h
    new_w = max(1, int(round(new_w)))
    new_h = max(1, int(round(new_h)))
    left = (w - new_w) // 2
    top = (h - new_h) // 2
    return img.crop((left, top, left + new_w, top + new_h))


def load_grayscale(image, crop_box=None, invert=False, autocontrast=True,
                   gamma=1.0, equalize=False, aspect=1.0):
    """
    画像を読み込み、枠と同じアスペクト比にクロップして
    グレースケール配列(0=黒, 1=白)を返す。

    crop_box: (left, top, right, bottom) の 0..1 相対座標。
    aspect:   出力枠の 高さ/幅 比率。クロップ形状をこれに合わせる。
    """
    img = _open_image(image).convert("L")

    if crop_box is not None:
        w, h = img.size
        l, t, r, b = crop_box
        left = int(round(min(l, r) * w))
        top = int(round(min(t, b) * h))
        right = int(round(max(l, r) * w))
        bottom = int(round(max(t, b) * h))
        left = max(0, min(left, w - 1))
        top = max(0, min(top, h - 1))
        right = max(left + 1, min(right, w))
        bottom = max(top + 1, min(bottom, h))
        img = img.crop((left, top, right, bottom))

    # 枠と同じ比率に中央クロップ(aspect=1.0 なら従来通りの正方形)
    img = center_crop_to_aspect(img, aspect)

    if equalize:
        img = ImageOps.equalize(img)
    if autocontrast:
        img = ImageOps.autocontrast(img, cutoff=1)
    if invert:
        img = ImageOps.invert(img)

    arr = np.asarray(img, dtype=np.float64) / 255.0  # 0=黒,1=白
    if gamma != 1.0:
        arr = np.clip(arr, 0.0, 1.0) ** gamma
    return arr  # shape (H, W)


def sample_bilinear(arr, xs, ys, Rx, Ry=None):
    """
    arr: (H,W) 0=黒,1=白 の輝度配列
    xs, ys: mm座標の配列 (同shape)。x は -Rx..Rx、y は -Ry..Ry が画像の範囲。
    範囲外は白(1.0=線なし)として扱う。

    Ry を分けているのは --aspect != 1 の長方形に対応するため
    (以前は正方形前提で、縦長の枠だと画像が縦に潰れていた)。
    """
    if Ry is None:
        Ry = Rx
    H, W = arr.shape
    px = (xs + Rx) / (2 * Rx) * (W - 1)
    py = (Ry - ys) / (2 * Ry) * (H - 1)  # 画像は上が y=+Ry

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
# 顔検出による自動クロップ
# ---------------------------------------------------------------------------
class FaceDetectionUnavailable(RuntimeError):
    """OpenCVが入っていない等で顔検出ができない場合"""


CASCADE_NAMES = (
    "haarcascade_frontalface_default.xml",
    "haarcascade_frontalface_alt2.xml",
    "haarcascade_profileface.xml",
)


def _cascade_dirs():
    """
    カスケードXMLの探索先。
    OpenCV 5.x では cv2.data にXMLが同梱されなくなったため、
    環境変数と一般的な配置場所もフォールバックとして見る。
    """
    import os
    import cv2

    dirs = []
    env = os.environ.get("HAARCASCADE_DIR")
    if env:
        dirs.append(Path(env))
    data_dir = getattr(getattr(cv2, "data", None), "haarcascades", None)
    if data_dir:
        dirs.append(Path(data_dir))
    dirs += [
        Path(cv2.__file__).parent / "data",
        Path("/usr/share/opencv4/haarcascades"),
        Path("/usr/local/share/opencv4/haarcascades"),
        Path(__file__).parent / "vendor" / "haarcascades",
    ]
    return dirs


_CASCADE_CACHE = None


def _load_cascades():
    global _CASCADE_CACHE
    if _CASCADE_CACHE is not None:
        return _CASCADE_CACHE

    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - 環境依存
        raise FaceDetectionUnavailable(
            "顔検出には OpenCV が必要です。"
            "`pip install 'opencv-python-headless>=4.8,<5'` を実行してください。"
        ) from exc

    cascades = []
    for name in CASCADE_NAMES:
        for d in _cascade_dirs():
            path = d / name
            if not path.exists():
                continue
            clf = cv2.CascadeClassifier(str(path))
            if not clf.empty():
                cascades.append(clf)
                break
    if not cascades:  # pragma: no cover - 環境依存
        raise FaceDetectionUnavailable(
            "OpenCVのカスケード分類器(haarcascade_*.xml)が見つかりませんでした。"
            "OpenCV 5.x はXMLを同梱しないため、"
            "`pip install 'opencv-python-headless>=4.8,<5'` を使うか、"
            "環境変数 HAARCASCADE_DIR でXMLのあるディレクトリを指定してください。"
        )
    _CASCADE_CACHE = cascades
    return cascades


def detect_faces(image, min_size_ratio=0.06):
    """
    画像から顔の矩形を検出する。
    戻り値: (faces, (W, H))  faces は [(x, y, w, h), ...] のピクセル座標リスト。
    OpenCVが使えない場合は FaceDetectionUnavailable を送出する。
    """
    cascades = _load_cascades()
    import cv2

    img = _open_image(image).convert("L")
    W, H = img.size

    # 大きな写真をそのまま流すと遅いので、長辺1000pxに縮めて検出し座標を戻す
    scale = min(1.0, 1000.0 / max(W, H))
    if scale < 1.0:
        det_img = img.resize((max(1, int(W * scale)), max(1, int(H * scale))),
                             Image.BILINEAR)
    else:
        det_img = img

    gray = cv2.equalizeHist(np.asarray(det_img, dtype=np.uint8))
    dw, dh = det_img.size
    min_side = max(24, int(min(dw, dh) * min_size_ratio))

    faces = []
    for clf in cascades:
        found = clf.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5,
            minSize=(min_side, min_side),
        )
        for (x, y, w, h) in found:
            faces.append((int(x / scale), int(y / scale),
                          int(w / scale), int(h / scale)))
        if faces:
            # 正面顔で見つかればプロファイル検出まで回さない(高速化)
            break
    return faces, (W, H)


def detect_face_crop_box(image, margin=0.6, aspect=1.0, vertical_bias=0.12):
    """
    顔検出の結果から、枠比率(aspect)に合わせた相対クロップ範囲を返す。

    margin:        顔の幅に対して周囲にどれだけ余白を取るか(0.6 = 顔幅の60%ずつ)
    aspect:        出力枠の 高さ/幅 比率
    vertical_bias: クロップ中心を顔中心よりどれだけ下にずらすか(顔の比率で指定)。
                   正の値で「頭上に余白、下に体」というポートレート的な構図になる。

    戻り値: (l, t, r, b) 0..1 の相対座標。顔が見つからない場合は None。
    """
    faces, (W, H) = detect_faces(image)
    if not faces:
        return None

    x0 = min(f[0] for f in faces)
    y0 = min(f[1] for f in faces)
    x1 = max(f[0] + f[2] for f in faces)
    y1 = max(f[1] + f[3] for f in faces)
    fw = max(1, x1 - x0)
    fh = max(1, y1 - y0)

    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0 + fh * vertical_bias

    # 顔を包む矩形を margin ぶん広げ、さらに枠比率に合わせる
    want_w = fw * (1.0 + 2.0 * margin)
    want_h = fh * (1.0 + 2.0 * margin)
    box_w = max(want_w, want_h / aspect)
    box_h = box_w * aspect

    # 画像からはみ出す場合は比率を保ったまま縮める
    scale = min(1.0, W / box_w, H / box_h)
    box_w *= scale
    box_h *= scale

    # 中心を画像内に収める
    cx = min(max(cx, box_w / 2.0), W - box_w / 2.0)
    cy = min(max(cy, box_h / 2.0), H - box_h / 2.0)

    l = (cx - box_w / 2.0) / W
    t = (cy - box_h / 2.0) / H
    r = (cx + box_w / 2.0) / W
    b = (cy + box_h / 2.0) / H
    return (
        float(np.clip(l, 0.0, 1.0)),
        float(np.clip(t, 0.0, 1.0)),
        float(np.clip(r, 0.0, 1.0)),
        float(np.clip(b, 0.0, 1.0)),
    )


# ---------------------------------------------------------------------------
# 枠の形状 (円 / 六角形 / 四角 / n角形)
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
    if geom is None or geom.is_empty:
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
        n = max(3, shape)
    else:
        raise ValueError(f"unknown shape: {shape}")
    offset = np.pi / 6 if shape == "hexagon" else np.pi / 2
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False) + offset
    pts = np.column_stack([r * np.cos(theta), r * np.sin(theta)])
    return Polygon(pts)


def make_frame_ring(shape_poly, frame_width):
    """
    デザイン部の外側に、どこでも同じ幅の枠(リング)を作る。

    以前は「基準半径を frame_width ぶん大きくした相似形」との差分で枠を作っていたため、
    枠の幅が一定にならなかった:
      - rectangle で aspect=2 だと上下の枠が左右の2倍の太さになる
      - 正多角形では辺の中央が角より薄くなる
    外側へ一定距離オフセット(buffer)することで、どの形状でも幅が均一になる。
    join_style=2(mitre)で角は従来どおり尖ったままにする。

    戻り値: (frame_ring, outer_poly)
    """
    if frame_width <= 0:
        return Polygon(), shape_poly
    outer = shape_poly.buffer(frame_width, join_style=2, mitre_limit=10.0)
    return to_polygonal(outer.difference(shape_poly)), outer


def shape_cover_radius(shape, r, aspect=1.0):
    """
    その形状を完全に覆うのに必要な最大半径(外接円半径)を返す。

    ここが従来のバグの本体だった: 線の生成範囲を R 基準の固定係数(1.3倍)で
    決めていたため、square でも角(R*√2 ≒ 1.414R)に届かず、
    --aspect を大きくした rectangle ではさらに大きく足りていなかった。
    正しくは 四角形なら R * hypot(1, aspect)、正多角形なら外接円半径 R。
    """
    if shape in ("square", "rectangle"):
        return float(r) * math.hypot(1.0, float(aspect))
    return float(r)


def compute_pitch(num_lines, r, pitch_reference=PITCH_REFERENCE):
    """
    --lines からピッチ(線の中心間隔)を求める。
    「基準スパン 2*r*pitch_reference に num_lines 本」という従来の密度定義を
    そのまま維持しているので、--lines の意味と既存の推奨値は変わらない。
    """
    span = 2.0 * float(r) * float(pitch_reference)
    return span / max(1, int(num_lines) - 1)


# ---------------------------------------------------------------------------
# ライン(線幅が明暗で変化するストライプ)を生成
# ---------------------------------------------------------------------------
def build_line_polygons(arr, Rx, Ry, cover_r, pitch, angle_deg, min_hw, max_hw,
                        samples_per_line=400):
    """
    cover_r: 枠を完全に覆うのに必要な半径(shape_cover_radius の戻り値)。
             線の本数・長さともにこの値から決めるので、
             どんな aspect でも必ず角まで線が届く。
    pitch:   線の中心間隔(mm)。compute_pitch() で算出。
    """
    angle = np.radians(angle_deg)
    cos_a, sin_a = np.cos(angle), np.sin(angle)

    # 角まで確実に届くよう、覆う半径に少しだけ余裕を持たせる
    reach = cover_r * 1.05
    L = reach                      # 線方向の半長
    v_max = reach + max_hw         # 線に直交する方向の生成範囲

    n_half = int(math.ceil(v_max / pitch)) if pitch > 0 else 0
    v_centers = np.arange(-n_half, n_half + 1, dtype=np.float64) * pitch

    u_vals = np.linspace(-L, L, max(2, int(samples_per_line)))

    polygons = []
    for v in v_centers:
        # サンプリング点 (u方向に一列)。まず中心線上の点でその位置の明暗を取得
        x_line = u_vals * cos_a - v * sin_a
        y_line = u_vals * sin_a + v * cos_a
        brightness = sample_bilinear(arr, x_line, y_line, Rx, Ry)
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
# 安全性チェック(線幅とピッチのバランス)
# ---------------------------------------------------------------------------
def check_line_width_safety(pitch, min_line_width, max_line_width,
                            min_gap_ratio=0.25, min_width_floor=0.4):
    """
    ピッチに対して線の太さが適切かをチェックする。
    - 最大太さの時にも隙間(gap)が pitch の min_gap_ratio 以上残っているか
      (太すぎ+近すぎだと影絵効果が失われる)
    - 最小太さが min_width_floor 以上あるか(細すぎると造形が安定しない)
    問題があれば日本語の警告メッセージを返す(問題なければ空リスト)。

    注意: これは「線幅」に関する助言であり、作品サイズ(diameter)には関与しない。
    サイズは MAX_PRINT_SIZE_MM までは何の警告も出さない。
    """
    warnings = []
    if max_line_width > pitch * (1 - min_gap_ratio):
        safe_max = pitch * (1 - min_gap_ratio)
        warnings.append(
            f"警告: 現在のピッチ({pitch:.2f}mm)に対して最大線幅({max_line_width}mm)が太すぎます。"
            f"隙間が狭くなりすぎて陰影効果が失われる/線同士がくっつく恐れがあります。"
            f"最大線幅を {safe_max:.2f}mm 以下にするか、線の本数を減らしてピッチを広げてください。"
        )
    if min_line_width < min_width_floor:
        warnings.append(
            f"警告: 最小線幅({min_line_width}mm)が細すぎる可能性があります。"
            f"造形が安定しない/ちぎれる恐れがあるため、{min_width_floor}mm 以上を推奨します。"
        )
    return warnings


def check_print_size(width_mm, height_mm, max_size=MAX_PRINT_SIZE_MM):
    """造形サイズが上限を超えている場合だけ警告する(上限内なら完全に無警告)。"""
    warnings = []
    if width_mm > max_size or height_mm > max_size:
        warnings.append(
            f"警告: 外形サイズ {width_mm:.0f} x {height_mm:.0f} mm が"
            f"プリンタの最大造形サイズ {max_size:.0f}mm を超えています。"
        )
    return warnings


# ---------------------------------------------------------------------------
# 2Dジオメトリの生成(プレビューとSTLで共有)
# ---------------------------------------------------------------------------
@dataclass
class Artwork:
    """2D形状の生成結果。プレビュー描画にもメッシュ化にもこれを使う。"""
    lines_area: object          # shapely Polygon / MultiPolygon
    frame_ring: object          # shapely Polygon / MultiPolygon
    half_extent: float          # 描画範囲(枠外周までの半径)
    outer_width: float          # 外形の幅(mm)
    outer_height: float         # 外形の高さ(mm)
    design_width: float         # 枠を含まないデザイン部の幅(mm)
    design_height: float        # 枠を含まないデザイン部の高さ(mm)
    pitch: float                # 線の中心間隔(mm)
    line_count: int             # 実際に生成した線の本数
    warnings: list = field(default_factory=list)


def build_artwork(image, shape="hexagon", diameter=120.0, aspect=1.0,
                  num_lines=70, angle_deg=20.0, min_line_width=0.35,
                  max_line_width=2.6, frame_width=8.0, gamma=1.0,
                  invert=False, equalize=False, crop_box=None,
                  auto_face=False, face_margin=0.6, samples_per_line=400):
    """
    画像とパラメータから2Dジオメトリ(線の集合と枠のリング)を生成する。
    STL化を伴わないため、プレビュー用途ではこれだけを呼べばよい。
    """
    R = float(diameter) / 2.0
    aspect = float(aspect)

    if auto_face and crop_box is None:
        crop_box = detect_face_crop_box(image, margin=face_margin, aspect=aspect)

    arr = load_grayscale(image, crop_box=crop_box, invert=invert,
                         gamma=gamma, equalize=equalize, aspect=aspect)

    shape_poly = make_shape_polygon(shape, R, aspect)

    # 画像がマッピングされる範囲。四角形は高さが R*aspect になる。
    if shape in ("square", "rectangle"):
        Rx, Ry = R, R * aspect
    else:
        Rx = Ry = R

    cover_r = shape_cover_radius(shape, R, aspect)
    pitch = compute_pitch(num_lines, R)

    warnings = check_line_width_safety(pitch, min_line_width, max_line_width)

    line_polys_raw = build_line_polygons(
        arr, Rx, Ry, cover_r, pitch, angle_deg,
        min_line_width / 2.0, max_line_width / 2.0,
        samples_per_line=samples_per_line,
    )

    # 枠の内側でクリップ
    clipped = []
    for p in line_polys_raw:
        c = p.intersection(shape_poly)
        if c.is_empty:
            continue
        if c.geom_type == "Polygon":
            clipped.append(c)
        elif c.geom_type in ("MultiPolygon", "GeometryCollection"):
            clipped.extend([g for g in c.geoms if g.geom_type == "Polygon"])

    lines_area = to_polygonal(unary_union(clipped)) if clipped else Polygon()

    # 外枠(フレームのリング)。幅がどこでも一定になるよう外側にオフセットする。
    frame_ring, outer_poly = make_frame_ring(shape_poly, frame_width)

    minx, miny, maxx, maxy = outer_poly.bounds
    outer_width = maxx - minx
    outer_height = maxy - miny
    half_extent = max(abs(minx), abs(maxx), abs(miny), abs(maxy))

    # デザイン部の実寸は形状によって異なる(六角形は幅と高さが違う)ので
    # 直径から推定せず、実際のポリゴンの外接矩形から取る。
    dminx, dminy, dmaxx, dmaxy = shape_poly.bounds
    design_width = dmaxx - dminx
    design_height = dmaxy - dminy

    warnings += check_print_size(outer_width, outer_height)

    return Artwork(
        lines_area=lines_area,
        frame_ring=frame_ring,
        half_extent=half_extent,
        outer_width=outer_width,
        outer_height=outer_height,
        design_width=design_width,
        design_height=design_height,
        pitch=pitch,
        line_count=len(line_polys_raw),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# メイン処理: 画像 -> STL
# ---------------------------------------------------------------------------
def build_mesh(art, thickness=2.0, frame_thickness=2.0):
    """
    Artwork(2Dジオメトリ)を押し出して1つのtrimeshにする。

    線と枠は枠の内周でぴったり接しているため、別々に押し出して concatenate すると
    その境界で4枚の面が1本の辺を共有する非多様体(non-manifold)エッジになる。
    厚みが同じ場合は2Dの段階で結合してから一度に押し出すことでこれを回避する。
    厚みが異なる場合は形状として段差があるので、従来どおり別々に押し出す。
    """
    if abs(thickness - frame_thickness) < 1e-9:
        merged = to_polygonal(unary_union([art.lines_area, art.frame_ring]))
        mesh = extrude_any(merged, thickness)
        if mesh is None:
            raise RuntimeError("生成されたジオメトリが空です。パラメータを見直してください。")
        mesh.merge_vertices()
        return mesh

    meshes = []
    lines_mesh = extrude_any(art.lines_area, thickness)
    if lines_mesh is not None:
        meshes.append(lines_mesh)
    frame_mesh = extrude_any(art.frame_ring, frame_thickness)
    if frame_mesh is not None:
        meshes.append(frame_mesh)
    if not meshes:
        raise RuntimeError("生成されたジオメトリが空です。パラメータを見直してください。")

    combined = trimesh.util.concatenate(meshes)
    combined.merge_vertices()
    return combined


def generate_stl(image_path, output_path, shape="hexagon", diameter=120.0,
                 aspect=1.0, num_lines=70, angle_deg=20.0, min_line_width=0.35,
                 max_line_width=2.6, thickness=2.0, frame_width=8.0,
                 frame_thickness=2.0, gamma=1.0, invert=False,
                 equalize=False, crop_box=None, preview_path=None,
                 auto_face=False, face_margin=0.6, samples_per_line=400,
                 verbose=True):

    art = build_artwork(
        image_path, shape=shape, diameter=diameter, aspect=aspect,
        num_lines=num_lines, angle_deg=angle_deg,
        min_line_width=min_line_width, max_line_width=max_line_width,
        frame_width=frame_width, gamma=gamma, invert=invert,
        equalize=equalize, crop_box=crop_box, auto_face=auto_face,
        face_margin=face_margin, samples_per_line=samples_per_line,
    )

    if verbose:
        for w in art.warnings:
            print(w)

    if preview_path:
        save_preview_png(art, preview_path)

    # --- 3Dメッシュ化 ---
    combined = build_mesh(art, thickness=thickness, frame_thickness=frame_thickness)

    if output_path is not None:
        combined.export(output_path)
    return combined


# ---------------------------------------------------------------------------
# プレビュー描画
# ---------------------------------------------------------------------------
def render_preview_image(art, size=900, bg=(222, 201, 158), fg=(20, 20, 20)):
    """
    3D化する前の2D形状をプレビュー画像(PIL Image)として描画する。
    PILで逐次描画する: 各ポリゴンについて「外形を塗る→自分の穴を背景色で塗り戻す」を
    その場で行うため、描画順に依存する不具合(前段の穴が後段の図形を隠す等)が起きない。
    この前提を崩さないよう注意すること。
    """
    from PIL import ImageDraw

    ext = art.half_extent * 1.05
    if ext <= 0:
        ext = 1.0

    # 外形の縦横比に合わせたキャンバス(長辺が size になる)
    ow = max(art.outer_width, 1e-6)
    oh = max(art.outer_height, 1e-6)
    if ow >= oh:
        W = int(size)
        H = max(1, int(round(size * oh / ow)))
        ext_x = ext
        ext_y = ext * oh / ow
    else:
        H = int(size)
        W = max(1, int(round(size * ow / oh)))
        ext_y = ext
        ext_x = ext * ow / oh

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    def to_px(pt):
        x, y = pt[0], pt[1]
        return ((x + ext_x) / (2 * ext_x) * W, (ext_y - y) / (2 * ext_y) * H)

    def draw_poly(poly):
        if poly is None or poly.is_empty:
            return
        geoms = (list(poly.geoms)
                 if poly.geom_type in ("MultiPolygon", "GeometryCollection")
                 else [poly])
        for g in geoms:
            if g.is_empty or g.geom_type != "Polygon":
                continue
            draw.polygon([to_px(p) for p in g.exterior.coords], fill=fg)
            for interior in g.interiors:
                draw.polygon([to_px(p) for p in interior.coords], fill=bg)

    draw_poly(art.frame_ring)
    draw_poly(art.lines_area)
    return img


def save_preview_png(art, path, size=900, bg=(222, 201, 158), fg=(20, 20, 20)):
    """プレビュー画像をPNGとして保存する。"""
    render_preview_image(art, size=size, bg=bg, fg=fg).save(path)


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
    ap.add_argument("--lines", type=int, default=48, help="線の本数(密度の基準)")
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
    ap.add_argument("--auto-face", action="store_true",
                    help="OpenCVの顔検出で自動クロップする(--crop 指定時はそちらを優先)")
    ap.add_argument("--face-margin", type=float, default=0.6,
                    help="--auto-face のとき顔の周囲に取る余白(顔幅に対する比率)")
    ap.add_argument("--samples", type=int, default=400,
                    help="1本の線あたりのサンプリング数(大きいほど高精細・低速)")
    ap.add_argument("--preview", help="2Dプレビューpng出力パス(任意)")
    args = ap.parse_args()

    shape = args.sides if args.sides else args.shape

    crop_box = tuple(args.crop) if args.crop else None
    auto_face = args.auto_face
    if crop_box is not None and auto_face:
        print("注意: --crop が指定されているため --auto-face は無視します。")
        auto_face = False

    if auto_face:
        try:
            detected = detect_face_crop_box(args.image, margin=args.face_margin,
                                            aspect=args.aspect)
            if detected is None:
                print("注意: 顔を検出できませんでした。中央クロップにフォールバックします。")
            else:
                l, t, r, b = detected
                print(f"顔検出クロップ: L={l:.3f} T={t:.3f} R={r:.3f} B={b:.3f}")
        except FaceDetectionUnavailable as exc:
            print(f"注意: {exc} 中央クロップにフォールバックします。")
            detected = None
        crop_box = detected
        auto_face = False  # 上でクロップ済み

    generate_stl(
        args.image, args.output, shape=shape, diameter=args.diameter,
        aspect=args.aspect, num_lines=args.lines, angle_deg=args.angle,
        min_line_width=args.min_width, max_line_width=args.max_width,
        thickness=args.thickness, frame_width=args.frame_width,
        frame_thickness=args.frame_thickness, gamma=args.gamma,
        invert=args.invert, equalize=args.equalize,
        crop_box=crop_box, preview_path=args.preview,
        auto_face=auto_face, face_margin=args.face_margin,
        samples_per_line=args.samples,
    )
    print(f"書き出し完了: {args.output}")


if __name__ == "__main__":
    main()
