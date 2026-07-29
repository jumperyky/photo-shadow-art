# Photo Shadow Art — 引き継ぎ資料

写真を「線幅で濃淡を表現するシャドウアート」風の3Dプリント用STLに変換するツール。
CLIに加えて、ブラウザから操作できるGUI(Next.js + FastAPI)を同梱しています。

## 1. これは何か

Instagram(stlai.3d などのアカウント)で見かける、次のようなスタイルの3Dプリント作品を
自分の好きな写真から自作するためのツール。

- 一定ピッチ・一定角度の平行線(リッジ)を並べる
- 各線の太さを、その位置の元写真の明度に応じて変える
  (暗い部分=太い線・隙間が狭い / 明るい部分=細い線・隙間が広い)
- 外枠(四角・円・六角形など)でクリップし、枠自体もリング状のリッジとして
  線同士をつなぎ、1つの印刷可能な形状にする
- 一定の厚みで押し出してSTLを書き出す

いわゆる「ラインスクリーン(line screen)」「シャドウアート」と呼ばれる手法で、
背景に光を通す/影を落とすと写真のような像が浮かび上がる仕組み。

## 2. ファイル構成

```
photo-shadow-art/
├── README.md              ← このファイル
├── requirements.txt        ← コア(CLI)の依存
├── dev.sh                  ← API + UI をまとめて起動する開発用スクリプト
├── line_art_stl.py         ← 本体(CLI兼ライブラリ)。ジオメトリ生成の実装はすべてここ
├── samples/
│   ├── test_silhouette.png ← 動作確認用の合成テスト画像
│   └── test_face.png       ← 顔検出の動作確認用の合成顔画像(実在の人物ではない)
├── tests/
│   ├── test_line_art_stl.py ← コアの回帰テスト
│   └── test_api.py          ← APIのテスト
├── backend/                ← Python APIサーバー (FastAPI)
│   ├── requirements.txt
│   └── app/
│       ├── main.py         ← エンドポイント定義
│       ├── schemas.py      ← リクエスト/レスポンスのスキーマと入力検証
│       └── storage.py      ← アップロード画像の一時保管
└── frontend/               ← GUI (Next.js App Router + TypeScript)
    ├── app/
    │   ├── page.tsx        ← メイン画面(状態管理はすべてここ)
    │   ├── layout.tsx
    │   └── globals.css
    ├── components/
    │   ├── Dropzone.tsx    ← 画像アップロード
    │   ├── CropStage.tsx   ← react-image-crop によるトリミング
    │   ├── ParamPanel.tsx  ← パラメータ調整UI
    │   ├── PreviewStage.tsx← プレビュー表示
    │   └── Controls.tsx    ← スライダー等の共通部品
    └── lib/
        ├── api.ts          ← APIクライアント
        ├── types.ts
        └── defaults.ts
```

## 3. セットアップ

### 3-0. かんたん手順(推奨)

```bash
./setup.sh      # .venv 作成 + Python/npm の依存インストール + 動作確認
./dev.sh        # API(:8000) と UI(:3000) を起動
```

ブラウザで http://localhost:3000 を開く。停止は Ctrl+C。

必要なもの: Python 3.10以上、Node.js 20以上。
`dev.sh` は `./.venv` があれば自動で使うので、仮想環境を activate する必要はない。

ポートが埋まっている場合:

```bash
PORT_UI=3100 PORT_API=8001 ./dev.sh
```

以下は手動で入れる場合の内訳。

### 3-1. Python(CLI・APIサーバー共通)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt   # コアの requirements.txt も一緒に入る
```

CLIだけ使う場合は `pip install -r requirements.txt` で足ります。

> **注意 (OpenCV):** 顔検出には haarcascade のXMLが必要ですが、
> OpenCV 5.x はこれを同梱しなくなりました。そのため
> `opencv-python-headless>=4.8,<5` にピン留めしてあります。
> 別の場所にXMLがある場合は環境変数 `HAARCASCADE_DIR` で指定できます。

> **注意 (trimesh):** ポリゴンの押し出しに三角形分割エンジンが必要です。
> `mapbox-earcut` を requirements.txt に追加してあります
> (これが無いと `No available triangulation engine!` で落ちます)。

### 3-2. フロントエンド

```bash
cd frontend
npm install
```

### 3-3. 起動

```bash
./dev.sh            # API(:8000) と UI(:3000) を同時に起動
```

個別に起動する場合:

```bash
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

ブラウザで http://localhost:3000 を開きます。
フロントの `/api/*` は `next.config.mjs` の rewrites でAPIへプロキシしているため、
CORSの設定を気にする必要はありません(APIのURLを変えたい場合は環境変数
`API_BASE_URL` を指定)。

この構成では Python API は `127.0.0.1` にしかバインドされません。
ブラウザが直接触るのは Next.js(:3000)だけで、APIへの中継は同一マシン内で
完結するため、APIがLANに露出することはありません。

