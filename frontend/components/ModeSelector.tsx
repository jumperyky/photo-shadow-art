"use client";

import type { Mode, ModeInfo } from "@/lib/types";

/**
 * 生成方式の選択。ここで選んだ方式に応じて、以降のトリミング比率・
 * パラメータ・プレビューの内容がすべて切り替わる。
 * 写真は選び直さずに切り替えられるので、両方式を見比べられる。
 */
export function ModeSelector({
  modes,
  value,
  onChange,
}: {
  modes: ModeInfo[];
  value: Mode;
  onChange: (mode: Mode) => void;
}) {
  return (
    <div className="mode-bar" role="radiogroup" aria-label="生成方式">
      {modes.map((m) => (
        <button
          key={m.id}
          type="button"
          role="radio"
          aria-checked={value === m.id}
          className={`mode-card${value === m.id ? " active" : ""}`}
          onClick={() => onChange(m.id)}
        >
          <span className="mode-icon" aria-hidden="true">
            {GLYPHS[m.id]()}
          </span>
          <span className="mode-text">
            <span className="mode-title">{m.label}</span>
            <span className="mode-desc">{m.description}</span>
          </span>
        </button>
      ))}
    </div>
  );
}

/** 線幅で濃淡を表すことを示す図 */
/**
 * モードごとのアイコン。Record<Mode,...> にしてあるので、モードを足すと
 * TypeScript がここの追加漏れを検出してくれる。
 */
const GLYPHS: Record<Mode, () => React.ReactElement> = {
  shadow_art: () => <ShadowArtGlyph />,
  lithophane: () => <LithophaneGlyph />,
  keychain: () => <KeychainGlyph />,
};

function KeychainGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none"
         stroke="currentColor" strokeWidth="1.6">
      <circle cx="12" cy="14.5" r="7" />
      <circle cx="12" cy="14.5" r="4.2" strokeDasharray="1.5 1.5" />
      <circle cx="12" cy="4" r="2.1" />
    </svg>
  );
}

function ShadowArtGlyph() {
  const widths = [1, 2, 3.4, 5, 3.4, 2, 1];
  return (
    <svg viewBox="0 0 40 40" width="40" height="40">
      <rect x="2" y="2" width="36" height="36" rx="3" fill="none"
            stroke="currentColor" strokeWidth="2.5" />
      {widths.map((w, i) => (
        <line
          key={i}
          x1="7"
          x2="33"
          y1={8 + i * 4}
          y2={8 + i * 4}
          stroke="currentColor"
          strokeWidth={w}
          strokeLinecap="round"
        />
      ))}
    </svg>
  );
}

/** 厚みで濃淡を表すことを示す図(断面) */
function LithophaneGlyph() {
  return (
    <svg viewBox="0 0 40 40" width="40" height="40">
      <path
        d="M6 30 L6 20 Q10 12 14 18 Q18 26 22 14 Q26 8 30 19 Q32 24 34 21 L34 30 Z"
        fill="currentColor"
        opacity="0.85"
      />
      <line x1="6" y1="30" x2="34" y2="30" stroke="currentColor" strokeWidth="2.5" />
      {[11, 20, 29].map((x) => (
        <line key={x} x1={x} y1="37" x2={x} y2="33" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" opacity="0.6" />
      ))}
    </svg>
  );
}
