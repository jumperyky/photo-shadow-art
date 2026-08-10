"""APIのリクエスト/レスポンススキーマ。

生成方式は2つあり、`mode` で切り替える。
  - "shadow_art"  … 線幅で濃淡を表現する(line_art_stl.py)
  - "lithophane"  … 厚みで濃淡を表現する(lithophane_stl.py)

サイズ関連の上限は photo_common.MAX_PRINT_SIZE_MM (1800mm) に合わせてある。
1800mm以内であれば警告もエラーも出さずに通す。
"""

from __future__ import annotations

import re
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from photo_common import MAX_PRINT_SIZE_MM

Mode = Literal["shadow_art", "lithophane", "keychain"]
ShapeName = Literal["square", "rectangle", "circle", "hexagon"]

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

# プレビューの既定のフィラメント色。line_art_stl.render_preview_image() の
# fg 既定値と同じ濃いグレー。フロント側の DEFAULT_FILAMENT と揃えること。
DEFAULT_FILAMENT_COLOR = "#141414"


class CropBox(BaseModel):
    """0..1 の相対クロップ範囲"""
    left: float = Field(ge=0.0, le=1.0)
    top: float = Field(ge=0.0, le=1.0)
    right: float = Field(ge=0.0, le=1.0)
    bottom: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_order(self):
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError("クロップ範囲が空です(right>left, bottom>top が必要)。")
        return self

    def as_tuple(self):
        return (self.left, self.top, self.right, self.bottom)


class CommonParams(BaseModel):
    """両方式で共通のパラメータ"""

    image_id: str
    crop: Optional[CropBox] = None
    auto_face: bool = False
    face_margin: float = Field(default=0.6, ge=0.0, le=3.0)
    gamma: float = Field(default=1.0, gt=0.0, le=5.0)
    equalize: bool = False


# ---------------------------------------------------------------------------
# シャドウアート(線幅で表現)
# ---------------------------------------------------------------------------
class ShadowArtParams(CommonParams):
    mode: Literal["shadow_art"] = "shadow_art"

    shape: ShapeName = "square"
    sides: Optional[int] = Field(default=None, ge=3, le=64)
    aspect: float = Field(default=1.0, gt=0.05, le=20.0)

    # 3Dプリンタの最大造形サイズ(1800mm)まで自由に指定できる
    diameter: float = Field(default=150.0, gt=0.0, le=MAX_PRINT_SIZE_MM)
    lines: int = Field(default=48, ge=2, le=2000)
    angle: float = Field(default=20.0, ge=-180.0, le=180.0)
    min_width: float = Field(default=0.5, gt=0.0, le=200.0)
    max_width: float = Field(default=2.9, gt=0.0, le=400.0)
    thickness: float = Field(default=2.0, gt=0.0, le=200.0)
    frame_width: float = Field(default=8.0, ge=0.0, le=400.0)
    frame_thickness: float = Field(default=2.0, gt=0.0, le=200.0)
    invert: bool = False

    @field_validator("shape", mode="before")
    @classmethod
    def _normalize_shape(cls, v):
        return v.lower() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _check_widths(self):
        if self.max_width < self.min_width:
            raise ValueError("最大線幅は最小線幅以上にしてください。")
        return self

    @property
    def effective_aspect(self) -> float:
        """円/多角形は常に等方なので aspect は 1 として扱う"""
        if self.sides is not None:
            return 1.0
        return self.aspect if self.shape in ("square", "rectangle") else 1.0

    @property
    def effective_shape(self):
        """sides 指定時は n角形(int)が優先される"""
        return self.sides if self.sides is not None else self.shape