> **別のPCからも使いたい場合(未対応):**
> 本番モード(`npm run build && npm start`)なら `http://<PCのIP>:3000` で
> LAN内の別端末から使えることを確認済み。ただし `./dev.sh` が使う開発モードは
> Next.js 16 のクロスオリジン保護(`allowedDevOrigins`)により別端末からは
> 動かない。対応する場合は `next.config.mjs` に `allowedDevOrigins` の設定が必要。

### 3-4. テスト

```bash
python3 tests/test_line_art_stl.py    # コア
python3 tests/test_api.py             # API
python3 -m pytest tests/ -q           # pytest があればこちらでも可

cd frontend && npm run typecheck && npm run build
```

## 4. GUIの使い方

1. **写真をアップロード** — ドラッグ＆ドロップ、クリックして選択、Ctrl+V での貼り付けに対応。
2. **トリミング** — 枠の比率は右側の「形状」設定(shape / 縦横比)に自動で連動します。
   「顔に合わせる」ボタン、または「顔を自動検出してトリミング」をONにすると、
   OpenCVの顔検出で枠を顔に合わせます(`--auto-face` 相当)。
3. **パラメータ調整** — スライダー/数値入力を動かすたびに、APIから
   PNGプレビューを取り直して表示します(約280msのデバウンス付き)。
   外形サイズ・線の本数・ピッチもリアルタイムに表示されます。
4. **STL出力** — ファイル名と品質を選んで「STLを出力する」。
   Chrome / Edge では保存先を選ぶダイアログが開きます
   (File System Access API 非対応のブラウザでは通常のダウンロード)。

出力品質は線1本あたりのサンプリング数の違いです
(ドラフト260 / 標準420 / 高精細700)。プレビューは常に220で高速に生成します。

## 5. 使い方(CLIリファレンス)

```bash
python3 line_art_stl.py <入力画像> <出力STL> [オプション]
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--shape` | `square` | `square` / `rectangle` / `circle` / `hexagon` |
| `--sides` | なし | 任意のn角形にしたい場合の頂点数(指定すると`--shape`より優先) |
| `--aspect` | `1.0` | square/rectangleのときの 高さ/幅 比率 |
| `--diameter` | `150.0` | デザイン部分のサイズ(mm)。円は直径、四角は幅 |
| `--lines` | `48` | 線の密度の基準となる本数(実際の本数は形状に応じて自動調整) |
| `--angle` | `20.0` | 線の角度(度) |
| `--min-width` | `0.5` | 最小線幅(mm) |
| `--max-width` | `2.9` | 最大線幅(mm) |
| `--thickness` | `2.0` | 線(デザイン部分)の押し出し厚み(mm) |
| `--frame-width` | `8.0` | 外枠の幅(mm) |
| `--frame-thickness` | `2.0` | 外枠の押し出し厚み(mm) |
| `--gamma` | `1.0` | 明暗のコントラスト調整(>1で暗部強調) |
| `--invert` | off | 明暗反転 |
| `--equalize` | off | ヒストグラム均等化 |
| `--crop L T R B` | なし | 相対クロップ範囲 0..1 |
| `--auto-face` | off | 顔検出による自動クロップ(`--crop`指定時はそちらを優先) |
| `--face-margin` | `0.6` | `--auto-face` のときに顔の周囲に取る余白(顔幅に対する比率) |
| `--samples` | `400` | 1本の線あたりのサンプリング数(大きいほど高精細・低速) |
| `--preview` | なし | 2Dプレビューpngの出力パス(任意、確認用) |

実行例:

```bash
python3 line_art_stl.py my_photo.jpg output.stl \
    --shape rectangle --aspect 1.4 --diameter 150 --auto-face --preview preview.png
```

