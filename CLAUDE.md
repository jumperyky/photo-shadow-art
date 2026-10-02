# CLAUDE.md

写真を 3D プリント用の STL に変換するツール。方式は 3 つ（シャドウアート / リソフェイン / キーホルダー）。
CLI に加えて、ブラウザ GUI（Next.js + FastAPI）がある。
セットアップ・使い方・API は [README.md](./README.md)。**変更の前に README の「8. 設計上のポイント・ハマりどころ」を読むこと。**
実際に踏んだ不具合の理由が書いてある。

リポジトリは**公開**。実在の人物の写真をコミットしない（`samples/` は合成画像だけ）。

## 起動とテスト

```bash
./dev.sh    # API(:8000) と UI(:3000)。Windows は start.bat
```

```bash
python3 -m pytest tests/ -q
cd frontend && npm run typecheck && npm run build
```

## 守ること

- **モードを足したら API の 4 箇所すべてを直す。** `/api/config` `/api/preview` `/api/mesh` `/api/stl`。
  分岐が漏れると、新しいモードが黙ってシャドウアートとして処理される。
- トリミング枠の輪郭は、バックエンドの `make_shape_polygon()` とフロントの `cropOutline()`
  （`frontend/lib/defaults.ts`）の両方にある。形状を足すときは両方を揃える。
- フィラメント色の明暗判定も 2 箇所（バックエンドの `_luma()` と 3D ビューアの `isLightFilament()`）。閾値を揃える。
- リソフェインの `build_mesh()` は行と列を反転させている（法線と左右反転のため）。触るなら `validate=True` のテストを通す。
- キーホルダーは矩形スラブをブーリアンで切り抜く方式。`Lithophane.footprint()` / `.face_count` はキーホルダーに使わない。
- Python API は `127.0.0.1` にだけバインドする。LAN に出すのは Next.js 側だけ。
- `output: "export"` は `NEXT_OUTPUT_EXPORT=1` のときだけ。常時オンにすると `dev.sh` のプロキシが壊れる。
- FastAPI の静的配信の `mount` は `main.py` の最後に置く。前に置くと `/api/*` が隠れる。
- `.bat` は CP932・CRLF、`.sh` は LF（`.gitattributes` で強制している）。
