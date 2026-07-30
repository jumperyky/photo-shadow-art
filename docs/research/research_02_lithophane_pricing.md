# リソフェイン（Lithophane）価格相場・技術仕様リサーチ

**調査目的**: Bambu Lab A1 mini（ビルドサイズ180×180×180mm）1台での個人運営を前提に、赤ちゃん・子供の写真リソフェインの価格戦略と製造ノウハウを検討する。

**為替レート仮定**: 1USD = 155円（本レポート内の円換算はすべてこの仮定レートによる。実勢レートは変動するため参考値）

**調査手法に関する重要な注記**: 本セッションではWebFetchツール（個別URLの本文取得）が環境側の制約で全面的に403エラーとなり、Wikipedia等の一般サイトも含めて直接本文を取得できなかった。そのため以下の情報はすべて **WebSearch（検索エンジンのスニペット・要約）経由** で収集したものである。検索結果のタイトルとURLは実在するページのものだが、価格等の数値はGoogle等の検索スニペットに基づく要約であり、個別ページの本文を直接確認できていない点に留意。数値の裏取りが弱い箇所は「不明」「未確認」と明記した。

---

## 1. 海外（Etsy / eBay等）の価格相場

### 1-1. 形状別・サイズ別 価格マトリクス（USD／円換算）