## 6. APIリファレンス

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/api/health` | 死活監視 |
| GET | `/api/config` | 既定値・上限・顔検出の可否 |
| POST | `/api/upload` | 画像アップロード(multipart)。`image_id` を返す |
| GET | `/api/images/{id}` | アップロード済み画像(トリミングUIの表示用) |
| POST | `/api/detect-face` | 顔検出。枠比率に合わせたクロップ範囲を返す |
| POST | `/api/preview` | パラメータからPNGプレビュー(data URL)と寸法情報を返す |
| POST | `/api/stl` | STLを生成して返す |

- アップロード画像は一時ディレクトリに保存され、6時間で自動削除されます
  (`PSA_DATA_DIR` / `PSA_UPLOAD_TTL_SECONDS` で変更可)。
- アップロード上限は25MB、サーバー内部では長辺2400pxに縮小して保持します。
- `image_id` は32桁のhexのみ受け付けるため、パス・トラバーサルはできません。

## 7. サイズについて

手持ちの3Dプリンタの最大造形サイズ **1800mm** を上限としています。

- **1800mm以内であれば、警告もエラーも一切出さずに通します。**
  UIのスライダーは扱いやすさのため400mmまでですが、
  数値入力欄には1800mmまで直接入力できます。
- 枠を含めた外形が1800mmを超えた場合のみ、「分割印刷が必要」という警告を1件出します。
  この場合もSTLの生成自体は行えます。
- 線幅とピッチのバランスに関する警告(下記)は、サイズとは独立して出ます。

## 8. 設計上のポイント・ハマりどころ

- **線幅とピッチのバランスが最重要。** 参考にした解説動画によると、線が細すぎると
  造形が安定せずちぎれる、逆に太すぎて隙間が狭すぎると陰影効果自体が失われる
  (線同士がくっつく)とのこと。
  → `check_line_width_safety()` で警告を出す。デフォルト値(本数48・最小0.5mm・
  最大2.9mm)は、常に隙間がピッチの25%以上残るように調整済み。
- **プレビュー描画は「図形ごとに穴を即座に punch する」。** 最初matplotlibで
  「外形を塗ってから穴を白で塗り直す」実装にしたところ、`zorder` が描画全体で
  共有されるため、枠の穴の白塗りが後から描く線パターンより手前に来て内側が
  真っ白になる不具合があった。PILで逐次処理に書き換えて解決(`render_preview_image`)。
  今後このプレビュー部分を改造する際は、この前提を崩さないよう注意。
- **`showSaveFilePicker` はクリック直後にしか呼べない。** STLの生成を待ってから
  呼ぶとユーザー操作の有効期限が切れてブラウザに拒否される。そのため
  `page.tsx` では「クリック→保存先を訊く→生成→書き込み」の順にしている。
- **レンダー中に `window` を見ない。** 保存先ダイアログの対応可否をレンダー中に
  判定していたところ、SSRの結果と食い違ってハイドレーションが壊れ(React #418)、
  開発モードでページ全体が無反応になった。マウント後に `useEffect` で判定すること。

## 9. このバージョンで直したバグ

| 内容 | 詳細 |
|---|---|
| **`--aspect` 時に線が角まで届かない** | 線の生成範囲を `R*1.3` の固定係数で決めていたため、形状の外接円半径に足りていなかった。`shape_cover_radius()`(四角なら `R*hypot(1, aspect)`)を基準に、本数も線の長さも算出するように変更。修正前は aspect=1.6 で枠の10.9%、aspect=2.5 で42.1%に線が届いていなかった。square でも角(`R*1.414`)には届いていなかったので併せて解消。ピッチの定義(`--lines` の意味)は従来どおりなので、既存の推奨値はそのまま使える。 |
| **`--aspect` 時に画像が引き伸ばされる** | 画像を常に正方形にクロップし、`sample_bilinear` も正方形前提だった。枠と同じ比率でクロップし、x/y別々の範囲(`Rx`/`Ry`)でサンプリングするよう修正。 |
| **`--aspect` 時に枠の幅が不均一になる** | 枠を「基準半径を `frame_width` ぶん大きくした相似形」との差分で作っていたため、aspect=2 では上下の枠が左右の2倍の太さになっていた(正多角形でも辺の中央が角より薄かった)。外側へ一定距離オフセットする方式(`make_frame_ring`)に変更し、どの形状でも幅が均一になった。 |
| **STLが非多様体になる** | 線と枠を別々に押し出して結合していたため、枠の内周で4面が1辺を共有していた(circleで31本)。厚みが同じ場合は2Dの段階で結合してから押し出すよう変更し、watertightになった。厚みが異なる場合は形状として段差があるため従来どおり別々に押し出す。 |
| **依存の不足** | `mapbox-earcut` が無いと `trimesh` の押し出しが動かないのに requirements.txt に入っていなかった。 |

## 10. 今後のTODO

- 参考動画で紹介されていた「プリントベッドサイズを超える大きな作品を複数パネルに
  分割する」テクニックは未実装。1800mm超の警告は出すが、分割は手動。
- プレビューは2Dの塗りつぶし画像のみ。3Dレンダリング(角度をつけた見え方の確認)は未対応。
- 顔検出はHaarカスケード。横顔や小さく写った顔では外すことがある。
  精度が要るなら DNN ベース(`cv2.FaceDetectorYN`)への差し替えを検討。
- APIは認証なしのローカル利用前提。外部に公開する場合は認証とレート制限が必要。

## 11. 素材について

`samples/` の画像はいずれもコード内で生成した合成画像で、実在の人物写真ではない
(`test_face.png` はHaarカスケードが反応する明暗構造を持たせた顔検出テスト用)。
実際に使用した子供の顔写真はこのリポジトリには含めていない
(プライバシーのため各自手元で用意する想定)。