# ---------------------------------------------------------------------------
# リソフェイン(厚みで表現)
# ---------------------------------------------------------------------------
class LithophaneParams(CommonParams):
    mode: Literal["lithophane"] = "lithophane"

    # 湾曲させる場合、width は弧の長さ
    width: float = Field(default=100.0, gt=0.0, le=MAX_PRINT_SIZE_MM)
    min_thickness: float = Field(default=0.6, gt=0.0, le=100.0)
    max_thickness: float = Field(default=3.0, gt=0.0, le=200.0)
    samples: int = Field(default=400, ge=8, le=1200)
    curve: float = Field(default=0.0, ge=0.0, le=350.0)
    positive: bool = False

    # リソフェインは暗部の階調を出すため 1未満が定番
    gamma: float = Field(default=0.8, gt=0.0, le=5.0)

    @model_validator(mode="after")
    def _check_thickness(self):
        if self.max_thickness < self.min_thickness:
            raise ValueError("最大厚みは最小厚み以上にしてください。")
        return self


# ---------------------------------------------------------------------------
# キーホルダー(形状クリップしたリソフェイン + 枠 + リング穴)
# ---------------------------------------------------------------------------
class KeychainParams(CommonParams):
    """
    ShadowArtParams を継承しないこと。main.py は isinstance で分岐しており、
    サブクラスにすると黙ってシャドウアート側に流れてしまう。
    """
    mode: Literal["keychain"] = "keychain"

    shape: ShapeName = "circle"
    sides: Optional[int] = Field(default=None, ge=3, le=64)
    aspect: float = Field(default=1.0, gt=0.05, le=20.0)

    diameter: float = Field(default=50.0, gt=0.0, le=MAX_PRINT_SIZE_MM)
    frame_width: float = Field(default=3.0, ge=0.0, le=200.0)
    min_thickness: float = Field(default=0.6, gt=0.0, le=100.0)
    max_thickness: float = Field(default=2.4, gt=0.0, le=200.0)
    # 枠厚は max_thickness + well_depth で決まる。枠厚を直接指定させないことで、
    # 「枠が凹凸より低くレジンが溜まらない」設定をUIから作れなくしている。
    well_depth: float = Field(default=0.6, gt=0.0, le=50.0)
    hole_diameter: float = Field(default=3.5, gt=0.0, le=50.0)
    ring_margin: float = Field(default=2.5, gt=0.0, le=50.0)
    samples: int = Field(default=320, ge=8, le=800)
    # ノズル径。ジオメトリには影響せず、印刷できる横解像度の判定にだけ使う。
    # 立てて印刷するので横方向はここで頭打ちになる。
    nozzle: float = Field(default=0.4, gt=0.0, le=2.0)

    # リソフェインと同じく暗部の階調を出すため1未満が定番
    gamma: float = Field(default=0.8, gt=0.0, le=5.0)
    positive: bool = False

    @field_validator("shape", mode="before")
    @classmethod
    def _normalize_shape(cls, v):
        return v.lower() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _check_thickness(self):
        if self.max_thickness < self.min_thickness:
            raise ValueError("最大厚みは最小厚み以上にしてください。")
        return self

    @property
    def effective_aspect(self) -> float:
        """円/多角形は常に等方なので aspect は 1 として扱う"""
        if self.sides is not None:
            return 1.0
        return self.aspect if self.shape in ("square", "rectangle") else 1.0

    @property
    def effective_shape(self):
        return self.sides if self.sides is not None else self.shape


# ---------------------------------------------------------------------------
# リクエスト
# ---------------------------------------------------------------------------
class PreviewOptions(BaseModel):
    preview_size: int = Field(default=760, ge=200, le=1600)

    # 見た目だけに効く。ジオメトリにもSTLにも影響しないので、
    # ジオメトリ用のパラメータ(ShadowArtParams/LithophaneParams)とは分けてある。
    filament_color: str = DEFAULT_FILAMENT_COLOR

    @field_validator("filament_color")
    @classmethod
    def _check_hex(cls, v):
        if not _HEX_COLOR.match(v):
            raise ValueError("フィラメント色は #rrggbb 形式で指定してください。")
        return v.lower()


class ShadowArtPreviewRequest(ShadowArtParams, PreviewOptions):
    pass


class LithophanePreviewRequest(LithophaneParams, PreviewOptions):
    pass


