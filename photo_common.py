#!/usr/bin/env python3
"""
photo_common.py
シャドウアート(line_art_stl.py)とリソフェイン(lithophane_stl.py)で共通して使う、
画像の読み込み・前処理・顔検出。

両方の生成方式で「同じ写真を同じようにクロップして同じ明暗補正をかける」
必要があるため、ここに一本化してある。
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

# 3Dプリンタの最大造形サイズ(mm)。ここを超える場合のみ注意喚起する。
MAX_PRINT_SIZE_MM = 1800.0


# ---------------------------------------------------------------------------
# 画像の読み込みと前処理
# ---------------------------------------------------------------------------
def open_image(image):
    """パス / PIL.Image / numpy配列 のいずれを渡してもPIL Imageを返す"""
    if isinstance(image, Image.Image):
        return image
    if isinstance(image, np.ndarray):
        return Image.fromarray(image)
    return Image.open(image)


def center_crop_to_aspect(img, aspect=1.0):
    """
    画像の中央を 高さ/幅 = aspect の比率に切り出す。
    aspect=None のときは何もしない(元の比率のまま)。
    """
    if aspect is None:
        return img
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


def apply_crop_box(img, crop_box):
    """0..1 の相対座標 (left, top, right, bottom) で切り出す"""
    if crop_box is None:
        return img
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
    return img.crop((left, top, right, bottom))


def load_grayscale(image, crop_box=None, invert=False, autocontrast=True,
                   gamma=1.0, equalize=False, aspect=1.0):
    """
    画像を読み込み、グレースケール配列(0=黒, 1=白)を返す。

    crop_box: (left, top, right, bottom) の 0..1 相対座標。
    aspect:   出力枠の 高さ/幅 比率。クロップ形状をこれに合わせる。
              None を渡すとクロップ後の比率をそのまま使う(リソフェイン用)。
    """
    img = open_image(image).convert("L")
    img = apply_crop_box(img, crop_box)
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

    img = open_image(image).convert("L")
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
# 造形サイズのチェック
# ---------------------------------------------------------------------------
def check_print_size(width_mm, height_mm, depth_mm=0.0, max_size=MAX_PRINT_SIZE_MM):
    """造形サイズが上限を超えている場合だけ警告する(上限内なら完全に無警告)。"""
    warnings = []
    if width_mm > max_size or height_mm > max_size or depth_mm > max_size:
        dims = f"{width_mm:.0f} x {height_mm:.0f}"
        if depth_mm > 0:
            dims += f" x {depth_mm:.0f}"
        warnings.append(
            f"警告: 外形サイズ {dims} mm が"
            f"プリンタの最大造形サイズ {max_size:.0f}mm を超えています。"
        )
    return warnings
