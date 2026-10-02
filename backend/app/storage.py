"""
アップロード画像の一時保管。

- 画像は起動時に作られる作業ディレクトリに保存する(既定はOSのtemp配下)。
- image_id は32桁のhexのみを許可し、パス・トラバーサルを防ぐ。
- 一定時間(既定6時間)を過ぎたファイルは、次のアップロード時に掃除する。
"""

from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir

from PIL import Image, ImageOps

# 保存先。環境変数 PSA_DATA_DIR で差し替え可能。
DATA_DIR = Path(os.environ.get("PSA_DATA_DIR")
                or Path(gettempdir()) / "photo-shadow-art-uploads")

# アップロード上限とサーバ内部で保持する解像度の上限
MAX_UPLOAD_BYTES = int(os.environ.get("PSA_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
MAX_STORED_PIXELS = int(os.environ.get("PSA_MAX_STORED_PIXELS", 2400))
TTL_SECONDS = int(os.environ.get("PSA_UPLOAD_TTL_SECONDS", 6 * 60 * 60))

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class StorageError(ValueError):
    """不正なIDや壊れた画像など、呼び出し側の入力に起因するエラー"""


@dataclass
class StoredImage:
    image_id: str
    path: Path
    width: int
    height: int


def ensure_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _path_for(image_id: str) -> Path:
    if not _ID_RE.match(image_id or ""):
        raise StorageError("不正な image_id です。")
    return ensure_dir() / f"{image_id}.png"


def cleanup_expired(ttl_seconds: int = TTL_SECONDS) -> int:
    """期限切れのアップロードを削除し、削除件数を返す。"""
    if not DATA_DIR.exists():
        return 0
    cutoff = time.time() - ttl_seconds
    removed = 0
    for f in DATA_DIR.glob("*.png"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def save_upload(data: bytes) -> StoredImage:
    """
    アップロードされたバイト列を検証し、正規化(EXIF回転の適用・縮小・RGB化)して保存する。
    """
    if not data:
        raise StorageError("空のファイルです。")
    if len(data) > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES / 1024 / 1024
        raise StorageError(f"ファイルが大きすぎます(上限 {limit_mb:.0f}MB)。")

    import io

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:  # noqa: BLE001 - Pillowは多様な例外を投げる
        raise StorageError("画像として読み込めませんでした。") from exc

    # スマホ写真のEXIF回転を反映しておく(以降は素直に扱える)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    w, h = img.size
    scale = min(1.0, MAX_STORED_PIXELS / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                         Image.LANCZOS)

    cleanup_expired()

    image_id = uuid.uuid4().hex
    path = _path_for(image_id)
    img.save(path, format="PNG")
    return StoredImage(image_id=image_id, path=path,
                       width=img.size[0], height=img.size[1])


def get_path(image_id: str) -> Path:
    """保存済み画像のパスを返す。存在しなければ StorageError。"""
    path = _path_for(image_id)
    if not path.exists():
        raise StorageError("画像が見つかりません。再度アップロードしてください。")
    # アクセスのたびにTTLを延ばす(調整中に消えないように)
    try:
        os.utime(path, None)
    except OSError:
        pass
    return path
