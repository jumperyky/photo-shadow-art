"use client";

import { Message, Segmented, Slider, Toggle } from "./Controls";
import { MAX_PRINT_SIZE_MM, SHAPE_LABELS } from "@/lib/defaults";
import type { ArtParams, ShapeName } from "@/lib/types";

/**
 * line_art_stl.py のパラメータをひと通り調整できるパネル。
 * 値を変えるたびに親がプレビューを取り直す。
 */
export function ParamPanel({
  params,
  onChange,
  onReset,
  faceAvailable,
  faceBusy,
  onDetectFace,
  faceMessage,
}: {
  params: ArtParams;
  onChange: (patch: Partial<ArtParams>) => void;
  onReset: () => void;
  faceAvailable: boolean;
  faceBusy: boolean;
  onDetectFace: () => void;
  faceMessage: string | null;
}) {
  const isBox = params.shape === "square" || params.shape === "rectangle";
  const usesPolygon = params.sides !== null;

  // 造形サイズの目安（枠を含む外形）
  const outerW = params.diameter + params.frame_width * 2;
  const outerH =
    (isBox && !usesPolygon ? params.diameter * params.aspect : params.diameter) +
    params.frame_width * 2;
  const overLimit = outerW > MAX_PRINT_SIZE_MM || outerH > MAX_PRINT_SIZE_MM;

  return (
    <>
      <div className="section">
        <h3>形状</h3>
        <Segmented<ShapeName>
          label="外枠の形"
          value={params.shape}
          options={(Object.keys(SHAPE_LABELS) as ShapeName[]).map((s) => ({
            value: s,
            label: SHAPE_LABELS[s],
          }))}
          onChange={(shape) =>
            onChange({
              shape,
              // 正方形を選んだら比率は1に戻す
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
          label={isBox ? "幅" : "直径"}
          value={params.diameter}
          onChange={(diameter) => onChange({ diameter })}
          min={30}
          max={400}
          step={1}
          hardMax={MAX_PRINT_SIZE_MM}
          unit="mm"
          help={`スライダーは400mmまで。数値欄には最大${MAX_PRINT_SIZE_MM}mmまで直接入力できます`}
        />
        <Slider
          label="外枠の幅"
          value={params.frame_width}
          onChange={(frame_width) => onChange({ frame_width })}
          min={0}
          max={40}
          step={0.5}
          hardMax={400}
          unit="mm"
          decimals={1}
        />
        <Slider
          label="線の厚み"
          value={params.thickness}
          onChange={(thickness) => onChange({ thickness })}
          min={0.5}
          max={10}
          step={0.1}
          hardMax={200}
          unit="mm"
          decimals={1}
        />
        <Slider
          label="外枠の厚み"
          value={params.frame_thickness}
          onChange={(frame_thickness) => onChange({ frame_thickness })}
          min={0.5}
          max={12}
          step={0.1}
          hardMax={200}
          unit="mm"
          decimals={1}
        />
        <p className={`muted${overLimit ? " over-limit" : ""}`} style={{ margin: 0 }}>
          外形の目安 {Math.round(outerW)} × {Math.round(outerH)} mm
          {overLimit ? `（最大造形サイズ ${MAX_PRINT_SIZE_MM}mm 超）` : null}
        </p>
      </div>

      <div className="section">
        <h3>線</h3>
        <Slider
          label="線の本数"
          value={params.lines}
          onChange={(lines) => onChange({ lines })}
          min={8}
          max={200}
          step={1}
          hardMax={2000}
          help="線の密度の基準。角まで届くよう実際の本数は自動で調整されます"
        />
        <Slider
          label="線の角度"
          value={params.angle}
          onChange={(angle) => onChange({ angle })}
          min={-90}
          max={90}
          step={1}
          hardMin={-180}
          hardMax={180}
          unit="°"
        />
        <Slider
          label="最小線幅"
          value={params.min_width}
          onChange={(min_width) => onChange({ min_width })}
          min={0.1}
          max={5}
          step={0.05}
          hardMax={200}
          unit="mm"
          decimals={2}
          help="細すぎると造形が安定しません（0.4mm以上を推奨）"
        />
        <Slider
          label="最大線幅"
          value={params.max_width}
          onChange={(max_width) => onChange({ max_width })}
          min={0.2}
          max={20}
          step={0.05}
          hardMax={400}
          unit="mm"
          decimals={2}
          help="太すぎると線同士がくっついて陰影が失われます"
        />
      </div>

      <div className="section">
        <h3>明暗</h3>
        <Slider
          label="ガンマ"
          value={params.gamma}
          onChange={(gamma) => onChange({ gamma })}
          min={0.2}
          max={3}
          step={0.05}
          hardMin={0.05}
          hardMax={5}
          decimals={2}
          help="1より大きくすると暗部が強調されます"
        />
        <Toggle
          label="明暗を反転"
          checked={params.invert}
          onChange={(invert) => onChange({ invert })}
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
        <button type="button" className="btn" onClick={onReset}>
          パラメータを初期値に戻す
        </button>
      </div>
    </>
  );
}
