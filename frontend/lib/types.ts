/** 生成方式。最初にこれを選び、以降のパラメータとプレビューが切り替わる。 */
export type Mode = "shadow_art" | "lithophane" | "keychain";

export type ShapeName = "square" | "rectangle" | "circle" | "hexagon";

/** プレビューの表示方法。2D画像か、three.jsによる3D表示か。 */
export type ViewMode = "2d" | "3d";

export interface CropBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/**
 * トリミング枠の中に重ねて描く、実際に出力される輪郭。
 * 座標は枠を 0..1 に正規化したもの(x は右、y は下が正)。
 * null は「枠そのものが出力範囲」= 正方形/長方形のとき。
 */
export type CropOutline = { points: [number, number][] } | null;

/** 両方式で共通のパラメータ */
export interface CommonParams {
  gamma: number;
  equalize: boolean;
  auto_face: boolean;
  face_margin: number;
}

/**
 * 外形を持つモード(シャドウアート・キーホルダー)で共通の形状パラメータ。
 * cropAspect() / cropOutline() はこれだけを見るので、両モードで使い回せる。
 */
export interface ShapeParams {
  shape: ShapeName;
  sides: number | null;
  aspect: number;
}

/** line_art_stl.py のパラメータと1対1で対応する */
export interface ShadowArtParams extends CommonParams, ShapeParams {
  diameter: number;
  lines: number;
  angle: number;
  min_width: number;
  max_width: number;
  thickness: number;
  frame_width: number;
  frame_thickness: number;
  invert: boolean;
}

/** lithophane_stl.py のパラメータと1対1で対応する */
export interface LithophaneParams extends CommonParams {
  width: number;
  min_thickness: number;
  max_thickness: number;
  samples: number;
  curve: number;
  positive: boolean;
}

/** keychain_stl.py のパラメータと1対1で対応する */
export interface KeychainParams extends CommonParams, ShapeParams {
  diameter: number;
  frame_width: number;
  min_thickness: number;
  max_thickness: number;
  /** 枠の高さ = max_thickness + well_depth。枠厚を直接は指定させない。 */
  well_depth: number;
  hole_diameter: number;
  ring_margin: number;
  samples: number;
  /** ノズル径。ジオメトリには影響せず、印刷できる解像度の判定にだけ使う。 */
  nozzle: number;
  positive: boolean;
}

export interface SizeInfo {
  outer_width_mm: number;
  outer_height_mm: number;
  outer_depth_mm: number;
  design_width_mm: number;
  design_height_mm: number;
  within_print_limit: boolean;
  // シャドウアート専用
  pitch_mm: number | null;
  line_count: number | null;
  // リソフェイン専用
  min_thickness_mm: number | null;
  max_thickness_mm: number | null;
  grid: string | null;
  face_count: number | null;
  radius_mm: number | null;
  // キーホルダー専用
  frame_thickness_mm: number | null;
  well_depth_mm: number | null;
  hole_diameter_mm: number | null;
  resin_volume_ml: number | null;
  printable_px: number | null;
  grid_px: number | null;
}

export interface PreviewResponse {
  mode: Mode;
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

export interface ModeInfo {
  id: Mode;
  label: string;
  description: string;
  defaults: Record<string, unknown>;
}

export interface AppConfig {
  max_print_size_mm: number;
  max_upload_bytes: number;
  shapes: string[];
  face_detection_available: boolean;
  modes: ModeInfo[];
  defaults: Record<string, unknown>;
}

export type Quality = "draft" | "normal" | "fine";
