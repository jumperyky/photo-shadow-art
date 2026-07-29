"use client";

import { Message } from "./Controls";
import { MAX_PRINT_SIZE_MM } from "@/lib/defaults";
import type { PreviewResponse } from "@/lib/types";

export function PreviewStage({
  preview,
  busy,
  error,
  hasImage,
}: {
  preview: PreviewResponse | null;
  busy: boolean;
  error: string | null;
  hasImage: boolean;
}) {
  const size = preview?.size;
  const overLimit = size ? !size.within_print_limit : false;

  return (
    <>
      <div className="preview-stage">
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview.image} alt="生成される形状のプレビュー" />
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

      {size ? (
        <div className="chips">
          <span className={`chip${overLimit ? " over" : ""}`}>
            外形
            <b>
              {fmt(size.outer_width_mm)} × {fmt(size.outer_height_mm)} mm
            </b>
          </span>
          <span className="chip">
            デザイン部
            <b>
              {fmt(size.design_width_mm)} × {fmt(size.design_height_mm)} mm
            </b>
          </span>
          <span className="chip">
            線
            <b>{size.line_count} 本</b>
          </span>
          <span className="chip">
            ピッチ
            <b>{size.pitch_mm.toFixed(2)} mm</b>
          </span>
          {preview ? (
            <span className="chip">
              生成
              <b>{preview.elapsed_ms} ms</b>
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
