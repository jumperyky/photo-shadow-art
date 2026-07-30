"use client";

import { FILAMENT_COLORS } from "@/lib/defaults";

/**
 * プレビューに使うフィラメントの色を選ぶ。
 *
 * 2Dプレビュー(サーバー描画)と3Dビューア(three.jsのマテリアル)の両方に
 * 同じ値が渡るので、タブを切り替えても色は変わらない。
 * 見た目だけの設定で、出力されるSTLには影響しない。
 */
export function FilamentPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (color: string) => void;
}) {
  return (
    <div
      className="filament-picker"
      role="radiogroup"
      aria-label="フィラメントの色"
    >
      <span className="filament-label">色</span>
      {FILAMENT_COLORS.map((c) => (
        <button
          key={c.value}
          type="button"
          role="radio"
          aria-checked={value === c.value}
          aria-label={c.label}
          title={c.label}
          className="filament-swatch"
          style={{ background: c.value }}
          onClick={() => onChange(c.value)}
        />
      ))}
    </div>
  );
}
