"""APIのリクエスト/レスポンススキーマ。

サイズ関連の上限は line_art_stl.MAX_PRINT_SIZE_MM (1800mm) に合わせてある。
1800mm以内であれば警告もエラーも出さずに通す。
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from line_art_stl import MAX_PRINT_SIZE_MM

ShapeName = Literal["square", "rectangle", "circle", "hexagon"]


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


class ArtParams(BaseModel):
    """プレビューとSTL生成で共通のパラメータ"""

    image_id: str
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

    gamma: float = Field(default=1.0, gt=0.0, le=5.0)
    invert: bool = False
    equalize: bool = False

    crop: Optional[CropBox] = None
    auto_face: bool = False
    face_margin: float = Field(default=0.6, ge=0.0, le=3.0)

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
        """--sides 指定時は n角形(int)が優先される"""
        return self.sides if self.sides is not None else self.shape


class PreviewRequest(ArtParams):
    preview_size: int = Field(default=760, ge=200, le=1600)


class StlRequest(ArtParams):
    filename: Optional[str] = Field(default=None, max_length=120)
    quality: Literal["draft", "normal", "fine"] = "normal"


class SizeInfo(BaseModel):
    outer_width_mm: float
    outer_height_mm: float
    design_width_mm: float
    design_height_mm: float
    pitch_mm: float
    line_count: int
    within_print_limit: bool


class PreviewResponse(BaseModel):
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


class ConfigResponse(BaseModel):
    max_print_size_mm: float
    max_upload_bytes: int
    shapes: List[str]
    face_detection_available: bool
    defaults: dict
