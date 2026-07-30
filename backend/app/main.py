"""
Photo Shadow Art — Web API

Next.jsのUIから2種類のSTL生成を呼び出すFastAPIサーバー。

    shadow_art  … line_art_stl.py  (線の太さで濃淡を表現)
    lithophane  … lithophane_stl.py (厚みで濃淡を表現)

どちらも「アップロード → クロップ → パラメータ調整 → プレビュー → STL」の
流れは共通で、リクエストの `mode` で処理を分岐する。

起動:
    cd backend && uvicorn app.main:app --reload --port 8000
    (または ../dev.sh)

エンドポイント:
    GET  /api/health        死活監視
    GET  /api/config        既定値・上限・顔検出の可否(モードごと)
    POST /api/upload        画像アップロード
    GET  /api/images/{id}   アップロード済み画像の取得(クロップUI表示用)
    POST /api/detect-face   顔検出による自動クロップ範囲の算出
    POST /api/preview       パラメータからPNGプレビューを生成
    POST /api/mesh          3Dプレビュー用の軽量メッシュ(独自バイナリ)
    POST /api/stl           STLを生成してダウンロード
"""

from __future__ import annotations

import base64
import io
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote

import numpy as np
from fastapi import Body, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

# リポジトリ直下のモジュールを import できるようにする
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import line_art_stl as la  # noqa: E402
import lithophane_stl as lp  # noqa: E402
import photo_common as pc  # noqa: E402

from . import storage  # noqa: E402
from .schemas import (  # noqa: E402
    AnyMeshRequest,
    AnyPreviewRequest,
    AnyStlRequest,
    ConfigResponse,
    CropBox,
    FaceDetectRequest,
    FaceDetectResponse,
    FaceRect,
    LithophaneMeshRequest,
    LithophanePreviewRequest,
    LithophaneStlRequest,
    ModeInfo,
    PreviewResponse,
    ShadowArtPreviewRequest,
    SizeInfo,
    UploadResponse,
)

app = FastAPI(title="Photo Shadow Art API", version="2.0.0")

