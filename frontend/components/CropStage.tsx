"use client";

import { useCallback, useMemo } from "react";
import ReactCrop, { type PercentCrop } from "react-image-crop";
import type { CropBox } from "@/lib/types";

/**
 * 画像のトリミングUI。
 * 出力形状(shape / aspect)から決まる比率に固定されるので、
 * 「UI上で見えている枠 = 実際に出力される範囲」になる。
 */
export function CropStage({
  src,
  aspect,
  crop,
  onChange,
  onComplete,
  alt = "トリミング対象の画像",
}: {
  src: string;
  /** undefined なら自由な比率で切り抜ける(リソフェイン) */
  aspect?: number;
  crop: CropBox | null;
  onChange: (box: CropBox) => void;
  onComplete?: () => void;
  alt?: string;
}) {
  const percent: PercentCrop | undefined = useMemo(() => {
    if (!crop) return undefined;
    return {
      unit: "%",
      x: crop.left * 100,
      y: crop.top * 100,
      width: (crop.right - crop.left) * 100,
      height: (crop.bottom - crop.top) * 100,
    };
  }, [crop]);

  const handleChange = useCallback(
    (_pixel: unknown, p: PercentCrop) => {
      if (p.width <= 0 || p.height <= 0) return;
      onChange(clampBox({
        left: p.x / 100,
        top: p.y / 100,
        right: (p.x + p.width) / 100,
        bottom: (p.y + p.height) / 100,
      }));
    },
    [onChange],
  );

  return (
    <div className="crop-stage">
      <ReactCrop
        crop={percent}
        aspect={aspect}
        keepSelection
        minWidth={16}
        onChange={handleChange}
        onComplete={() => onComplete?.()}
      >
        {/* next/image はプロキシ経由の動的画像と相性が悪いので素の img を使う */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt={alt} />
      </ReactCrop>
    </div>
  );
}

/** 0..1 の範囲に収め、幅・高さが 0 にならないようにする */
function clampBox(b: CropBox): CropBox {
  const left = Math.min(Math.max(b.left, 0), 1);
  const top = Math.min(Math.max(b.top, 0), 1);
  const right = Math.min(Math.max(b.right, left + 0.001), 1);
  const bottom = Math.min(Math.max(b.bottom, top + 0.001), 1);
  return { left, top, right, bottom };
}
