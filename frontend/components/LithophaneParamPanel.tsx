"use client";

import { Message, Slider, Toggle } from "./Controls";
import { MAX_PRINT_SIZE_MM } from "@/lib/defaults";
import type { LithophaneParams, SizeInfo } from "@/lib/types";

/**
 * lithophane_stl.py のパラメータを調整するパネル。
 * 値を変えるたびに親がプレビュー(裏から照らした見え方)を取り直す。
 */
export function LithophaneParamPanel({
  params,
  onChange,
  onReset,
  size,
  faceAvailable,
  faceBusy,
  onDetectFace,
  faceMessage,
}: {
  params: LithophaneParams;
  onChange: (patch: Partial<LithophaneParams>) => void;
  onReset: () => void;
  size: SizeInfo | null;
  faceAvailable: boolean;
  faceBusy: boolean;
  onDetectFace: () => void;
  faceMessage: string | null;
}) {
  const curved = params.curve > 0;

  return (
    <>
      <div className="section">
        <h3>サイズ（mm）</h3>
        <Slider
          label={curved ? "横幅（弧の長さ）" : "横幅"}
          value={params.width}
          onChange={(width) => onChange({ width })}
          min={30}
          max={300}
          step={1}
          hardMax={MAX_PRINT_SIZE_MM}
          unit="mm"
          help={
            size
              ? `高さはトリミング比率から決まります（現在 ${size.design_height_mm.toFixed(0)}mm）`
              : `スライダーは300mmまで。数値欄には最大${MAX_PRINT_SIZE_MM}mmまで直接入力できます`
          }
        />
        <Slider
          label="最小厚み（明部）"
          value={params.min_thickness}
          onChange={(min_thickness) => onChange({ min_thickness })}
          min={0.2}
          max={2}
          step={0.05}
          hardMax={100}
          unit="mm"
          decimals={2}
          help="薄すぎると穴が開きます。0.6mm 前後が定番です"
        />
        <Slider
          label="最大厚み（暗部）"
          value={params.max_thickness}
          onChange={(max_thickness) => onChange({ max_thickness })}
          min={1}
          max={8}
          step={0.05}
          hardMax={200}
          unit="mm"
          decimals={2}
          help="厚すぎると光が通らず暗部が潰れます。3mm 前後が定番です"
        />
      </div>

      <div className="section">
        <h3>形状</h3>
        <Slider
          label="湾曲（中心角）"
          value={params.curve}
          onChange={(curve) => onChange({ curve })}
          min={0}
          max={180}
          step={1}
          hardMax={350}
          unit="°"
          help={
            curved
              ? `円弧状に曲げます（内側の半径 ${size?.radius_mm?.toFixed(0) ?? "—"}mm）`
              : "0 で平板。ランプシェード状にするなら 60〜180° 程度"
          }
        />
        <Slider
          label="分割数（横方向）"
          value={params.samples}
          onChange={(samples) => onChange({ samples })}
          min={100}
          max={800}
          step={10}
          hardMax={1200}
          help={
            size?.grid
              ? `格子 ${size.grid} / 三角形 約${((size.face_count ?? 0) / 1000).toFixed(0)}k。多いほど精細でファイルも大きくなります`
              : "多いほど精細になり、STLのファイルサイズも大きくなります"
          }
        />
      </div>

      <div className="section">
        <h3>明暗</h3>
        <Slider
          label="ガンマ"
          value={params.gamma}
          onChange={(gamma) => onChange({ gamma })}
          min={0.3}
          max={2}
          step={0.05}
          hardMin={0.05}
          hardMax={5}
          decimals={2}
          help="1より小さくすると暗部の階調が出ます（0.8 前後が定番）"
        />
        <Toggle
          label="明るい所を厚くする"
          desc="裏から照らさず、彫刻（レリーフ）として見せる場合に使います"
          checked={params.positive}
          onChange={(positive) => onChange({ positive })}
        />
        <Toggle
          label="ヒストグラム均等化"
          desc="コントラストの低い写真に有効"
          checked={params.equalize}
          onChange={(equalize) => onChange({ equalize })}
        />
      </div>

      <div className="section">
        <h3>顔検出（自動トリミング）</h3>
        <Toggle
          label="顔を自動検出してトリミング"
          desc={
            faceAvailable
              ? "OpenCVのカスケード分類器で顔を探し、トリミング枠を合わせます"
              : "このサーバーでは顔検出を利用できません"
          }
          checked={params.auto_face}
          disabled={!faceAvailable}
          onChange={(auto_face) => onChange({ auto_face })}
        />
        {params.auto_face ? (
          <>
            <Slider
              label="顔まわりの余白"
              value={params.face_margin}
              onChange={(face_margin) => onChange({ face_margin })}
              min={0}
              max={2}
              step={0.05}
              hardMax={3}
              decimals={2}
              help="顔の幅に対する比率。大きいほど引きの構図になります"
            />
            <button
              type="button"
              className="btn small"
              onClick={onDetectFace}
              disabled={faceBusy || !faceAvailable}
            >
              {faceBusy ? "検出中…" : "もう一度検出する"}
            </button>
          </>
        ) : null}
        {faceMessage ? <Message kind="info">{faceMessage}</Message> : null}
      </div>

      <div className="section">
        <p className="muted" style={{ margin: "0 0 10px" }}>
          印刷のコツ: レイヤー高 0.1mm・壁を厚め（充填100%）で、
          <b>立てて印刷</b>するのが定番です。横倒しにするとレイヤーの段差が
          階調に出てしまいます。
        </p>
        <button type="button" className="btn" onClick={onReset}>
          パラメータを初期値に戻す
        </button>
      </div>
    </>
  );
}
