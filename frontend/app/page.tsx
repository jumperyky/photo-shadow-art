"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Message, Panel } from "@/components/Controls";
import { CropStage } from "@/components/CropStage";
import { Dropzone } from "@/components/Dropzone";
import { KeychainParamPanel } from "@/components/KeychainParamPanel";
import { LithophaneParamPanel } from "@/components/LithophaneParamPanel";
import { ModeSelector } from "@/components/ModeSelector";
import { ParamPanel } from "@/components/ParamPanel";
import { PreviewStage } from "@/components/PreviewStage";
import {
  ApiError,
  detectFace,
  fetchConfig,
  fetchMesh,
  fetchPreview,
  fetchStl,
  imageUrl,
  pickSaveLocation,
  supportsSavePicker,
  uploadImage,
  withStlExtension,
  writeToTarget,
} from "@/lib/api";
import {
  DEFAULT_FILAMENT,
  DEFAULT_KEYCHAIN,
  DEFAULT_LITHOPHANE,
  DEFAULT_SHADOW_ART,
  MODE_LABELS,
  centeredCrop,
  cropAspect,
  cropOutline,
} from "@/lib/defaults";
import type { MeshData } from "@/lib/mesh";
import type {
  AppConfig,
  CropBox,
  KeychainParams,
  LithophaneParams,
  Mode,
  ModeInfo,
  PreviewResponse,
  Quality,
  ShadowArtParams,
  UploadResponse,
  ViewMode,
} from "@/lib/types";

const PREVIEW_DEBOUNCE_MS = 280;

// 3Dはメッシュ生成と転送(数百KB〜1MB)を伴うので、2Dより長めに待つ。
// スライダーを動かしている最中に何度も投げないための間隔。
const MESH_DEBOUNCE_MS = 650;

const FALLBACK_MODES: ModeInfo[] = [
  {
    id: "shadow_art",
    label: "シャドウアート",
    description: "線の太さで濃淡を表現します。",
    defaults: {},
  },
  {
    id: "lithophane",
    label: "リソフェイン",
    description: "厚みで濃淡を表現します。裏から光を当てて見ます。",
    defaults: {},
  },
  {
    id: "keychain",
    label: "キーホルダー",
    description: "枠付きの小さなリソフェイン。レジンで固めて持ち運べます。",
    defaults: {},
  },
];