class KeychainPreviewRequest(KeychainParams, PreviewOptions):
    pass


class MeshOptions(BaseModel):
    """3Dプレビュー用。STLより粗いメッシュをブラウザに渡す。"""
    # 転送量と生成時間を抑えるための解像度。UIからは変えない想定だが、
    # 端末性能に応じて調整できるよう残してある。
    mesh_detail: Literal["low", "medium"] = "medium"


class ShadowArtMeshRequest(ShadowArtParams, MeshOptions):
    pass


class LithophaneMeshRequest(LithophaneParams, MeshOptions):
    pass


class KeychainMeshRequest(KeychainParams, MeshOptions):
    pass


AnyMeshRequest = Union[ShadowArtMeshRequest, LithophaneMeshRequest,
                       KeychainMeshRequest]


class ExportOptions(BaseModel):
    filename: Optional[str] = Field(default=None, max_length=120)
    quality: Literal["draft", "normal", "fine"] = "normal"


class ShadowArtStlRequest(ShadowArtParams, ExportOptions):
    pass


class LithophaneStlRequest(LithophaneParams, ExportOptions):
    pass


class KeychainStlRequest(KeychainParams, ExportOptions):
    pass


AnyPreviewRequest = Union[ShadowArtPreviewRequest, LithophanePreviewRequest,
                          KeychainPreviewRequest]
AnyStlRequest = Union[ShadowArtStlRequest, LithophaneStlRequest,
                      KeychainStlRequest]


# ---------------------------------------------------------------------------
# レスポンス
# ---------------------------------------------------------------------------
class SizeInfo(BaseModel):
    """造形サイズの要約。方式によって埋まる項目が異なる。"""
    outer_width_mm: float
    outer_height_mm: float
    outer_depth_mm: float
    design_width_mm: float
    design_height_mm: float
    within_print_limit: bool

    # シャドウアート専用
    pitch_mm: Optional[float] = None
    line_count: Optional[int] = None

    # リソフェイン専用
    min_thickness_mm: Optional[float] = None
    max_thickness_mm: Optional[float] = None
    grid: Optional[str] = None          # "400 x 533"
    face_count: Optional[int] = None
    radius_mm: Optional[float] = None   # 湾曲時の内側半径

    # キーホルダー専用
    frame_thickness_mm: Optional[float] = None   # 枠の高さ(=最大厚み+レジンだまり)
    well_depth_mm: Optional[float] = None        # レジンだまりの深さ
    hole_diameter_mm: Optional[float] = None
    resin_volume_ml: Optional[float] = None      # 必要なレジンの量の目安
    printable_px: Optional[int] = None           # 実際に印刷できる横解像度(ノズル径で決まる)
    grid_px: Optional[int] = None                # メッシュの格子の列数(印刷の細かさではない)


class PreviewResponse(BaseModel):
    mode: Mode
    image: str                       # data URL (PNG)
    warnings: List[str] = []
    notices: List[str] = []          # 顔検出のフォールバック等の情報メッセージ
    size: SizeInfo
    applied_crop: Optional[CropBox] = None
    elapsed_ms: int


class UploadResponse(BaseModel):
    image_id: str
    width: int
    height: int
    url: str


class FaceDetectRequest(BaseModel):
    image_id: str
    aspect: float = Field(default=1.0, gt=0.05, le=20.0)
    margin: float = Field(default=0.6, ge=0.0, le=3.0)


class FaceRect(BaseModel):
    x: int
    y: int
    width: int
    height: int


class FaceDetectResponse(BaseModel):
    available: bool
    detected: bool
    crop: Optional[CropBox] = None
    faces: List[FaceRect] = []
    message: str = ""


class ModeInfo(BaseModel):
    id: Mode
    label: str
    description: str
    defaults: dict


class ConfigResponse(BaseModel):
    max_print_size_mm: float
    max_upload_bytes: int
    shapes: List[str]
    face_detection_available: bool
    modes: List[ModeInfo]
    # 後方互換: シャドウアートの既定値
    defaults: dict
