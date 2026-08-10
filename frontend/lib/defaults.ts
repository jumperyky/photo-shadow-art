import type {
  CropBox,
  KeychainParams,
  CropOutline,
  LithophaneParams,
  Mode,
  ShadowArtParams,
  ShapeName,
  ShapeParams,
} from "./types";

export const DEFAULT_SHADOW_ART: ShadowArtParams = {
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

export const DEFAULT_LITHOPHANE: LithophaneParams = {
  width: 100,
  min_thickness: 0.6,
  max_thickness: 3.0,
  samples: 400,
  curve: 0,
  // リソフェインは暗部の階調を出すため1未満が定番
  gamma: 0.8,
  positive: false,
  equalize: false,
  auto_face: false,
  face_margin: 0.6,
};

/** backend/app/main.py の KEYCHAIN_DEFAULTS と一致させること */
export const DEFAULT_KEYCHAIN: KeychainParams = {
  shape: "circle",
  sides: null,
  aspect: 1.0,
  diameter: 50,
  frame_width: 3.0,
  min_thickness: 0.6,
  max_thickness: 2.4,
  well_depth: 0.6,
  hole_diameter: 3.5,
  ring_margin: 2.5,
  samples: 320,
  nozzle: 0.4,
  gamma: 0.8,
  positive: false,
  equalize: false,
  auto_face: false,
  face_margin: 0.6,
};

/** プリンタの最大造形サイズ(mm)。ここまでは警告なしで指定できる。 */
export const MAX_PRINT_SIZE_MM = 1800;

/**
 * プレビューに使うフィラメントの色。
 *
 * 見た目だけの設定で、ジオメトリにもSTLにも影響しない。2Dプレビュー
 * (サーバーが描画)と3Dビューア(three.jsのマテリアル)の両方に同じ値が
 * 渡るので、どちらのタブでも同じ色に見える。
 *
 * 既定値はバックエンドの schemas.DEFAULT_FILAMENT_COLOR と揃えること。
 */
export const DEFAULT_FILAMENT = "#141414";

export const FILAMENT_COLORS: { value: string; label: string }[] = [
  { value: "#141414", label: "ブラック" },
  { value: "#f2f0ea", label: "ホワイト" },
  { value: "#9aa1ab", label: "グレー" },
  { value: "#d3bd93", label: "ベージュ" },
  { value: "#c0392b", label: "レッド" },
  { value: "#e1732b", label: "オレンジ" },
  { value: "#e8b93b", label: "イエロー" },
  { value: "#2e8b57", label: "グリーン" },
  { value: "#2c6fb5", label: "ブルー" },
  { value: "#8e5bb5", label: "パープル" },
];

/**
 * 明るいフィラメントかどうか。背景を明暗どちらにするかの判定に使う。
 *
 * 閾値と式はバックエンドの `_luma()` / `BACKDROP_SWITCH_LUMA` と同じ。
 * ずらすと2Dと3Dで背景が食い違い、片方だけ作品が背景に溶ける。
 */
export function isLightFilament(hex: string): boolean {
  const v = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.45;
}

export const MODE_LABELS: Record<Mode, string> = {
  shadow_art: "シャドウアート",
  lithophane: "リソフェイン",
  keychain: "キーホルダー",
};

export const SHAPE_LABELS: Record<ShapeName, string> = {
  square: "正方形",
  rectangle: "長方形",
  circle: "円",
  hexagon: "六角形",
};

/**
 * トリミングUIに渡すアスペクト比 (幅/高さ)。
 * undefined を返すと自由な比率で切り抜ける。
 *
 * シャドウアートは枠の形が決まっているので比率を固定する
 * (バックエンドの aspect は「高さ/幅」なので逆数になる)。
 * リソフェインは板の比率がクロップからそのまま決まるので自由。
 */
export function cropAspect(
  mode: Mode,
  params: ShapeParams,
): number | undefined {
  // 外形を持たないのはリソフェインだけ(板の比率がクロップでそのまま決まる)
  if (mode === "lithophane") return undefined;
  if (params.sides !== null) return 1;
  if (params.shape === "rectangle") return 1 / params.aspect;
  return 1;
}

/**
 * トリミング枠の中に重ねて表示する輪郭を返す。
 *
 * 円や六角形を選んでいるとき、枠は正方形のままなので「四隅は捨てられる」
 * ことが見た目から分からない。実際に出力される形を枠の中に描いておくと、
 * 顔が角で切れるといった事故を防げる。
 *
 * 形は line_art_stl.make_shape_polygon() と同じ式で出している。片方だけ
 * 変えると表示と出力がずれるので、追加するときは両方に入れること。
 * バックエンドは画像を [-R, R]^2 に貼ってから形状で切り抜くので、
 * 枠 = その正方形、輪郭 = そこに内接する形、という対応になる。
 */
export function cropOutline(
  mode: Mode,
  params: ShapeParams,
): CropOutline {
  if (mode === "lithophane") return null;

  // sides 指定時は n角形が shape より優先される(backend の effective_shape と同じ)
  const sides =
    params.sides !== null
      ? params.sides
      : params.shape === "circle"
        ? 240
        : params.shape === "hexagon"
          ? 6
          : null;
  if (sides === null) return null; // square / rectangle は枠と一致する

  // 六角形だけ 30 度回して平らな辺を左右に持ってくる
  const offset =
    params.sides === null && params.shape === "hexagon"
      ? Math.PI / 6
      : Math.PI / 2;

  const points: [number, number][] = [];
  for (let i = 0; i < sides; i++) {
    const t = (2 * Math.PI * i) / sides + offset;
    // SVG は y が下向きなので符号を反転する
    points.push([0.5 + 0.5 * Math.cos(t), 0.5 - 0.5 * Math.sin(t)]);
  }
  return { points };
}

/** 画像全体を、指定アスペクト比に収まる最大の中央矩形にする */
export function centeredCrop(
  imgWidth: number,
  imgHeight: number,
  aspect: number | undefined,
): CropBox {
  if (aspect === undefined) {
    return { left: 0, top: 0, right: 1, bottom: 1 };
  }
  const imgAspect = imgWidth / imgHeight;
  let w = 1;
  let h = 1;
  if (imgAspect > aspect) {
    w = aspect / imgAspect;
  } else {
    h = imgAspect / aspect;
  }
  return {
    left: (1 - w) / 2,
    top: (1 - h) / 2,
    right: (1 + w) / 2,
    bottom: (1 + h) / 2,
  };
}