export default function Page() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [mode, setMode] = useState<Mode>("shadow_art");
  const [image, setImage] = useState<UploadResponse | null>(null);

  // 方式ごとにパラメータを保持する。切り替えても調整内容が失われない。
  const [shadowParams, setShadowParams] = useState<ShadowArtParams>(DEFAULT_SHADOW_ART);
  const [lithoParams, setLithoParams] = useState<LithophaneParams>(DEFAULT_LITHOPHANE);
  const [keychainParams, setKeychainParams] = useState<KeychainParams>(DEFAULT_KEYCHAIN);
  const [crop, setCrop] = useState<CropBox | null>(null);

  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [view, setView] = useState<ViewMode>("2d");
  // 2Dプレビューと3Dビューアの両方に渡す表示色。ジオメトリには影響しない。
  const [filament, setFilament] = useState(DEFAULT_FILAMENT);
  const [mesh, setMesh] = useState<MeshData | null>(null);
  const [meshBusy, setMeshBusy] = useState(false);
  const [meshError, setMeshError] = useState<string | null>(null);

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

  const litho = mode === "lithophane";
  const keychain = mode === "keychain";
  const common = litho ? lithoParams : keychain ? keychainParams : shadowParams;
  // 外形を持つモード(シャドウアート・キーホルダー)は形状パラメータを共有する
  const shapeSource = keychain ? keychainParams : shadowParams;
  const aspect = cropAspect(mode, shapeSource);
  // 形状が変わったときだけ作り直す。毎レンダーで新しい配列を返すと
  // ReactCrop(PureComponent)が描き直され、ドラッグが重くなる。
  const outline = useMemo(
    () => cropOutline(mode, shapeSource),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mode, shapeSource.shape, shapeSource.sides, shapeSource.aspect],
  );
  // API に渡すパラメータ束。参照が変わるとプレビューを取り直すので useMemo で固定する。
  const modeParams = useMemo(
    () => ({ shadow: shadowParams, litho: lithoParams, keychain: keychainParams }),
    [shadowParams, lithoParams, keychainParams],
  );
  const abortRef = useRef<AbortController | null>(null);
  const meshAbortRef = useRef<AbortController | null>(null);

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

  const patchShadow = useCallback((p: Partial<ShadowArtParams>) => {
    setShadowParams((prev) => ({ ...prev, ...p }));
  }, []);
  const patchLitho = useCallback((p: Partial<LithophaneParams>) => {
    setLithoParams((prev) => ({ ...prev, ...p }));
  }, []);
  const patchKeychain = useCallback((p: Partial<KeychainParams>) => {
    setKeychainParams((prev) => ({ ...prev, ...p }));
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
          res.detected ? `${res.message} トリミング枠を顔に合わせました。` : res.message,
        );
      } catch (e) {
        setFaceMessage(`顔検出に失敗しました: ${(e as Error).message}`);
      } finally {
        setFaceBusy(false);
      }
    },
    [],
  );

  // 顔検出に渡す比率。リソフェインは比率が自由なので正方形基準で探す。
  const faceAspect = useMemo(
    () => (aspect === undefined ? 1 : 1 / aspect),
    [aspect],
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
        setMesh(null);
        setMeshError(null);
        setCrop(centeredCrop(res.width, res.height, aspect));
        setFilename(suggestName(file.name, mode));
        if (common.auto_face && config?.face_detection_available) {
          void runFaceDetect(res.image_id, faceAspect, common.face_margin);
        }
      } catch (e) {
        setUploadError((e as Error).message);
      } finally {
        setUploadBusy(false);
      }
    },
    [aspect, faceAspect, mode, common.auto_face, common.face_margin, config, runFaceDetect],
  );

  // 形状の比率が変わったらトリミング枠を作り直す（自動検出中なら再検出）
  const prevAspectRef = useRef(aspect);
  useEffect(() => {
    if (!image || prevAspectRef.current === aspect) return;
    prevAspectRef.current = aspect;
    if (common.auto_face && config?.face_detection_available) {
      void runFaceDetect(image.image_id, faceAspect, common.face_margin);
    } else {
      setCrop(centeredCrop(image.width, image.height, aspect));
    }
  }, [aspect, faceAspect, image, common.auto_face, common.face_margin, config, runFaceDetect]);

  // 顔検出のON/マージン変更に追従
  const faceKey = common.auto_face ? `${mode}:on:${common.face_margin}` : `${mode}:off`;
  const prevFaceKeyRef = useRef(faceKey);
  useEffect(() => {
    if (prevFaceKeyRef.current === faceKey) return;
    prevFaceKeyRef.current = faceKey;
    if (!image) return;
    if (common.auto_face && config?.face_detection_available) {
      void runFaceDetect(image.image_id, faceAspect, common.face_margin);
    } else {
      setFaceMessage(null);
    }
  }, [faceKey, image, common.auto_face, common.face_margin, faceAspect, config, runFaceDetect]);

  // ------------------------------------------------------------ プレビュー
  useEffect(() => {
    if (!image) return;
    const timer = setTimeout(() => {
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      setPreviewBusy(true);

      fetchPreview(
        mode, image.image_id, modeParams, crop, 760, filament, ac.signal)
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
  }, [mode, image, modeParams, crop, filament]);

  useEffect(() => () => abortRef.current?.abort(), []);

  // -------------------------------------------------------- 3Dメッシュ
  // 3Dタブを開いているときだけ取りに行く。2Dで作業している間は
  // 重いメッシュ生成を走らせない。
  useEffect(() => {
    if (!image || view !== "3d") return;
    const timer = setTimeout(() => {
      meshAbortRef.current?.abort();
      const ac = new AbortController();
      meshAbortRef.current = ac;
      setMeshBusy(true);

      fetchMesh(mode, image.image_id, modeParams, crop, "medium", ac.signal)
        .then((res) => {
          setMesh(res);
          setMeshError(null);
        })
        .catch((e) => {
          if ((e as Error).name === "AbortError") return;
          setMeshError((e as Error).message);
        })
        .finally(() => {
          if (!ac.signal.aborted) setMeshBusy(false);
        });
    }, MESH_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [view, mode, image, modeParams, crop]);

  useEffect(() => () => meshAbortRef.current?.abort(), []);

  // ------------------------------------------------------------ モード切替
  const handleModeChange = useCallback(
    (next: Mode) => {
      if (next === mode) return;
      setMode(next);
      setPreview(null);
      // 方式が変われば形状も別物なので、前のメッシュは破棄する
      setMesh(null);
      setMeshError(null);
      setStlDone(null);
      setStlError(null);
      setFilename((prev) => swapModeSuffix(prev, mode, next));
    },
    [mode],
  );

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
        mode,
        image.image_id,
        modeParams,
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
  }, [mode, image, shadowParams, lithoParams, crop, filename, quality]);

  const faceAvailable = config?.face_detection_available ?? false;
  const modes = config?.modes ?? FALLBACK_MODES;

  return (
    <div className="app">
      <header className="header">
        <h1>Photo Shadow Art</h1>
        <span className="sub">写真 → 3DプリントSTL</span>
        <span className="spacer" />
        <span className="muted">
          最大造形サイズ {config?.max_print_size_mm ?? 1800}mm
        </span>
      </header>

      <div className="mode-row">
        <span className="mode-step">1</span>
        <span className="mode-label">つくり方を選ぶ</span>
        <ModeSelector modes={modes} value={mode} onChange={handleModeChange} />
      </div>

      <main className="workspace">
        {/* ------------------------------------------------ 2. 写真 */}
        <div className="col">
          <Panel step={2} title="写真とトリミング" flush={!!image}>
            {image ? (
              <>
                <CropStage
                  src={imageUrl(image.image_id)}
                  aspect={aspect}
                  outline={outline}
                  crop={crop}
                  onChange={setCrop}
                />
                <div className="crop-actions">
                  <button
                    type="button"
                    className="btn small"
                    onClick={() => setCrop(centeredCrop(image.width, image.height, aspect))}
                  >
                    枠をリセット
                  </button>
                  {faceAvailable ? (
                    <button
                      type="button"
                      className="btn small"
                      disabled={faceBusy}
                      onClick={() =>
                        runFaceDetect(image.image_id, faceAspect, common.face_margin)
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
                      setMesh(null);
                      setMeshError(null);
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
                {litho
                  ? "リソフェインは板の縦横比がトリミングでそのまま決まるので、比率は自由に切り抜けます。明暗の差がはっきりした写真ほどきれいに出ます。"
                  : outline
                    ? "枠の中の点線が実際に出力される形です。暗くなっている四隅は切り落とされるので、顔がこの形の内側に収まるように寄せてください。"
                    : "枠の比率は右の「形状」設定に連動します。顔がはっきり大きく写るように寄せると、線の陰影で表情が出やすくなります。"}
              </p>
            </Panel>
          ) : null}
        </div>

        {/* ---------------------------------------------- 3. プレビュー */}
        <div className="col">
          <Panel step={3} title="プレビュー">
            <PreviewStage
              mode={mode}
              view={view}
              onViewChange={setView}
              filament={filament}
              onFilamentChange={setFilament}
              preview={preview}
              busy={previewBusy}
              error={previewError}
              hasImage={!!image}
              mesh={mesh}
              meshBusy={meshBusy}
              meshError={meshError}
            />
          </Panel>

          {/* ------------------------------------------------ 4. 出力 */}
          <Panel step={4} title="STLを出力">
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
                <option value="draft">
                  {litho ? "ドラフト（分割数 半分・速い）" : "ドラフト（速い・粗い）"}
                </option>
                <option value="normal">標準</option>
                <option value="fine">
                  {litho ? "高精細（分割数 1.5倍・重い）" : "高精細（遅い・大きいファイル）"}
                </option>
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
              {litho ? " リソフェインは分割数によってファイルが数十MBになります。" : null}
            </p>

            {stlError ? <Message kind="error">{stlError}</Message> : null}
            {stlDone ? <Message kind="info">{stlDone}</Message> : null}
          </Panel>
        </div>

        {/* ---------------------------------------- 5. パラメータ */}
        <div className="col col-params">
          <Panel title={`パラメータ（${MODE_LABELS[mode]}）`} flush>
            {keychain ? (
              <KeychainParamPanel
                params={keychainParams}
                onChange={patchKeychain}
                onReset={() => setKeychainParams(DEFAULT_KEYCHAIN)}
                size={preview?.size ?? null}
                faceAvailable={faceAvailable}
                faceBusy={faceBusy}
                faceMessage={faceMessage}
                onDetectFace={() => {
                  if (image) {
                    void runFaceDetect(image.image_id, faceAspect, keychainParams.face_margin);
                  }
                }}
              />
            ) : litho ? (
              <LithophaneParamPanel
                params={lithoParams}
                onChange={patchLitho}
                onReset={() => setLithoParams(DEFAULT_LITHOPHANE)}
                size={preview?.size ?? null}
                faceAvailable={faceAvailable}
                faceBusy={faceBusy}
                faceMessage={faceMessage}
                onDetectFace={() => {
                  if (image) {
                    void runFaceDetect(image.image_id, faceAspect, lithoParams.face_margin);
                  }
                }}
              />
            ) : (
              <ParamPanel
                params={shadowParams}
                onChange={patchShadow}
                onReset={() => setShadowParams(DEFAULT_SHADOW_ART)}
                faceAvailable={faceAvailable}
                faceBusy={faceBusy}
                faceMessage={faceMessage}
                onDetectFace={() => {
                  if (image) {
                    void runFaceDetect(image.image_id, faceAspect, shadowParams.face_margin);
                  }
                }}
              />
            )}
          </Panel>
        </div>
      </main>
    </div>
  );
}

const MODE_SUFFIX: Record<Mode, string> = {
  shadow_art: "-shadow-art",
  lithophane: "-lithophane",
  keychain: "-keychain",
};

/** アップロードしたファイル名からSTLのファイル名候補を作る */
function suggestName(original: string, mode: Mode): string {
  const base = original.replace(/\.[^.]+$/, "").trim();
  return base ? `${base}${MODE_SUFFIX[mode]}` : MODE_SUFFIX[mode].slice(1);
}

/** モードを切り替えたらファイル名の接尾辞も付け替える */
function swapModeSuffix(current: string, from: Mode, to: Mode): string {
  const oldSuffix = MODE_SUFFIX[from];
  const newSuffix = MODE_SUFFIX[to];
  if (current.endsWith(oldSuffix)) {
    return current.slice(0, -oldSuffix.length) + newSuffix;
  }
  if (current === oldSuffix.slice(1)) return newSuffix.slice(1);
  return current;
}
