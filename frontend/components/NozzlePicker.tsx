"use client";

import { Segmented } from "./Controls";
import { NOZZLE_OPTIONS } from "@/lib/defaults";
import type { SizeInfo } from "@/lib/types";

/**
 * ノズル径の選択(リソフェイン・キーホルダー共通)。
 *
 * 形状は変えない。サーバー側で「格子がノズルより粗くならないように分割数を
 * 引き上げる」のと、印刷できる解像度の表示・警告に使われる。プリンタ側の
 * 設定なので、どちらのモードで切り替えても両方に反映する(page.tsx)。
 */
export function NozzlePicker({
  value,
  onChange,
  samples,
  size,
}: {
  value: number;
  onChange: (nozzle: number) => void;
  /** スライダーで指定している分割数。引き上げられたかどうかの表示に使う。 */
  samples: number;
  size: SizeInfo | null;
}) {
  const raised =
    size?.samples_used != null && size.samples_used > samples
      ? size.samples_used
      : null;

  return (
    <>
      <Segmented<string>
        label="ノズル径"
        value={String(value)}
        options={NOZZLE_OPTIONS.map((n) => ({
          value: String(n),
          label: `${n} mm`,
        }))}
        onChange={(v) => onChange(Number(v))}
      />
      <p className="muted" style={{ margin: "-4px 0 10px" }}>
        形状は変わりません。
        {size?.printable_px ? (
          <>
            このノズルで印刷できる横解像度は <b>約 {size.printable_px}px</b>
            （縦はレイヤー高で決まるので、これよりずっと細かくなります）。
          </>
        ) : null}
        {raised !== null ? (
          <>
            {" "}
            格子がノズルより粗くならないよう、分割数を <b>{raised}</b>{" "}
            に引き上げています。
          </>
        ) : null}
      </p>
    </>
  );
}
