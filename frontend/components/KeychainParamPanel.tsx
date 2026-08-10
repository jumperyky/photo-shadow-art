"use client";

import { Message, Segmented, Slider, Toggle } from "./Controls";
import { SHAPE_LABELS } from "@/lib/defaults";
import type { KeychainParams, ShapeName, SizeInfo } from "@/lib/types";

/**
 * keychain_stl.py のパラメータを調整するパネル。
 *
 * 枠の厚みは直接いじらせず「レジンだまりの深さ」だけを見せている。
 * 枠厚 = 最大厚み + レジンだまり なので、この形にしておけば
 * 「枠が凹凸より低くてレジンが溜まらない」設定を作れない。
 */
export function KeychainParamPanel({
  params,
  onChange,
  onReset,
  size,
  faceAvailable,
  faceBusy,
  onDetectFace,
  faceMessage,
}: {
  params: KeychainParams;
  onChange: (patch: Partial<KeychainParams>) => void;
  onReset: () => void;
  size: SizeInfo | null;
  faceAvailable: boolean;
  faceBusy: boolean;
  onDetectFace: () => void;
  faceMessage: string | null;
}) {
  const usesPolygon = params.sides !== null;
  const frameThickness = params.max_thickness + params.well_depth;
  const tabDiameter = params.hole_diameter + params.ring_margin * 2;

  return (
    <>
      <div className="section">
        <h3>形状</h3>
        <Segmented<ShapeName>
          label="外形"
          value={params.shape}
          options={(Object.keys(SHAPE_LABELS) as ShapeName[]).map((s) => ({
            value: s,
            label: SHAPE_LABELS[s],
          }))}
          onChange={(shape) =>
            onChange({
              shape,
              aspect: shape === "rectangle" ? params.aspect : 1.0,
            })
          }
        />

        {params.shape === "rectangle" && !usesPolygon ? (
          <Slider
            label="縦横比（高さ÷幅）"
            value={params.aspect}
            onChange={(aspect) => onChange({ aspect })}
            min={0.3}
            max={3}
            step={0.01}
            hardMin={0.06}
            hardMax={20}
            decimals={2}
            help="トリミング枠もこの比率に追従します"
          />
        ) : null}

        <Toggle
          label="任意のn角形にする"
          desc="円・六角形の代わりに好きな頂点数の正多角形を使う"
          checked={usesPolygon}
          onChange={(on) => onChange({ sides: on ? 8 : null })}
        />
        {usesPolygon ? (
          <Slider
            label="頂点数"
            value={params.sides ?? 8}
            onChange={(sides) => onChange({ sides })}
            min={3}
            max={24}
            step={1}
            hardMax={64}
          />
        ) : null}
      </div>

      <div className="section">
        <h3>サイズ（mm）</h3>
        <Slider
          label="デザイン部の大きさ"
          value={params.diameter}
          onChange={(diameter) => onChange({ diameter })}
          min={30}
          max={120}
          step={1}
          hardMin={10}
          hardMax={200}
          help={
            size?.relief_px
              ? `写真が入る範囲。立てて印刷するため横の細かさはノズル径で決まります（実質 約${size.relief_px}px 相当）`
              : "写真が入る範囲。50mm以上を推奨します"
          }
        />
        <Slider
          label="枠の幅"
          value={params.frame_width}
          onChange={(frame_width) => onChange({ frame_width })}
          min={1}
          max={10}
          step={0.1}
          hardMin={0}
          hardMax={50}
          decimals={1}
          help="レジンを受け止めるダムになります"
        />
        {size ? (
          <p className="muted" style={{ margin: "-4px 0 10px" }}>
            外形の目安 {size.outer_width_mm} × {size.outer_height_mm} ×{" "}
            {size.outer_depth_mm} mm
          </p>
        ) : null}
      </div>

      <div className="section">
        <h3>厚み（mm）</h3>
        <Slider
          label="最小厚み（明部）"
          value={params.min_thickness}
          onChange={(min_thickness) => onChange({ min_thickness })}
          min={0.3}
          max={1.5}
          step={0.05}
          hardMin={0.2}
          hardMax={20}
          decimals={2}
          help="薄すぎると穴が開きます。0.6mm 前後が定番です"
        />
        <Slider
          label="最大厚み（暗部）"
          value={params.max_thickness}
          onChange={(max_thickness) => onChange({ max_thickness })}
          min={1.2}
          max={4}
          step={0.05}
          hardMin={0.4}
          hardMax={50}
          decimals={2}
          help="厚すぎると光が通らず暗部が潰れます"
        />
        <Slider
          label="レジンだまりの深さ"
          value={params.well_depth}
          onChange={(well_depth) => onChange({ well_depth })}
          min={0.3}
          max={2.5}
          step={0.05}
          hardMin={0.1}
          hardMax={20}
          decimals={2}
          help={`枠が凹凸よりこのぶん高くなります（枠の高さ ${frameThickness.toFixed(2)}mm）`}
        />
        {size?.resin_volume_ml ? (
          <p className="muted" style={{ margin: "-4px 0 10px" }}>
            必要なレジンの目安 約 {size.resin_volume_ml} ml
          </p>
        ) : null}
      </div>

      <div className="section">
        <h3>リング取付部</h3>
        <Slider
          label="穴の径"
          value={params.hole_diameter}
          onChange={(hole_diameter) => onChange({ hole_diameter })}
          min={2}
          max={8}
          step={0.1}
          hardMin={1}
          hardMax={30}
          decimals={1}
          help="市販のキーホルダーリングが通る大きさに"
        />
        <Slider
          label="穴の上の肉厚"
          value={params.ring_margin}
          onChange={(ring_margin) => onChange({ ring_margin })}
          min={1.5}
          max={6}
          step={0.1}
          hardMin={0.8}
          hardMax={30}
          decimals={1}
          help={`立てて印刷するとここは積層方向に引っ張られます（取付部の直径 ${tabDiameter.toFixed(1)}mm）`}
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
        <Slider
          label="分割数（横方向）"
          value={params.samples}
          onChange={(samples) => onChange({ samples })}
          min={120}
          max={600}
          step={10}
          hardMin={8}
          hardMax={800}
          help={
            size?.face_count
              ? `三角形 約${(size.face_count / 1000).toFixed(0)}k。多いほど精細ですがファイルも大きくなります`
              : "多いほど精細ですがファイルも大きくなります"
          }
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
          仕上げ方: レイヤー高 0.1mm・充填100%で<b>立てて印刷</b>し、
          ブリムを付けると安定します。印刷後、枠の内側に透明レジンを流して
          硬化させると表面が平らになり、凹凸が欠けたり引っ掛かったりしません。
          <b>リング穴にレジンが入らないよう</b>養生するか、硬化後にさらってください。
        </p>
        <button type="button" className="btn small" onClick={onReset}>
          パラメータを初期値に戻す
        </button>
      </div>
    </>
  );
}
