"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const ACCEPT = "image/png,image/jpeg,image/webp,image/bmp,image/tiff";

export function Dropzone({
  onFile,
  disabled = false,
  maxBytes,
}: {
  onFile: (file: File) => void;
  disabled?: boolean;
  maxBytes?: number;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const take = useCallback(
    (files: FileList | null | undefined) => {
      const file = files?.[0];
      if (file && file.type.startsWith("image/")) onFile(file);
    },
    [onFile],
  );

  // クリップボードからの貼り付けにも対応
  useEffect(() => {
    if (disabled) return;
    const onPaste = (e: ClipboardEvent) => {
      const item = Array.from(e.clipboardData?.items ?? []).find((i) =>
        i.type.startsWith("image/"),
      );
      const file = item?.getAsFile();
      if (file) onFile(file);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [onFile, disabled]);

  const limitMb = maxBytes ? Math.floor(maxBytes / 1024 / 1024) : null;

  return (
    <div
      className={`dropzone${over ? " over" : ""}`}
      role="button"
      tabIndex={0}
      aria-disabled={disabled}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if (!disabled && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (!disabled) take(e.dataTransfer.files);
      }}
    >
      <strong>写真をドラッグ＆ドロップ</strong>
      クリックして選択 / ⌘V・Ctrl+V で貼り付け
      <div className="hint">
        JPEG・PNG・WebP など
        {limitMb ? `（最大 ${limitMb}MB）` : null}
      </div>
      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept={ACCEPT}
        disabled={disabled}
        onChange={(e) => {
          take(e.target.files);
          e.target.value = ""; // 同じファイルを続けて選べるようにする
        }}
      />
    </div>
  );
}
