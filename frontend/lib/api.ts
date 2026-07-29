import type {
  AppConfig,
  ArtParams,
  CropBox,
  FaceDetectResponse,
  PreviewResponse,
  Quality,
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

/** サーバーに渡すリクエストボディを組み立てる(shape依存の正規化もここで行う) */
function requestBody(imageId: string, params: ArtParams, crop: CropBox | null) {
  const isBox = params.shape === "square" || params.shape === "rectangle";
  return {
    image_id: imageId,
    shape: params.shape,
    sides: params.sides,
    // 円/六角形/n角形は常に等方なので aspect は 1 に固定して送る
    aspect: isBox && params.sides === null ? params.aspect : 1.0,
    diameter: params.diameter,
    lines: params.lines,
    angle: params.angle,
    min_width: params.min_width,
    max_width: params.max_width,
    thickness: params.thickness,
    frame_width: params.frame_width,
    frame_thickness: params.frame_thickness,
    gamma: params.gamma,
    invert: params.invert,
    equalize: params.equalize,
    crop,
    auto_face: params.auto_face,
    face_margin: params.face_margin,
  };
}

export function fetchPreview(
  imageId: string,
  params: ArtParams,
  crop: CropBox | null,
  previewSize: number,
  signal?: AbortSignal,
): Promise<PreviewResponse> {
  return postJson(
    "/api/preview",
    { ...requestBody(imageId, params, crop), preview_size: previewSize },
    signal,
  );
}

export interface StlResult {
  blob: Blob;
  filename: string;
}

export async function fetchStl(
  imageId: string,
  params: ArtParams,
  crop: CropBox | null,
  filename: string,
  quality: Quality,
): Promise<StlResult> {
  const res = await fetch(`${BASE}/api/stl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...requestBody(imageId, params, crop),
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
