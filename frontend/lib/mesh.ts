/**
 * 3Dプレビュー用メッシュ("PSAM"バイナリ)の取得とデコード。
 *
 * バックエンド(backend/app/main.py の _mesh_response)と対になっている。
 * STLは1三角形あたり50バイトで頂点を共有しないため、同じ形状でも
 * インデックス付きのこの形式のほうが1/3以下に収まる。
 *
 * レイアウト (リトルエンディアン):
 *   magic   char[4]  "PSAM"
 *   version uint32   1
 *   n_vert  uint32
 *   n_index uint32
 *   pos     float32[n_vert * 3]   XYZ (mm)。XYは中心、Zは底面が0
 *   index   uint32[n_index]
 */

const MAGIC = "PSAM";
const HEADER_BYTES = 16;
const SUPPORTED_VERSION = 1;

export interface MeshData {
  positions: Float32Array;
  indices: Uint32Array;
  vertexCount: number;
  triangleCount: number;
  /** バイト数(UIに転送量を出すため) */
  byteLength: number;
}

export function decodeMesh(buffer: ArrayBuffer): MeshData {
  if (buffer.byteLength < HEADER_BYTES) {
    throw new Error("メッシュデータが短すぎます");
  }
  const view = new DataView(buffer);
  const magic = String.fromCharCode(
    view.getUint8(0),
    view.getUint8(1),
    view.getUint8(2),
    view.getUint8(3),
  );
  if (magic !== MAGIC) {
    throw new Error(`メッシュの形式が不正です (magic=${magic})`);
  }
  const version = view.getUint32(4, true);
  if (version !== SUPPORTED_VERSION) {
    throw new Error(`未対応のメッシュ形式です (version=${version})`);
  }
  const vertexCount = view.getUint32(8, true);
  const indexCount = view.getUint32(12, true);

  const expected = HEADER_BYTES + vertexCount * 12 + indexCount * 4;
  if (buffer.byteLength !== expected) {
    throw new Error(
      `メッシュのサイズが合いません (期待 ${expected} / 実際 ${buffer.byteLength})`,
    );
  }

  // Float32Array/Uint32Array は 4バイト境界を要求する。ヘッダが16バイトなので
  // 常に揃っているが、slice せず参照で持つことでコピーを避けている。
  const positions = new Float32Array(buffer, HEADER_BYTES, vertexCount * 3);
  const indices = new Uint32Array(
    buffer,
    HEADER_BYTES + vertexCount * 12,
    indexCount,
  );

  return {
    positions,
    indices,
    vertexCount,
    triangleCount: indexCount / 3,
    byteLength: buffer.byteLength,
  };
}
