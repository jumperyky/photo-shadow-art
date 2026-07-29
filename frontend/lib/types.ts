export type ShapeName = "square" | "rectangle" | "circle" | "hexagon";

export interface CropBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** line_art_stl.py のパラメータと1対1で対応する */
export interface ArtParams {
  shape: ShapeName;
  sides: number | null;
  aspect: number;
  diameter: number;
  lines: number;
  angle: number;
  min_width: number;
  max_width: number;
  thickness: number;
  frame_width: number;
  frame_thickness: number;
  gamma: number;
  invert: boolean;
  equalize: boolean;
  auto_face: boolean;
  face_margin: number;
}

export interface SizeInfo {
  outer_width_mm: number;
  outer_height_mm: number;
  design_width_mm: number;
  design_height_mm: number;
  pitch_mm: number;
  line_count: number;
  within_print_limit: boolean;
}

export interface PreviewResponse {
  image: string;
  warnings: string[];
  notices: string[];
  size: SizeInfo;
  applied_crop: CropBox | null;
  elapsed_ms: number;
}

export interface UploadResponse {
  image_id: string;
  width: number;
  height: number;
  url: string;
}

export interface FaceRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface FaceDetectResponse {
  available: boolean;
  detected: boolean;
  crop: CropBox | null;
  faces: FaceRect[];
  message: string;
}

export interface AppConfig {
  max_print_size_mm: number;
  max_upload_bytes: number;
  shapes: string[];
  face_detection_available: boolean;
  defaults: Record<string, unknown>;
}

export type Quality = "draft" | "normal" | "fine";
