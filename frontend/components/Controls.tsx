"use client";

import { useEffect, useId, useState } from "react";

/**
 * スライダー + 数値入力。
 * スライダーは扱いやすい範囲(sliderMax)に限定しつつ、
 * 数値入力では hardMax まで直接指定できる。
 * 大きなサイズ(最大1800mm)を刻みなく入れられるようにするための作り。
 */
export function Slider({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  hardMax,
  hardMin,
  unit,
  decimals = 0,
  disabled = false,
  help,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  hardMax?: number;
  hardMin?: number;
  unit?: string;
  decimals?: number;
  disabled?: boolean;
  help?: string;
}) {
  const id = useId();
  const lo = hardMin ?? min;
  const hi = hardMax ?? max;

  // 入力途中("1." や空文字)を潰さないよう、テキストは別に保持する
  const [text, setText] = useState(() => format(value, decimals));
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!editing) setText(format(value, decimals));
  }, [value, decimals, editing]);

  const commit = (raw: string) => {
    const n = Number(raw);
    if (raw.trim() === "" || Number.isNaN(n)) {
      setText(format(value, decimals));
      return;
    }
    onChange(clamp(n, lo, hi));
  };

  // スライダーの上限を超えた値でも、つまみが振り切れて見えるだけで値は保持される
  const sliderMax = Math.max(max, Math.min(value, hi));

  return (
    <div className="field">
      <div className="field-head">
        <label htmlFor={id}>{label}</label>
        {unit ? <span className="unit">{unit}</span> : null}
        <input
          className="num-input"
          type="number"
          inputMode="decimal"
          value={text}
          min={lo}
          max={hi}
          step={step}
          disabled={disabled}
          aria-label={`${label}（数値入力）`}
          onFocus={() => setEditing(true)}
          onChange={(e) => {
            setText(e.target.value);
            const n = Number(e.target.value);
            if (e.target.value.trim() !== "" && !Number.isNaN(n)) {
              onChange(clamp(n, lo, hi));
            }
          }}
          onBlur={(e) => {
            setEditing(false);
            commit(e.target.value);
          }}
        />
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={sliderMax}
        step={step}
        value={clamp(value, min, sliderMax)}
        disabled={disabled}
        onChange={(e) => onChange(clamp(Number(e.target.value), lo, hi))}
      />
      {help ? <div className="muted">{help}</div> : null}
    </div>
  );
}

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

function format(v: number, decimals: number) {
  return decimals > 0 ? v.toFixed(decimals) : String(Math.round(v));
}

export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="field">
      <div className="field-head">
        <label>{label}</label>
      </div>
      <div className="seg" role="group" aria-label={label}>
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            aria-pressed={value === o.value}
            onClick={() => onChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Toggle({
  label,
  desc,
  checked,
  onChange,
  disabled = false,
}: {
  label: string;
  desc?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="toggle">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        {label}
        {desc ? <span className="desc">{desc}</span> : null}
      </span>
    </label>
  );
}

export function Message({
  kind,
  children,
}: {
  kind: "warn" | "info" | "error";
  children: React.ReactNode;
}) {
  const icon = kind === "warn" ? "⚠" : kind === "error" ? "✕" : "ℹ";
  return (
    <div className={`msg ${kind}`} role={kind === "error" ? "alert" : "status"}>
      <span className="icon" aria-hidden="true">
        {icon}
      </span>
      <span>{children}</span>
    </div>
  );
}

export function Panel({
  step,
  title,
  action,
  flush = false,
  children,
}: {
  step?: number;
  title: string;
  action?: React.ReactNode;
  flush?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        {step !== undefined ? <span className="step">{step}</span> : null}
        <h2>{title}</h2>
        <span className="spacer" />
        {action}
      </div>
      <div className={`panel-body${flush ? " flush" : ""}`}>{children}</div>
    </section>
  );
}