# 開発時は localhost の Next.js から叩く。PSA_CORS_ORIGINS で上書き可能。
_origins = os.environ.get(
    "PSA_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# シャドウアートの線のサンプリング密度。プレビューは粗く、STLは細かく。
SHADOW_SAMPLES = {"preview": 220, "draft": 260, "normal": 420, "fine": 700}

# リソフェインの分割数の倍率。ユーザー指定の samples に対して品質で調整する。
LITHO_QUALITY_SCALE = {"draft": 0.5, "normal": 1.0, "fine": 1.5}

# 3Dプレビューの解像度。実測で medium なら
#   シャドウアート 約2.2万面 / 0.4MB、リソフェイン 約7.7万面 / 1.3MB
# に収まり、生成も0.2秒以内。回転させながら調整できる程度の軽さを優先する。
MESH_SHADOW_SAMPLES = {"low": 90, "medium": 140}
MESH_LITHO_SAMPLES = {"low": 80, "medium": 120}

# --- プレビューの配色 -------------------------------------------------------
# シャドウアートの2Dプレビューの背景。線と同化しないよう、フィラメントが
# 暗ければ淡いタン、明るければ暗い紙に切り替える。背景は「線の隙間から
# 透けて見えるもの」であって造形物の一部ではないので、色は自由に選べる。
PREVIEW_BACKDROP_LIGHT = (222, 201, 158)
PREVIEW_BACKDROP_DARK = (38, 42, 50)
BACKDROP_SWITCH_LUMA = 0.45

# リソフェインの透過光(電球色)。フィラメントの色相にこれを掛けて色味を作る。
LITHO_LIGHT = (255, 244, 224)
# これより暗いフィラメントは光をほとんど通さないので注意を出す
LITHO_DARK_LUMA = 0.18

SHADOW_ART_DEFAULTS = {
    "shape": "square", "aspect": 1.0, "diameter": 150.0, "lines": 48,
    "angle": 20.0, "min_width": 0.5, "max_width": 2.9,
    "thickness": 2.0, "frame_width": 8.0, "frame_thickness": 2.0,
    "gamma": 1.0, "invert": False, "equalize": False,
    "auto_face": False, "face_margin": 0.6,
}

LITHOPHANE_DEFAULTS = {
    "width": 100.0, "min_thickness": 0.6, "max_thickness": 3.0,
    "samples": 400, "curve": 0.0, "gamma": 0.8, "positive": False,
    "equalize": False, "auto_face": False, "face_margin": 0.6,
}


# ---------------------------------------------------------------------------
# 共通ヘルパ
# ---------------------------------------------------------------------------
def _resolve_image(image_id: str) -> Path:
    try:
        return storage.get_path(image_id)
    except storage.StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _face_detection_available() -> bool:
    try:
        pc._load_cascades()
        return True
    except pc.FaceDetectionUnavailable:
        return False


def _resolve_crop(params, image_path: Path, aspect: float, fallback: str):
    """
    実際に使うクロップ範囲を決める。
    手動クロップが指定されていればそれを優先し、auto_face のときだけ顔検出を試す。
    検出できなくてもエラーにはせず、notices で理由を返す。

    fallback: 検出できなかったときに何が起きるかの説明。
              シャドウアートは枠の比率に合わせた中央クロップ、
              リソフェインはクロップなし(画像全体)になるため文言が異なる。
    """
    notices: list[str] = []
    if params.crop is not None:
        return params.crop.as_tuple(), notices

    if not params.auto_face:
        return None, notices

    try:
        box = pc.detect_face_crop_box(
            str(image_path), margin=params.face_margin, aspect=aspect,
        )
    except pc.FaceDetectionUnavailable as exc:
        notices.append(f"顔検出を利用できません: {exc} {fallback}")
        return None, notices

    if box is None:
        notices.append(f"顔を検出できませんでした。{fallback}")
        return None, notices
    return box, notices


def _applied_crop(crop_box):
    if crop_box is None:
        return None
    l, t, r, b = crop_box
    return CropBox(left=l, top=t, right=r, bottom=b)


# ---------------------------------------------------------------------------
# シャドウアート
# ---------------------------------------------------------------------------
def _build_shadow_art(params, image_path: Path, samples: int):
    aspect = params.effective_aspect
    crop_box, notices = _resolve_crop(params, image_path, aspect,
                                      "中央クロップを使用します。")

    try:
        art = la.build_artwork(
            str(image_path),
            shape=params.effective_shape,
            diameter=params.diameter,
            aspect=aspect,
            num_lines=params.lines,
            angle_deg=params.angle,
            min_line_width=params.min_width,
            max_line_width=params.max_width,
            frame_width=params.frame_width,
            gamma=params.gamma,
            invert=params.invert,
            equalize=params.equalize,
            crop_box=crop_box,
            samples_per_line=samples,
        )
    except (ValueError, MemoryError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return art, crop_box, notices


def _shadow_art_size(art, params) -> SizeInfo:
    depth = max(params.thickness, params.frame_thickness)
    return SizeInfo(
        outer_width_mm=round(art.outer_width, 2),
        outer_height_mm=round(art.outer_height, 2),
        outer_depth_mm=round(depth, 2),
        design_width_mm=round(art.design_width, 2),
        design_height_mm=round(art.design_height, 2),
        within_print_limit=(art.outer_width <= pc.MAX_PRINT_SIZE_MM
                            and art.outer_height <= pc.MAX_PRINT_SIZE_MM),
        pitch_mm=round(art.pitch, 3),
        line_count=art.line_count,
    )


# ---------------------------------------------------------------------------
# リソフェイン
# ---------------------------------------------------------------------------
def _build_lithophane(params, image_path: Path, samples: int):
    # リソフェインは比率が自由なので、顔検出も正方形基準で行う
    crop_box, notices = _resolve_crop(params, image_path, 1.0,
                                      "画像全体を使用します。")

    try:
        litho = lp.build_lithophane(
            str(image_path),
            width_mm=params.width,
            min_thickness=params.min_thickness,
            max_thickness=params.max_thickness,
            samples=samples,
            gamma=params.gamma,
            positive=params.positive,
            equalize=params.equalize,
            crop_box=crop_box,
            curve_deg=params.curve,
        )
    except (ValueError, MemoryError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return litho, crop_box, notices


def _lithophane_size(litho) -> SizeInfo:
    fw, fh, fd = litho.footprint()
    return SizeInfo(
        outer_width_mm=round(fw, 2),
        outer_height_mm=round(fh, 2),
        outer_depth_mm=round(fd, 2),
        design_width_mm=round(litho.width_mm, 2),
        design_height_mm=round(litho.height_mm, 2),
        within_print_limit=(max(fw, fh, fd) <= pc.MAX_PRINT_SIZE_MM),
        min_thickness_mm=round(litho.min_thickness, 3),
        max_thickness_mm=round(litho.max_thickness, 3),
        grid=f"{litho.samples_x} x {litho.samples_z}",
        face_count=litho.face_count,
        radius_mm=round(litho.radius_mm, 2) if litho.curve_deg > 0 else None,
    )


# ---------------------------------------------------------------------------
# その他ヘルパ
# ---------------------------------------------------------------------------
def _safe_filename(name: str | None, fallback: str = "shadow-art") -> str:
    """Content-Disposition に載せられる安全なASCIIファイル名を作る"""
    base = (name or "").strip()
    base = base[:-4] if base.lower().endswith(".stl") else base
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-._")
    return (base or fallback)[:80] + ".stl"


def _png_data_url(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _mesh_response(mesh, req, size: SizeInfo) -> Response:
    """
    3Dプレビュー用のメッシュを独自バイナリで返す。

    STLは1三角形あたり50バイト(頂点を共有しない)なので、同じ形状でも
    インデックス付きのこの形式なら 1/3 以下になる。glTF等を使うほどの
    情報量(マテリアル・階層)は不要なので、最小限の構造にしてある。

    レイアウト (すべてリトルエンディアン):
        magic   char[4]  "PSAM"
        version uint32   1
        n_vert  uint32   頂点数
        n_index uint32   インデックス数 (= 三角形数 * 3)
        pos     float32[n_vert * 3]   XYZ (mm)。原点中心・Z上
        index   uint32[n_index]
    """
    import struct

    verts = np.ascontiguousarray(mesh.vertices, dtype=np.float32)
    faces = np.ascontiguousarray(mesh.faces, dtype=np.uint32)

    # ブラウザ側で毎回中心を計算しなくて済むよう、原点中心に寄せておく。
    # X/Yは中心、Zは底面を0にする(印刷時の置き方に合わせる)。
    lo = verts.min(axis=0)
    hi = verts.max(axis=0)
    verts[:, 0] -= (lo[0] + hi[0]) / 2.0
    verts[:, 1] -= (lo[1] + hi[1]) / 2.0
    verts[:, 2] -= lo[2]

    header = struct.pack("<4sIII", b"PSAM", 1, len(verts), faces.size)
    body = header + verts.tobytes() + faces.tobytes()

    return Response(
        content=body,
        media_type="application/octet-stream",
        headers={
            "X-Mode": req.mode,
            "X-Vertex-Count": str(len(verts)),
            "X-Face-Count": str(len(faces)),
            "X-Outer-Size-Mm": (
                f"{size.outer_width_mm}x{size.outer_height_mm}x{size.outer_depth_mm}"
            ),
            "Cache-Control": "no-store",
        },
    )


def _stl_response(mesh, req, size: SizeInfo) -> Response:
    stl_bytes = mesh.export(file_type="stl")
    if isinstance(stl_bytes, str):
        stl_bytes = stl_bytes.encode("utf-8")

    fallback = "lithophane" if req.mode == "lithophane" else "shadow-art"
    ascii_name = _safe_filename(req.filename, fallback)
    utf8_name = req.filename or fallback
    if not utf8_name.lower().endswith(".stl"):
        utf8_name += ".stl"

    return Response(
        content=stl_bytes,
        media_type="model/stl",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_name}"; '
                f"filename*=UTF-8''{quote(utf8_name)}"
            ),
            "X-Mode": req.mode,
            "X-Outer-Size-Mm": (
                f"{size.outer_width_mm}x{size.outer_height_mm}x{size.outer_depth_mm}"
            ),
            "X-Face-Count": str(len(mesh.faces)),
        },
    )


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config", response_model=ConfigResponse)
def get_config():
    return ConfigResponse(
        max_print_size_mm=pc.MAX_PRINT_SIZE_MM,
        max_upload_bytes=storage.MAX_UPLOAD_BYTES,
        shapes=["square", "rectangle", "circle", "hexagon"],
        face_detection_available=_face_detection_available(),
        modes=[
            ModeInfo(
                id="shadow_art",
                label="シャドウアート",
                description=(
                    "線の太さで濃淡を表現します。枠の形を選べて、"
                    "光を当てなくても模様として成立します。"
                ),
                defaults=SHADOW_ART_DEFAULTS,
            ),
            ModeInfo(
                id="lithophane",
                label="リソフェイン",
                description=(
                    "厚みで濃淡を表現します。裏から光を当てると写真が浮かび上がります。"
                    "連続階調が出せるかわりに、必ず背面照明が必要です。"
                ),
                defaults=LITHOPHANE_DEFAULTS,
            ),
        ],
        defaults=SHADOW_ART_DEFAULTS,
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    try:
        stored = storage.save_upload(data)
    except storage.StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadResponse(
        image_id=stored.image_id,
        width=stored.width,
        height=stored.height,
        url=f"/api/images/{stored.image_id}",
    )


@app.get("/api/images/{image_id}")
def get_image(image_id: str):
    path = _resolve_image(image_id)
    return Response(
        content=path.read_bytes(),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@app.post("/api/detect-face", response_model=FaceDetectResponse)
def detect_face(req: FaceDetectRequest):
    path = _resolve_image(req.image_id)
    try:
        faces, (W, H) = pc.detect_faces(str(path))
    except pc.FaceDetectionUnavailable as exc:
        return FaceDetectResponse(available=False, detected=False, message=str(exc))

    if not faces:
        return FaceDetectResponse(
            available=True, detected=False,
            message="顔を検出できませんでした。手動でトリミングしてください。",
        )

    box = pc.detect_face_crop_box(str(path), margin=req.margin, aspect=req.aspect)
    if box is None:
        return FaceDetectResponse(
            available=True, detected=False,
            message="顔を検出できませんでした。手動でトリミングしてください。",
        )

    l, t, r, b = box
    return FaceDetectResponse(
        available=True,
        detected=True,
        crop=CropBox(left=l, top=t, right=r, bottom=b),
        faces=[FaceRect(x=f[0], y=f[1], width=f[2], height=f[3]) for f in faces],
        message=f"{len(faces)}件の顔を検出しました。",
    )


def _hex_to_rgb(value: str) -> tuple:
    v = value.lstrip("#")
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


def _luma(rgb) -> float:
    """相対輝度 (0..1)。色の明暗の判定にだけ使う。"""
    r, g, b = (c / 255.0 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _preview_backdrop(fg) -> tuple:
    return (PREVIEW_BACKDROP_DARK if _luma(fg) > BACKDROP_SWITCH_LUMA
            else PREVIEW_BACKDROP_LIGHT)


def _litho_tint(fg) -> tuple:
    """
    リソフェインの透過光の色。

    フィラメントの色相だけを取り出し(最大チャンネルを255まで伸ばす)、
    照明色を掛ける。明るさは厚みのシミュレーション側が決めているので、
    暗い色をそのまま掛けると画像全体が黒く潰れて何も見えなくなる。
    暗いフィラメントについては別途 notice で注意する。
    """
    peak = max(fg)
    # 純黒は色相を持たないので白として扱う
    hue = (255, 255, 255) if peak == 0 else tuple(round(c * 255 / peak) for c in fg)
    return tuple(round(h * light / 255) for h, light in zip(hue, LITHO_LIGHT))


@app.post("/api/preview", response_model=PreviewResponse)
def preview(req: AnyPreviewRequest = Body(..., discriminator="mode")):
    started = time.perf_counter()
    path = _resolve_image(req.image_id)
    filament = _hex_to_rgb(req.filament_color)

    if isinstance(req, ShadowArtPreviewRequest):
        art, crop_box, notices = _build_shadow_art(
            req, path, SHADOW_SAMPLES["preview"])
        image = la.render_preview_image(
            art, size=req.preview_size,
            bg=_preview_backdrop(filament), fg=filament)
        warnings = art.warnings
        size = _shadow_art_size(art, req)
    else:
        # プレビューは分割数を抑えて高速に(見た目の階調は分割数に依存しない)
        samples = min(req.samples, req.preview_size)
        litho, crop_box, notices = _build_lithophane(req, path, samples)
        image = lp.render_preview_image(
            litho, size=req.preview_size, tint=_litho_tint(filament))
        if _luma(filament) < LITHO_DARK_LUMA:
            notices.append(
                "暗い色のフィラメントは光をほとんど通しません。"
                "プレビューは色味だけを反映しているので、実物はこれよりずっと"
                "暗くなります。リソフェインは白や淡い色での出力をおすすめします。"
            )
        # 警告は実際の分割数(=ユーザー指定)で出したいので作り直す
        warnings = [w for w in litho.warnings if "分割数" not in w]
        warnings += _litho_face_count_warning(req, litho)
        size = _lithophane_size(litho)
        size.grid = _projected_grid(req, litho)
        size.face_count = _projected_face_count(req, litho)

    return PreviewResponse(
        mode=req.mode,
        image=_png_data_url(image),
        warnings=warnings,
        notices=notices,
        size=size,
        applied_crop=_applied_crop(crop_box),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


def _projected_grid(req: LithophanePreviewRequest, litho) -> str:
    """プレビューは粗く作るので、STL出力時の格子サイズを計算して見せる"""
    nx, nz = litho.grid_for_samples(req.samples)
    return f"{nx} x {nz}"


def _projected_face_count(req: LithophanePreviewRequest, litho) -> int:
    return lp.face_count_for(*litho.grid_for_samples(req.samples))


def _litho_face_count_warning(req, litho):
    faces = _projected_face_count(req, litho)
    if faces <= lp.FACE_COUNT_WARN:
        return []
    return [
        f"警告: 分割数が多く、三角形が約{faces/1e6:.1f}M個になります。"
        f"STLが数百MBになりスライサーが重くなる恐れがあります。"
        f"分割数を下げることを検討してください。"
    ]


@app.post("/api/mesh")
def make_mesh(req: AnyMeshRequest = Body(..., discriminator="mode")):
    """
    3Dプレビュー用の軽量メッシュを返す。
    形状はSTLと同じ作り方だが、解像度を落として転送量と生成時間を抑える。
    """
    path = _resolve_image(req.image_id)

    if isinstance(req, LithophaneMeshRequest):
        # ユーザー指定の分割数より細かくしても意味がないので上限として使う
        samples = min(req.samples, MESH_LITHO_SAMPLES[req.mesh_detail])
        litho, _crop, _notices = _build_lithophane(req, path, samples)
        try:
            mesh = lp.build_mesh(litho)
        except (RuntimeError, MemoryError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _mesh_response(mesh, req, _lithophane_size(litho))

    art, _crop, _notices = _build_shadow_art(
        req, path, MESH_SHADOW_SAMPLES[req.mesh_detail])
    try:
        mesh = la.build_mesh(
            art, thickness=req.thickness, frame_thickness=req.frame_thickness
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _mesh_response(mesh, req, _shadow_art_size(art, req))


@app.post("/api/stl")
def make_stl(req: AnyStlRequest = Body(..., discriminator="mode")):
    path = _resolve_image(req.image_id)

    if isinstance(req, LithophaneStlRequest):
        scale = LITHO_QUALITY_SCALE[req.quality]
        samples = int(max(8, min(1200, round(req.samples * scale))))
        litho, _crop, _notices = _build_lithophane(req, path, samples)
        try:
            mesh = lp.build_mesh(litho)
        except (RuntimeError, MemoryError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _stl_response(mesh, req, _lithophane_size(litho))

    art, _crop, _notices = _build_shadow_art(
        req, path, SHADOW_SAMPLES[req.quality])
    try:
        mesh = la.build_mesh(
            art, thickness=req.thickness, frame_thickness=req.frame_thickness
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _stl_response(mesh, req, _shadow_art_size(art, req))
