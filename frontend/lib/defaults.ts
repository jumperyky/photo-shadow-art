import type { ArtParams, CropBox, ShapeName } from "./types";

export const DEFAULT_PARAMS: ArtParams = {
  shape: "square",
  sides: null,
  aspect: 1.0,
  diameter: 150,
  lines: 48,
  angle: 20,
  min_width: 0.5,
  max_width: 2.9,
  thickness: 2.0,
  frame_width: 8.0,
  frame_thickness: 2.0,
  gamma: 1.0,
  invert: false,
  equalize: false,
  auto_face: false,
  face_margin: 0.6,
};

/** プリンタの最大造形サイズ(mm)。ここまでは警告なしで指定できる。 */
export const MAX_PRINT_SIZE_MM = 1800;

export const SHAPE_LABELS: Record<ShapeName, string> = {
  square: "正方形",
  rectangle: "長方形",
  circle: "円",
  hexagon: "六角形",
};

/**
 * トリミングUIに渡すアスペクト比 (幅/高さ)。
 * バックエンドの aspect は「高さ/幅」なので逆数になる点に注意。
 * 円・六角形・n角形は等方なので常に 1。
 */
export function cropAspect(params: ArtParams): number {
  if (params.sides !== null) return 1;
  if (params.shape === "rectangle") return 1 / params.aspect;
  return 1;
}

/** 画像全体を、指定アスペクト比に収まる最大の中央矩形にする */
export function centeredCrop(
  imgWidth: number,
  imgHeight: number,
  aspect: number,
): CropBox {
  const imgAspect = imgWidth / imgHeight;
  let w = 1;
  let h = 1;
  if (imgAspect > aspect) {
    w = (aspect / imgAspect);
  } else {
    h = (imgAspect / aspect);
  }
  return {
    left: (1 - w) / 2,
    top: (1 - h) / 2,
    right: (1 + w) / 2,
    bottom: (1 + h) / 2,
  };
}

/** 造形サイズが上限を超えていないか(超えていても生成はできる。表示用の判定) */
export function isWithinPrintLimit(w: number, h: number): boolean {
  return w <= MAX_PRINT_SIZE_MM && h <= MAX_PRINT_SIZE_MM;
}
