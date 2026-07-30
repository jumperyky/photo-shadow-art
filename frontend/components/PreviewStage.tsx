"use client";

import { Message } from "./Controls";
import { FilamentPicker } from "./FilamentPicker";
import { MeshViewer } from "./MeshViewer";
import { MAX_PRINT_SIZE_MM } from "@/lib/defaults";
import type { MeshData } from "@/lib/mesh";
import type { Mode, PreviewResponse, ViewMode } from "@/lib/types";

export function PreviewStage({
  mode,
  view,
  onViewChange,
  filament,
  onFilamentChange,
  preview,
  busy,
  error,
  hasImage,
  mesh,
  meshBusy,
  meshError,
}: {
  mode: Mode;
  view: ViewMode;
  onViewChange: (v: ViewMode) => void;
  filament: string;
  onFilamentChange: (color: string) => void;
  preview: PreviewResponse | null;
  busy: boolean;
  error: string | null;
  hasImage: boolean;
  mesh: MeshData | null;
  meshBusy: boolean;
  meshError: string | null;
}) {
  const size = preview?.size;
  const overLimit = size ? !size.within_print_limit : false;
  const litho = mode === "lithophane";
  const is3d = view === "3d";

  return (
    <>
      <div className="preview-toolbar">
        <div className="view-tabs" role="tablist" aria-label="プレビューの表示方法">
          <button
            type="button"
            role="tab"
            aria-selected={!is3d}
            onClick={() => onViewChange("2d")}
          >
            {litho ? "2D（光の見え方）" : "2D（形状）"}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={is3d}
            onClick={() => onViewChange("3d")}
          >
            3D
          </button>
        </div>
        <FilamentPicker value={filament} onChange={onFilamentChange} />
      </div>

      {is3d ? (
        <MeshViewer
          mesh={mesh}
          mode={mode}
          color={filament}
          busy={meshBusy}
          error={meshError}
        />
      ) : (
        <div className={`preview-stage${litho ? " backlit" : ""}`}>
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={preview.image}
              alt={
                litho
                  ? "裏から光を当てたときの見え方のプレビュー"
                  : "生成される形状のプレビュー"
              }
            />
          ) : (
            <p className="preview-empty">
              {hasImage
                ? "プレビューを生成しています…"
                : "写真をアップロードすると、ここに仕上がりのプレビューが表示されます。"}
            </p>
          )}
          {busy ? (
            <div className="preview-busy">
              <span className="spinner" aria-hidden="true" />
              更新中
            </div>
          ) : null}
        </div>
      )}

      {is3d ? (
        mesh ? (
          <p className="muted preview-caption">
            {`プリントベッドに置いた状態で表示しています。表示用に粗くした${mesh.triangleCount.toLocaleString()}三角形のモデルなので、実際の出力はこれより滑らかです。`}
          </p>
        ) : null
      ) : litho && preview ? (
        <p className="muted preview-caption">
          裏から光を当てたときの見え方をシミュレートしています。
        </p>
      ) : null}

      {meshError && is3d ? <Message kind="error">{meshError}</Message> : null}

      {size ? (
        <div className="chips">
          <span className={`chip${overLimit ? " over" : ""}`}>
            外形
            <b>
              {fmt(size.outer_width_mm)} × {fmt(size.outer_height_mm)} ×{" "}
              {fmt(size.outer_depth_mm)} mm
            </b>
          </span>

          {litho ? (
            <>
              <span className="chip">
                厚み
                <b>
                  {size.min_thickness_mm?.toFixed(2)}–
                  {size.max_thickness_mm?.toFixed(2)} mm
                </b>
              </span>
              {size.grid ? (
                <span className="chip">
                  格子<b>{size.grid}</b>
                </span>
              ) : null}
              {size.face_count ? (
                <span className="chip">
                  三角形<b>{(size.face_count / 1000).toFixed(0)}k</b>
                </span>
              ) : null}
              {size.radius_mm ? (
                <span className="chip">
                  曲率半径<b>{size.radius_mm.toFixed(0)} mm</b>
                </span>
              ) : null}
            </>
          ) : (
            <>
              <span className="chip">
                デザイン部
                <b>
                  {fmt(size.design_width_mm)} × {fmt(size.design_height_mm)} mm
                </b>
              </span>
              {size.line_count ? (
                <span className="chip">
                  線<b>{size.line_count} 本</b>
                </span>
              ) : null}
              {size.pitch_mm ? (
                <span className="chip">
                  ピッチ<b>{size.pitch_mm.toFixed(2)} mm</b>
                </span>
              ) : null}
            </>
          )}

          {preview ? (
            <span className="chip">
              生成<b>{preview.elapsed_ms} ms</b>
            </span>
          ) : null}
        </div>
      ) : null}

      {error ? <Message kind="error">{error}</Message> : null}

      {preview?.notices.map((n, i) => (
        <Message key={`n${i}`} kind="info">
          {n}
        </Message>
      ))}

      {preview?.warnings.map((w, i) => (
        <Message key={`w${i}`} kind="warn">
          {w}
          {w.includes("最大造形サイズ")
            ? `（${MAX_PRINT_SIZE_MM}mm を超える作品は分割印刷が必要です。STLの生成自体は行えます）`
            : null}
        </Message>
      ))}
    </>
  );
}

function fmt(v: number): string {
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}
