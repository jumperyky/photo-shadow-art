import type {
  AppConfig,
  CropBox,
  FaceDetectResponse,
  LithophaneParams,
  Mode,
  PreviewResponse,
  Quality,
  ShadowArtParams,
  UploadResponse,
} from "./types";

// next.config.mjs の rewrites で Python API にプロキシしているので、既定は同一オリジン。
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  let detail = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body?.detail)) {
      // FastAPIのバリデーションエラーを読める形にまとめる
      detail = body.detail
        .map((d: { loc?: unknown[]; msg?: string }) => {
          const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : "";
          return field ? `${field}: ${d.msg}` : d.msg;
        })
        .join(" / ");
    }
  } catch {
    /* JSONでない場合はステータス文字列のまま */
  }
  return new ApiError(detail, res.status);
}

async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
}

export async function fetchConfig(): Promise<AppConfig> {
  const res = await fetch(`${BASE}/api/config`);
  if (!res.ok) throw await toApiError(res);
  return res.json();
}

export async function uploadImage(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/api/upload`, { method: "POST", body: form });
  if (!res.ok) throw await toApiError(res);
  return res.json();
}

export function imageUrl(imageId: string): string {
  return `${BASE}/api/images/${imageId}`;
}

export function detectFace(
  imageId: string,
  aspect: number,
  margin: number,
  signal?: AbortSignal,
): Promise<FaceDetectResponse> {
  return postJson("/api/detect-face", { image_id: imageId, aspect, margin }, signal);
}

/**
 * サーバーに渡すリクエストボディを組み立てる。
 * バックエンドは `mode` でスキーマを判別するので、方式ごとに必要な項目だけ送る。
 */
function requestBody(
  mode: Mode,
  imageId: string,
  shadow: ShadowArtParams,
  litho: LithophaneParams,
  crop: CropBox | null,
) {
  if (mode === "lithophane") {
    return {
      mode,
      image_id: imageId,
      crop,
      auto_face: litho.auto_face,
      face_margin: litho.face_margin,
      gamma: litho.gamma,
      equalize: litho.equalize,
      width: litho.width,
      min_thickness: litho.min_thickness,
      max_thickness: litho.max_thickness,
      samples: litho.samples,
      curve: litho.curve,
      positive: litho.positive,
    };
  }

  const isBox = shadow.shape === "square" || shadow.shape === "rectangle";
  return {
    mode,
    image_id: imageId,
    crop,
    auto_face: shadow.auto_face,
    face_margin: shadow.face_margin,
    gamma: shadow.gamma,
    equalize: shadow.equalize,
    shape: shadow.shape,
    sides: shadow.sides,
    // 円/六角形/n角形は常に等方なので aspect は 1 に固定して送る
    aspect: isBox && shadow.sides === null ? shadow.aspect : 1.0,
    diameter: shadow.diameter,
    lines: shadow.lines,
    angle: shadow.angle,
    min_width: shadow.min_width,
    max_width: shadow.max_width,
    thickness: shadow.thickness,
    frame_width: shadow.frame_width,
    frame_thickness: shadow.frame_thickness,
    invert: shadow.invert,
  };
}

export function fetchPreview(
  mode: Mode,
  imageId: string,
  shadow: ShadowArtParams,
  litho: LithophaneParams,
  crop: CropBox | null,
  previewSize: number,
  signal?: AbortSignal,
): Promise<PreviewResponse> {
  return postJson(
    "/api/preview",
    {
      ...requestBody(mode, imageId, shadow, litho, crop),
      preview_size: previewSize,
    },
    signal,
  );
}

export interface StlResult {
  blob: Blob;
  filename: string;
}

export async function fetchStl(
  mode: Mode,
  imageId: string,
  shadow: ShadowArtParams,
  litho: LithophaneParams,
  crop: CropBox | null,
  filename: string,
  quality: Quality,
): Promise<StlResult> {
  const res = await fetch(`${BASE}/api/stl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...requestBody(mode, imageId, shadow, litho, crop),
      filename,
      quality,
    }),
  });
  if (!res.ok) throw await toApiError(res);

  const blob = await res.blob();
  return { blob, filename: filenameFromDisposition(res, filename) };
}

function filenameFromDisposition(res: Response, fallback: string): string {
  const cd = res.headers.get("Content-Disposition") ?? "";
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  if (utf8) {
    try {
      return decodeURIComponent(utf8[1]);
    } catch {
      /* デコードできなければ下のASCII名にフォールバック */
    }
  }
  const ascii = /filename="([^"]+)"/i.exec(cd);
  if (ascii) return ascii[1];
  return fallback.toLowerCase().endsWith(".stl") ? fallback : `${fallback}.stl`;
}

interface WritableHandle {
  createWritable: () => Promise<{
    write: (d: Blob) => Promise<void>;
    close: () => Promise<void>;
  }>;
}

type SavePicker = (opts: unknown) => Promise<WritableHandle>;

function getPicker(): SavePicker | null {
  if (typeof window === "undefined") return null;
  const p = (window as unknown as { showSaveFilePicker?: SavePicker })
    .showSaveFilePicker;
  return typeof p === "function" ? p : null;
}

export function supportsSavePicker(): boolean {
  return getPicker() !== null;
}

export type SaveTarget =
  | { status: "picked"; handle: WritableHandle }
  | { status: "cancelled" }
  | { status: "unsupported" };

/**
 * STLの保存先をユーザーに選ばせる (File System Access API)。
 *
 * 重要: このAPIはユーザー操作の直後(transient user activation が有効なうち)にしか
 * 呼べない。STLの生成には数秒かかることがあるため、生成を待ってから呼ぶと
 * SecurityError で失敗する。必ずクリック直後にこれを呼び、生成後に
 * writeToTarget() で書き込むこと。
 */
export async function pickSaveLocation(filename: string): Promise<SaveTarget> {
  const picker = getPicker();
  if (!picker) return { status: "unsupported" };
  try {
    const handle = await picker.call(window, {
      suggestedName: filename,
      types: [{ description: "STL 3Dモデル", accept: { "model/stl": [".stl"] } }],
    });
    return { status: "picked", handle };
  } catch (err) {
    if ((err as DOMException)?.name === "AbortError") return { status: "cancelled" };
    // 権限エラー等は通常のダウンロードにフォールバックする
    return { status: "unsupported" };
  }
}

/** 選んだ保存先に書き込む。失敗したら通常のダウンロードにフォールバックする。 */
export async function writeToTarget(
  target: SaveTarget,
  blob: Blob,
  filename: string,
): Promise<void> {
  if (target.status === "picked") {
    try {
      const writable = await target.handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return;
    } catch {
      /* 書き込めなければ下のダウンロードへ */
    }
  }
  downloadBlob(blob, filename);
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** ユーザーが入力した名前を .stl 付きに整える */
export function withStlExtension(name: string): string {
  const base = name.trim() || "shadow-art";
  return base.toLowerCase().endsWith(".stl") ? base : `${base}.stl`;
}