| 形状 | サイズ目安 | 価格帯 (USD) | 円換算(155円/$) | LED/フレーム込み | 出典 |
|---|---|---|---|---|---|
| フラット単板（照明別・自立なし） | 約100×100mm | €18〜45（≒$19〜47） | 約2,950〜7,300円 | 含まず（ティーライト用） | [3dplotter.xyz](https://3dplotter.xyz/lithophane)（検索要約、ユーロ表記） |
| フラット単板（マルチカラー） | 4×6インチ（約100×150mm） | $35.00 | 約5,425円 | 含まず | [Etsy出品](https://www.etsy.com/listing/4318108692/3d-printed-lithophane-multi-color-custom) |
| フラット単板（マルチカラー） | 5×7インチ（約127×178mm） | $40.00 | 約6,200円 | 含まず | 同上 |
| 写真ランプ（フレーム＋台座＋LED込み） | 4×6インチ | 約$29〜(複数出品あり、正確な単価は個別確認要) | 約4,500円〜 | 含む（木製ベース＋LED電球） | [Personalized 4x6 Photo Lamp](https://www.etsy.com/listing/859380437/personalized-4x6-lithophane-picture-lamp)ほか |
| フレーム型（LEDライトパネル込み、8×10インチ） | 約203×254mm | 不明（価格スニペット未取得） | 不明 | 含む（スリムLEDパネル、厚み約7mm） | [lithophanelights.com](https://lithophanelights.com/product/lithophane-light-panel-8x10/) |
| ランプシェード／行灯型（円筒・曲面） | 中型（高さ目安150〜180mm程度） | $40〜$49 | 約6,200〜7,600円 | 含む場合が多い | [3D Printed Lithophane Lamp Shade](https://www.etsy.com/listing/862436036/3d-printed-lithophane-lamp-shade) |
| ナイトライト一体型（フォトランプ、木製ベース、光センサー付） | 高さ約4"×幅3.5"×奥行1.8"（約100×90×46mm） | 定価$90→セール$54（25%OFF、送料無料）／別購入者は送料込み約$20との報告あり | 約8,370円（$54）／約3,100円（$20） | 含む（LED＋光センサー） | [Etsy市場ページ要約](https://www.etsy.com/market/lithophane_night_light) |
| ハート型／丸型・小型キーホルダー | 約50〜60mm、厚み約3mm | 約$10〜11（MX$182.63からの逆算） | 約1,550〜1,700円 | 含まず（金属リング付） | [Personalized Lithophane Keychain](https://www.etsy.com/listing/4300939162/personalized-lithophane-keychain-with) |
| 参考：インド市場の小型キーホルダー | 50×60mm | ₹250（≒$3程度） | 約460円 | 含まず | [IndiaMart](https://www.indiamart.com/proddetail/lithophane-photo-keychain-3d-printed-21863535133.html)（Etsyではないため参考値） |

**注**: 表中の価格はいずれも検索エンジンのスニペットから抽出したものであり、セール状況・為替・出品者による変動が大きい。個別ページ本文（送料条件、実サイズ、素材詳細等）は今回未確認。

### 1-2. eBayの相場感

- アクティブ出品96件、価格帯 $5〜$515、平均 $66.96（≒10,230円）との検索要約あり。出典: [eBay lithophane検索](https://www.ebay.com/sch/i.html?_nkw=lithophane&_sop=12)
- 実売例: カスタムフォトリソフェイン（TVモチーフ）$45.00（10件販売）／個人化カスタム写真リソフェイン $39.06（3件販売）。出典: 検索スニペット（個別リンクは[こちら](https://www.ebay.com/itm/304401848082)など、本文未確認）
- 古い磁器製アンティークのリソフェイン（19世紀〜20世紀初頭、ドイツ製・アイルランドBelleek製など）は $68〜$168.75 で流通しており、3Dプリント品とは別の骨董品市場が存在する点に注意（コンセプトが混在しやすい）。

### 1-3. 価格設定の考え方（作り手側の議論）

- 3Dプリント・クラフト系フォーラムでは「材料費×3（店舗マージン・配送・利益込み）＋機械稼働時間 $25/時（知人向け）〜$40/時（一般客向け）、1時間未満の案件は一律$50」という目安が語られている。出典: [Vectric Customer Forum](https://forum.vectric.com/viewtopic.php?f=7&t=13741)（検索要約）
- 一方で「リソフェインは労務コストを十分にカバーできる値付けが難しい」という注意喚起もあり（同フォーラム）、印刷時間の長さ（後述、数時間〜半日）に対して薄利になりがちな構造的リスクが指摘されている。

---

## 2. 日本国内での販売価格

国内では「リトフェイン」表記が主流。個人ハンドメイド系（minne, creema）と、法人の記念品・メモリアル系事業者（PKL-Factory, TANPRO, Enfuku等）の二層構造が見られた。

| 提供元 | 商品 | サイズ | 価格 | 備考／出典 |
|---|---|---|---|---|
| minne（purisabijp） | リトフェインライト【正方形】 | 不明（正方形のみ） | **3,900円**（検索要約に基づく） | [minne商品ページ](https://minne.com/items/30999103)（本文未確認、価格は検索スニペットの二次情報） |
| minne | 3Dプリント作品 リトフェインアート（スタンドあり／なし） | 10cm×10cm以下、厚み約2mm | 不明 | [minne商品ページ](https://minne.com/items/4526943) |
| creema（ヒロ工房） | リトフェイン 写真・グラフィック | 不明 | 不明（価格スニペット取得できず） | [creema商品ページ](https://www.creema.jp/item/59095/detail) |
| creema | リトフェインの行灯風ナイトランプ | 不明 | 不明 | [creema商品ページ](https://www.creema.jp/item/225558/detail) |
| ココナラ | リトフェイン用3Dデータ作成代行（印刷物ではなくデータ作成のみ） | ― | 1,000円〜 | [ココナラ](https://coconala.com/services/44390) |
| workshop-enfuku | 3Dリトフェイン「メモリア」（本体＋フレーム＋スタンド＋LED、電池式or100V） | 不明 | 不明 | [Enfuku商品ページ](https://www.workshop-enfuku.com/products/3d-lithophane/) |
| PKL-Factory | 一般リトフェイン（人工大理石・CNC彫刻、3Dプリントではない） | 円形で径40/60/80/100/150/200mm等 | 不明（個別見積） | [PKL-Factory](https://www.pkl-factory.jp/product/lithophane/) |
| PKL-Factory | 大型リトフェイン（記念碑・モニュメント規模、人工大理石） | 大型 | 検索要約では「本体のみ1,000〜1,500万円」という言及あり | [PKL-Factory](https://www.pkl-factory.jp/product/lithophane_large/) ※記念碑・墓石スケールの別セグメント商品であり、本事業（写真ギフト）とは市場が全く異なる点に注意。数値の信憑性も未確認（検索要約のみ）。 |

### 国内 vs 海外の比較（暫定）

- 確度の高い比較ができるデータは乏しいが、唯一具体的な価格が取れたminneの正方形リトフェインライト**3,900円（≒$25.2）**は、海外Etsyの「フレーム＋LED込みナイトライト」帯（$54〜$90、約8,400〜14,000円）よりも**明確に安い**。
- 一方、PKL-FactoryやEnfuku「メモリア」のような法人系メモリアル商品は、3Dプリントではなく人工大理石CNC彫刻等の高付加価値プロセスを採っており、価格帯も全く異なる（記念品・仏事需要向けの高単価帯）。
- **結論（暫定・弱いエビデンス）**: 個人ハンドメイド（minne/creema）の価格帯は海外Etsyの同種商品よりやや安い可能性が高いが、データ点数が少なく確度は低い。日本市場では「リトフェイン」の認知度自体がまだ低く、比較可能な出品数も少ないため、価格相場としての一般化は避けるべきである。むしろ「競合が少ない＝価格弾力性を試す余地がある」市場と解釈する方が実務的に有用。

---

## 3. 技術仕様のベストプラクティス

### 3-1. 厚み（Thickness）

- 一般的なFDM推奨レンジ: **最薄 約0.8mm 〜 最厚 約3.2mm**（薄い部分＝光を最も通す＝画像の最も明るい部分、厚い部分＝光を通しにくい＝最も暗い部分）。出典: 複数の技術ブログの検索要約（[3D Printer Stuff](https://www.3dprinterstuff.com/workshop/lithophane-3d-printing-guide)等）
- 白色フィラメント全般では厚み **2.4mm〜4mm** 程度がよく使われるとの言及もあり（フィラメントの透過性次第で最適値は変動）。
- 小型キーホルダー等では「厚み最大3mm、縁の厚み2mm」という具体的モデル仕様も確認（[MakerWorldモデル要約](https://www.printables.com/model/171165-lithophane-photo-lamp-v2)）。

### 3-2. レイヤー高さ・ノズル径

- 垂直印刷（vertical/on-edge）の場合、**レイヤー高さ0.08〜0.12mm**が実務上の標準。0.12mmで縞模様（バンディング）が消え、0.10mm未満にしても効果は薄く印刷時間だけが伸びるとの報告。0.12mm超だとグラデーション部分に段差が出やすい。
- ノズル径は **0.4mmが標準**。より高精細を狙う場合は **0.2mmノズル＋0.08〜0.12mmレイヤー高さ** の組み合わせも使われる（Bambu Lab公式のCMYKカラーリソフェインガイドでも0.2mmノズル推奨）。出典: [Bambu Lab Wiki（検索要約）](https://wiki.bambulab.com/en/knowledge-sharing/CMYK-color-lithophane-printing-instructions)
- フラット印刷（寝かせて印刷）の場合は、解像度がレイヤー高さではなくノズル径・XY精度に依存するため、垂直印刷より精細さで劣るとされる。

### 3-3. 壁（ウォール）・インフィル設定

- Bambu Studioでは「Wall loopsを99に設定」＝断面全体を同心円壁で埋め尽くす設定が、実務上もっとも効果が大きいテクニックとして紹介されている（検索要約、[itslitho.comブログ](https://itslitho.com/itslitho-blog/slicer-settings-for-lithophanes-tweaking-to-perfection/)）。
- 代替アプローチとして「壁7本以上＋インフィル10〜15%」でも99%/100%インフィルや極厚壁と品質差がなかったとする検証報告もあり（同ブログ）。
- 一般的な目安としては「壁4〜5本以上、またはインフィル99〜100%」で中身を実質ソリッドにするのが基本。

### 3-4. 印刷方向（垂直立て printing vertically の理由）

- **垂直（エッジ立て）印刷が単色・中小サイズのリソフェインで推奨される理由**: 平置き印刷では1層＝画像全体を横切る水平スライスになるため、レイヤー高さのわずかなブレが画像全体を横切る「ブラインド越しのような」縞模様として現れる。垂直印刷では1層＝画像の縦方向の細い1列になるため、同じブレが人間の目には「質感」程度にしか見えず、結果的に格段にきれいに仕上がる。出典: 検索要約（複数ブログ、[itslitho.com](https://itslitho.com/itslitho-blog/slicer-settings-for-lithophanes-tweaking-to-perfection/)、Bambu Labフォーラム関連スレッド）
- ただし垂直印刷は「層と層の間に隙間ができる」問題（Arachneウォールジェネレータでも完全には解決しない）があり、20mm幅のブリムを付けても半分で剥がれて失敗した例も報告されている。
- **カラー（CMYK）印刷や大型リソフェインは平置きが推奨される**傾向: 色は平置きでレイヤーごとに色を変える方式と相性が良く、また大型パネルは平置きの方が「重なりや隙間の問題が出ず、輪郭がはっきりする」との報告がある。
- 実務的な使い分け（検索要約からの整理）: 小〜中型・単色 → 垂直／大型・多色・ランプシェード等の曲面 → 平置き＋Arachneウォールジェネレータ。

### 3-5. 推奨フィラメント

- 白PLAの中でも「半透明（semi-translucent）」「パールホワイト」「リソフェイン専用グレード」と明記された銘柄を選ぶべきで、**酸化チタン（TiO2）含有量が多い「真っ白で不透明」なタイプは光を均一に遮ってしまい、諧調が潰れる**ため不向き、という指摘がある。出典: 検索要約（[thewearify.com](https://thewearify.com/best-filament-for-lithophanes/)ほか）
- 具体的銘柄として **American Filament社の「Classic Lithophane White AF」PLA**（Lithophane Maker監修）が挙げられている。出典: [americanfilament.us商品ページ](https://americanfilament.us/products/lithophane-white-af-pla-1-75mm)（本文未確認、検索結果タイトルのみ）
- カラー（CMYK）リソフェインには **Bambu Lab純正「PLA CMYK Lithophane Bundle」**（シアン・マゼンタ・イエロー・白、各1kg×4巻）が使われる。価格は販売店により差があり、Bambu Lab公式ストアで **$65.99〜$91.96**（定価/セール）、3DJake等の代理店で$40〜$92と幅がある。円換算で約6,200円〜14,250円。出典: [3D Universe](https://shop3duniverse.com/products/bambu-lab-pla-cmyk-lithophane-bundle-1-75mm-1kg-x-4)、[Bambu Lab Asia Store](https://asia.store.bambulab.com/en/products/pla-cmyk-lithophane)ほか（検索要約）

### 3-6. LEDバックライト部材コスト（参考：原価計算用）

- Bambu Lab純正「Lithophane LED Backlight Board Kit」: 3DJake $11.59、Bambu Lab EU公式 €9.31（≒$10、約1,550円）。出典: [3DJake](https://www.3djake.com/bambu-lab/lithophane-led-backlight-board-kit)、[Bambu Lab EU Store](https://eu.store.bambulab.com/nl/products/lithophane-led-backlight-board-kit)

### 3-7. 印刷時間の目安

| サイズ／条件 | 印刷時間 | 出典 |
|---|---|---|
| 144×108mm、厚み4mm、0.4mmノズル、A1系（フィラメント16回交換=マルチカラー想定） | 約6時間 | Bambu Labフォーラム（検索要約） |
| 同等サイズ、0.2mmノズル＋高精細0.10mm設定、プライムタワーなし | 9時間18分 | Bambu Labフォーラム（検索要約） |
| 200×200mm級 | 「中間地点で残り5時間以上」との報告＝総時間10時間超と推定されるが総時間の明言なし | Bambu Labフォーラム（検索要約、**総時間は不明・推定**） |
| 参考：設定最適化（Genericプロファイル改造、0%インフィル＋壁10本以上）による高速化 | 旧世代プリンタ比で1/3の時間に短縮したとの報告あり | Bambu Labフォーラム（検索要約） |

**注記**: A1 mini固有の印刷時間データは検索スニペットからは十分に取得できず、上記は「A1」「Bambu」系フォーラムの一般的報告であり、A1 mini（無印A1やX1と比較して速度・仕様がやや異なる）に限定した数値ではない点に注意。A1 mini単体での100×150mm・150×200mm・200×250mm級の具体的印刷時間は**不明**。

---

## 4. A1 mini（180mm制約）と最大サイズ・多パネル化

- A1 miniのビルドボリュームは **180×180×180mm**（公称）。出典: [Bambu Lab公式スペックページ](https://bambulab.com/en/a1-mini/tech-specs)ほか（検索要約）
- **軸に平行に印刷する場合**: 単純な単板は最大 約180×180mm（ブリム等のマージンを考えると実用上170〜175mm角程度が安全）。垂直（縦置き）印刷であれば高さ方向も180mmまで使えるため、**縦180mm×横180mm程度のパネルが単板としての実用上限**となる。
- **対角線トリック（45度回転）**: ベッドを45度回転させて対角線方向に配置すると、理論上 180×√2 ≈ **254.6mm** までの長さの単板が印刷可能（計算値、出典未確認だが幾何学的に自明）。これにより「200×250mm」クラスのパネルは、短辺180mm以内・長辺254.6mm以内であれば対角配置で単板印刷できる可能性がある（ただし短辺方向の制約は残るため、200×250mmのような長方形をそのまま対角に収めるには追加の検討が必要＝**要実機検証、本調査では未確認**）。
- **多パネル化（タイル分割）**: より大きな画像を複数の小パネルに分割し、フレームや3Dプリント製のコーナーブラケットで組み立てる手法が実例として存在する（YouTube「HUGE Lithophane Grid」等）。出典: 検索要約
- **商品性への影響（考察）**:
  - A1 mini単体では、実務上「はがきサイズ（100×150mm＝4×6インチ）」〜「対角配置を使った150×200mm程度」までが単板での現実的な上限帯と考えられる。200×250mm以上の大型パネルは分割・多パネル化が前提になる。
  - 多パネル化は（a）印刷時間・材料が線形以上に増える、（b）継ぎ目・パネル間の明るさムラが生じるリスクがある、（c）組み立て工数が増える、というデメリットがあり、赤ちゃん・子供向けギフトとして「継ぎ目のない一枚物」を訴求する場合は競争力が落ちる可能性がある。逆に「大型ウォールアート」として訴求する場合はプレミアム価格を正当化する材料にもなり得る。
  - 上記は本調査で収集した情報からの**推論**であり、A1 miniでの200mm超パネルの実機検証データそのものは確認できなかった（不明）。

---

## 5. 品質上の失敗要因と歩留まり

### 5-1. 印刷起因の失敗

- **1層目のシワ・波打ち**: A1系フォーラムで「A1 First layer wrinkling problem」という報告があり、初期層の定着不良がその後の層に波状の歪みとして伝播する例が確認されている。出典: [Bambu Labフォーラム](https://forum.bambulab.com/t/a1-first-layer-wrinkling-problem/135178)（検索要約）
- **垂直印刷時の層間ギャップ**: 垂直（エッジ立て）印刷では層と層の間に微小な隙間ができやすく、Arachneウォールジェネレータを使っても完全には解消しないとの報告。
- **細部が多い画像でのインフィル乱れ**: 複雑な画像（線が多い、コントラストが細かい）では100%インフィルでも「線の隙間や奇妙なパターン」が出ることがあり、FFF（熱溶解積層）方式の解像度限界に起因するとされる。
- **反り（warping）・剥離**: ブリム幅20mmを付けても印刷半ばで剥離した失敗例が報告されている。フィラメントの乾燥不足も失敗要因として挙げられている（「リソフェインは拷問のようなテスト」という表現で、乾燥フィラメントの重要性が強調されている）。
- **曲面（ランプシェード・ナイトライト等）でのブリッジ・たわみ**: 45度を超えるオーバーハングは通常サポートが必要、または印刷速度を落として層を丸めるなどの対処が必要との一般論あり（A1 mini自体の仕様説明からの言及で、リソフェイン特有の検証データではない）。

### 5-2. 写真選定に起因する失敗（歩留まりに直結）

- **コントラスト**: 曇天・フラットな照明・マット加工された写真は低コントラストになりがちで、事前にコントラストを20〜30%程度強調する編集が推奨される。白黒変換や背景除去も有効とされる。
- **顔の向き・構図**: 顔がアップで画面いっぱいに写っている高コントラストのポートレートが最も良い結果になるとされる。広く引いて撮った写真は顔のパーツが小さくなり、ディテールが失われる。
- **背景処理**: シンプルな暗い背景が被写体を際立たせ、可読性を大きく向上させる。
- **避けるべき写真**: ピントがぼけた写真（グラデーションがぼやける）、多人数写真で顔が小さく写っているもの（典型的なリソフェイン解像度では潰れる）。
- 出典: 複数の技術ブログの検索要約（[imprint3d.nz](https://imprint3d.nz/2023/10/15/choosing-your-lithophane-photo/)、[vextrude.com](https://vextrude.com/blog-lithophane-guide)ほか）

### 5-3. 歩留まりに関する定量データ

- 具体的な「歩留まり率（成功率%）」を示す一次データは検索では**発見できず（不明）**。上記はいずれも定性的な失敗要因の指摘にとどまる。赤ちゃん写真ビジネスとして歩留まりを管理するには、上記要因（フィラメント乾燥、1層目の定着、写真のコントラスト事前チェック）を運用フローに組み込む必要がある、という運用上の示唆にとどめる。

---

## 6. Bambu Lab A1 mini 特有の話題

- **AMS lite**: A1 miniは「AMS lite」（4スプロール自動フィラメント供給機構）を搭載し、CMYKカラーリソフェインの自動色替えに対応する。ただし「AMS liteが色を切り替えない」という不具合報告がフォーラムに複数存在し（[AMS lite with A1 Mini not changing colors](https://forum.bambulab.com/t/ams-lite-with-a1-mini-not-changing-colors/163264)）、信頼性は完全ではない模様。
- **AMSなし運用**: AMSを使わない場合でも、特定レイヤーで一時停止（pause）を挟んで手動でフィラメントを差し替えることで、A1 mini単体でも多色リソフェインが印刷可能という手法がフォーラムで共有されている（[Hueforge & Lithophaneスレッド](https://forum.bambulab.com/t/hueforge-lithophane-printing-multiple-colors-a1-mini-without-ams/84900)）。
- **ビルドプレート（テクスチャ vs スムース）**: A1 miniには標準でテクスチャ入りPEIプレートが付属することが多いが、リソフェインのような「底面の質感が仕上がりに直結する平板・低レイヤーモデル」では、スムースプレートの方がZ軸精度が高く、底面が滑らかでマットな仕上がりになるためリソフェインに適しているとの言及がある。出典: 検索要約（[Bambu Lab Wiki: ビルドプレート紹介](https://wiki.bambulab.com/en/filament-acc/acc/plates)ほか）。**ただし「リソフェイン印刷にはスムースプレートが最適」という結論は本調査における推論であり、A1 miniのリソフェイン印刷でテクスチャ/スムースを直接比較検証した一次情報は確認できなかった（推測）**。
- **CMYKカラーリソフェイン公式ガイド**: Bambu Lab公式が「Make My Lithophane」というソフトウェア（単色・カラー両対応、CMYKバンドルに最適化）を提供しており、0.2mmノズル・0.08〜0.12mmレイヤー高さが推奨設定として紹介されている。「Colorful Litho with Fixed Frame」というテンプレートを使い、画像の向き・スケール・回転・色・明るさを調整して3MFを書き出すワークフローが解説されている。出典: [Bambu Lab Wiki（検索要約）](https://wiki.bambulab.com/en/knowledge-sharing/CMYK-color-lithophane-printing-instructions)
- **印刷時間の実例報告**: 前掲のとおり、144×108×4mmクラスで約6時間（0.4mmノズル）〜9時間18分（0.2mmノズル・高精細設定）。A1 mini限定の追加データは今回のリサーチでは十分に確認できなかった（不明）。
- **成功例/失敗例のまとめ**: フォーラムには「平置きにしたら見違えるほど良くなった（UPDATE: Printed them flat and it turned out awesome）」という報告がある一方、「垂直印刷で層間ギャップに悩まされた」という報告も多く、**単色小型は垂直、大型・カラー・曲面は平置き**という使い分けが実務上のコンセンサスに近いと考えられる。

---

## 7. 総括表：価格帯サマリー（USD／円、155円換算）

| セグメント | 価格帯目安 (USD) | 円換算 |
|---|---|---|
| 小型キーホルダー・ハート型 | $10〜$15 | 1,550〜2,325円 |
| フラット単板（フレーム・LEDなし、4x6〜5x7インチ） | $30〜$45 | 4,650〜6,975円 |
| ランプシェード・行灯型（曲面、LED込み） | $40〜$49 | 6,200〜7,600円 |
| ナイトライト一体型（フレーム＋LED＋センサー込み） | $20〜$90（セール込み実勢$50前後が中心） | 3,100〜13,950円（中心8,000円前後） |
| eBay全体平均 | 約$67 | 約10,400円 |
| 日本 minne 正方形リトフェインライト（唯一確認できた具体価格） | ≒$25.2（3,900円） | 3,900円 |

---

## 8. 未確認・不明な事項一覧（正直な棚卸し）

- 日本国内の主要ハンドメイド系（creema, minne）でのリトフェイン価格の大半（具体的な円額）は検索スニペットからは取得できず、**多くが「不明」**。
- Etsyの8×10インチLEDライトパネル製品の具体的価格。
- A1 mini固有（他モデルと分離した）の印刷時間データ。
- A1 miniでの200mm超パネルの実機検証（対角配置での歩留まり等）。
- リソフェイン印刷の定量的な歩留まり率（%）。
- A1 mini付属ビルドプレート（スムース/テクスチャ）でのリソフェイン専用の比較検証データ（本レポートの推奨は推論）。
- PKL-Factory「大型リトフェイン」の1,000〜1,500万円という数値の信憑性（検索要約のみで一次資料未確認、記念碑スケール商品の可能性が高く本事業とは別セグメント）。

---

### 主要出典一覧（URL）

- https://www.etsy.com/market/lithophane_3d_image ほかEtsyマーケットページ群
- https://www.etsy.com/listing/4318108692/3d-printed-lithophane-multi-color-custom
- https://www.etsy.com/listing/859380437/personalized-4x6-lithophane-picture-lamp
- https://lithophanelights.com/product/lithophane-light-panel-8x10/
- https://www.etsy.com/listing/862436036/3d-printed-lithophane-lamp-shade
- https://www.etsy.com/market/lithophane_night_light
- https://www.etsy.com/listing/4300939162/personalized-lithophane-keychain-with
- https://www.indiamart.com/proddetail/lithophane-photo-keychain-3d-printed-21863535133.html
- https://www.ebay.com/sch/i.html?_nkw=lithophane&_sop=12
- https://forum.vectric.com/viewtopic.php?f=7&t=13741
- https://minne.com/items/30999103
- https://minne.com/items/4526943
- https://www.creema.jp/item/59095/detail
- https://www.creema.jp/item/225558/detail
- https://coconala.com/services/44390
- https://www.workshop-enfuku.com/products/3d-lithophane/
- https://www.pkl-factory.jp/product/lithophane/
- https://www.pkl-factory.jp/product/lithophane_large/
- https://www.3dprinterstuff.com/workshop/lithophane-3d-printing-guide
- https://itslitho.com/itslitho-blog/slicer-settings-for-lithophanes-tweaking-to-perfection/
- https://thewearify.com/best-filament-for-lithophanes/
- https://americanfilament.us/products/lithophane-white-af-pla-1-75mm
- https://asia.store.bambulab.com/en/products/pla-cmyk-lithophane
- https://shop3duniverse.com/products/bambu-lab-pla-cmyk-lithophane-bundle-1-75mm-1kg-x-4
- https://www.3djake.com/bambu-lab/lithophane-led-backlight-board-kit
- https://eu.store.bambulab.com/nl/products/lithophane-led-backlight-board-kit
- https://forum.bambulab.com/t/a1-first-layer-wrinkling-problem/135178
- https://forum.bambulab.com/t/printing-lithophanes-flat-or-vertical/84574
- https://forum.bambulab.com/t/ams-lite-with-a1-mini-not-changing-colors/163264
- https://forum.bambulab.com/t/hueforge-lithophane-printing-multiple-colors-a1-mini-without-ams/84900
- https://wiki.bambulab.com/en/knowledge-sharing/CMYK-color-lithophane-printing-instructions
- https://wiki.bambulab.com/en/filament-acc/acc/plates
- https://bambulab.com/en/a1-mini/tech-specs
- https://imprint3d.nz/2023/10/15/choosing-your-lithophane-photo/
- https://vextrude.com/blog-lithophane-guide
