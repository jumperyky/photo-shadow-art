"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Message, Panel } from "@/components/Controls";
import { CropStage } from "@/components/CropStage";
import { Dropzone } from "@/components/Dropzone";
import { ParamPanel } from "@/components/ParamPanel";
import { PreviewStage } from "@/components/PreviewStage";
import {
  ApiError,
  detectFace,
  fetchConfig,
  fetchPreview,
  fetchStl,
  imageUrl,
  pickSaveLocation,
  supportsSavePicker,
  uploadImage,
  withStlExtension,
  writeToTarget,
} from "@/lib/api";
import { DEFAULT_PARAMS, centeredCrop, cropAspect } from "@/lib/defaults";
import type {
  AppConfig,
  ArtParams,
  CropBox,
  PreviewResponse,
  Quality,
  UploadResponse,
} from "@/lib/types";

const PREVIEW_DEBOUNCE_MS = 280;

export default function Page() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [image, setImage] = useState<UploadResponse | null>(null);
  const [params, setParams] = useState<ArtParams>(DEFAULT_PARAMS);
  const [crop, setCrop] = useState<CropBox | null>(null);

  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [faceBusy, setFaceBusy] = useState(false);
  const [faceMessage, setFaceMessage] = useState<string | null>(null);

  const [filename, setFilename] = useState("shadow-art");
  const [quality, setQuality] = useState<Quality>("normal");
  const [stlBusy, setStlBusy] = useState(false);
  const [stlError, setStlError] = useState<string | null>(null);
  const [stlDone, setStlDone] = useState<string | null>(null);

  // 保存先ダイアログの可否はブラウザ依存なので、マウント後に判定する。
  // レンダー中に window を見るとSSRの結果と食い違ってハイドレーションが壊れる。
  const [canPickSaveLocation, setCanPickSaveLocation] = useState(false);

  const aspect = cropAspect(params);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setCanPickSaveLocation(supportsSavePicker());
  }, []);

  useEffect(() => {
    fetchConfig()
      .then(setConfig)
      .catch((e: Error) =>
        setPreviewError(
          `APIサーバーに接続できません（${e.message}）。backend が起動しているか確認してください。`,
        ),
      );
  }, []);

  const patch = useCallback((p: Partial<ArtParams>) => {
    setParams((prev) => ({ ...prev, ...p }));
  }, []);

  // -------------------------------------------------------------- 顔検出
  const runFaceDetect = useCallback(
    async (imageId: string, forAspect: number, margin: number) => {
      setFaceBusy(true);
      setFaceMessage(null);
      try {
        const res = await detectFace(imageId, forAspect, margin);
        if (res.crop) setCrop(res.crop);
        setFaceMessage(
          res.detected
            ? `${res.message} トリミング枠を顔に合わせました。`
            : res.message,
        );
      } catch (e) {
        setFaceMessage(`顔検出に失敗しました: ${(e as Error).message}`);
      } finally {
        setFaceBusy(false);
      }
    },
    [],
  );

  // ------------------------------------------------------------ アップロード
  const handleFile = useCallback(
    async (file: File) => {
      setUploadBusy(true);
      setUploadError(null);
      setPreviewError(null);
      setStlDone(null);
      try {
        const res = await uploadImage(file);
        setImage(res);
        setPreview(null);
        setCrop(centeredCrop(res.width, res.height, aspect));
        setFilename(suggestName(file.name));
        if (params.auto_face && config?.face_detection_available) {
          // 「高さ÷幅」で渡す点に注意（UIのアスペクトは 幅÷高さ）
          void runFaceDetect(res.image_id, 1 / aspect, params.face_margin);
        }
      } catch (e) {
        setUploadError((e as Error).message);
      } finally {
        setUploadBusy(false);
      }
    },
    [aspect, params.auto_face, params.face_margin, config, runFaceDetect],
  );

  // 形状の比率が変わったらトリミング枠を作り直す（自動検出中なら再検出）
  const prevAspectRef = useRef(aspect);
  useEffect(() => {
    if (!image || prevAspectRef.current === aspect) return;
    prevAspectRef.current = aspect;
    if (params.auto_face && config?.face_detection_available) {
      void runFaceDetect(image.image_id, 1 / aspect, params.face_margin);
    } else {
      setCrop(centeredCrop(image.width, image.height, aspect));
    }
  }, [aspect, image, params.auto_face, params.face_margin, config, runFaceDetect]);

  // 顔検出のON/マージン変更に追従
  const faceKey = params.auto_face ? `on:${params.face_margin}` : "off";
  const prevFaceKeyRef = useRef(faceKey);
  useEffect(() => {
    if (prevFaceKeyRef.current === faceKey) return;
    prevFaceKeyRef.current = faceKey;
    if (!image) return;
    if (params.auto_face && config?.face_detection_available) {
      void runFaceDetect(image.image_id, 1 / aspect, params.face_margin);
    } else {
      setFaceMessage(null);
    }
  }, [faceKey, image, params.auto_face, params.face_margin, aspect, config, runFaceDetect]);

  // ------------------------------------------------------------ プレビュー
  useEffect(() => {
    if (!image) return;
    const timer = setTimeout(() => {
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      setPreviewBusy(true);

      fetchPreview(image.image_id, params, crop, 760, ac.signal)
        .then((res) => {
          setPreview(res);
          setPreviewError(null);
        })
        .catch((e) => {
          if ((e as Error).name === "AbortError") return;
          setPreviewError((e as Error).message);
        })
        .finally(() => {
          if (!ac.signal.aborted) setPreviewBusy(false);
        });
    }, PREVIEW_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [image, params, crop]);

  useEffect(() => () => abortRef.current?.abort(), []);

  // ------------------------------------------------------------------ STL
  const handleExport = useCallback(async () => {
    if (!image) return;

    // 保存先ダイアログはクリック直後(ユーザー操作が有効なうち)に開く必要がある。
    // STLの生成を待ってから呼ぶとブラウザに拒否されるため、先に場所を訊いておく。
    const target = await pickSaveLocation(withStlExtension(filename));
    if (target.status === "cancelled") return;

    setStlBusy(true);
    setStlError(null);
    setStlDone(null);
    try {
      const { blob, filename: name } = await fetchStl(
        image.image_id,
        params,
        crop,
        filename,
        quality,
      );
      await writeToTarget(target, blob, name);
      setStlDone(`${name} を保存しました（${(blob.size / 1024 / 1024).toFixed(1)} MB）`);
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : `STLの生成に失敗しました: ${(e as Error).message}`;
      setStlError(msg);
    } finally {
      setStlBusy(false);
    }
  }, [image, params, crop, filename, quality]);

  const faceAvailable = config?.face_detection_available ?? false;

  return (
    <div className="app">
      <header className="header">
        <h1>Photo Shadow Art</h1>
        <span className="sub">写真 → 線幅で濃淡を表現する3DプリントSTL</span>
        <span className="spacer" />
        <span className="muted">
          最大造形サイズ {config?.max_print_size_mm ?? 1800}mm
        </span>
      </header>

      <main className="workspace">
        {/* ------------------------------------------------ 1. 写真 */}
        <div className="col">
          <Panel step={1} title="写真とトリミング" flush={!!image}>
            {image ? (
              <>
                <CropStage
                  src={imageUrl(image.image_id)}
                  aspect={aspect}
                  crop={crop}
                  onChange={setCrop}
                />
                <div className="crop-actions">
                  <button
                    type="button"
                    className="btn small"
                    onClick={() =>
                      setCrop(centeredCrop(image.width, image.height, aspect))
                    }
                  >
                    枠をリセット
                  </button>
                  {faceAvailable ? (
                    <button
                      type="button"
                      className="btn small"
                      disabled={faceBusy}
                      onClick={() =>
                        runFaceDetect(image.image_id, 1 / aspect, params.face_margin)
                      }
                    >
                      {faceBusy ? "検出中…" : "顔に合わせる"}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="btn small"
                    onClick={() => {
                      setImage(null);
                      setPreview(null);
                      setCrop(null);
                      setFaceMessage(null);
                    }}
                  >
                    別の写真にする
                  </button>
                </div>
              </>
            ) : (
              <>
                <Dropzone
                  onFile={handleFile}
                  disabled={uploadBusy}
                  maxBytes={config?.max_upload_bytes}
                />
                {uploadBusy ? <Message kind="info">アップロード中…</Message> : null}
                {uploadError ? <Message kind="error">{uploadError}</Message> : null}
              </>
            )}
          </Panel>

          {image ? (
            <Panel title="トリミングのヒント">
              <p className="muted" style={{ margin: 0 }}>
                枠の比率は右の「形状」設定に連動します。顔がはっきり大きく写るように
                寄せると、線の陰影で表情が出やすくなります。
              </p>
            </Panel>
          ) : null}
        </div>

        {/* ---------------------------------------------- 2. プレビュー */}
        <div className="col">
          <Panel step={2} title="プレビュー">
            <PreviewStage
              preview={preview}
              busy={previewBusy}
              error={previewError}
              hasImage={!!image}
            />
          </Panel>

          {/* ------------------------------------------------ 3. 出力 */}
          <Panel step={3} title="STLを出力">
            <div className="field">
              <div className="field-head">
                <label htmlFor="fname">ファイル名</label>
              </div>
              <input
                id="fname"
                className="text"
                value={filename}
                onChange={(e) => setFilename(e.target.value)}
                placeholder="shadow-art"
              />
            </div>

            <div className="field">
              <div className="field-head">
                <label htmlFor="quality">出力品質</label>
              </div>
              <select
                id="quality"
                className="select"
                value={quality}
                onChange={(e) => setQuality(e.target.value as Quality)}
              >
                <option value="draft">ドラフト（速い・粗い）</option>
                <option value="normal">標準</option>
                <option value="fine">高精細（遅い・大きいファイル）</option>
              </select>
            </div>

            <button
              type="button"
              className="btn primary block"
              onClick={handleExport}
              disabled={!image || stlBusy}
            >
              {stlBusy ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  生成中…
                </>
              ) : (
                "STLを出力する"
              )}
            </button>

            <p className="muted" style={{ marginBottom: 0 }}>
              {canPickSaveLocation
                ? "保存先を選ぶダイアログが開きます。"
                : "ブラウザのダウンロードフォルダに保存されます。"}
            </p>

            {stlError ? <Message kind="error">{stlError}</Message> : null}
            {stlDone ? <Message kind="info">{stlDone}</Message> : null}
          </Panel>
        </div>

        {/* ---------------------------------------- 4. パラメータ */}
        <div className="col col-params">
          <Panel title="パラメータ" flush>
            <ParamPanel
              params={params}
              onChange={patch}
              onReset={() => setParams(DEFAULT_PARAMS)}
              faceAvailable={faceAvailable}
              faceBusy={faceBusy}
              faceMessage={faceMessage}
              onDetectFace={() => {
                if (image) {
                  void runFaceDetect(image.image_id, 1 / aspect, params.face_margin);
                }
              }}
            />
          </Panel>
        </div>
      </main>
    </div>
  );
}

/** アップロードしたファイル名からSTLのファイル名候補を作る */
function suggestName(original: string): string {
  const base = original.replace(/\.[^.]+$/, "").trim();
  return base ? `${base}-shadow-art` : "shadow-art";
}
