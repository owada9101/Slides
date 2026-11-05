# Research Slides

既存・新規のスライドを、**1つの発表を1つのフォルダにまとめて**管理します。
先輩の [quarto-html](https://github.com/murata-lab/quarto-html) の生成・配布の仕組みを参考に、画像とHTML図も発表フォルダの中に置きます。

## 最初の準備

Quarto CLI・uv・Node.jsが必要です。この `Slides` フォルダで実行します。

```sh
uv sync
uv run playwright install chromium
```

## 新しい発表を作る

```sh
uv run scripts/slides.py new {スライドのファイル名}
```

以下が一度に作られます。同じ名前がある場合は上書きしません。

```text
decks/
└── {スライドのファイル名}/
    ├── memo.md             # 文章で自由に書く発表の下書き
    ├── slides.qmd          # 実際のスライド原稿
    ├── assets/
    │   ├── images/         # PNG、SVG、動画、元データなど
    │   └── html/           # HTML図・アニメーション（図ごとにフォルダ）
    ├── styles/slides.css   # この発表だけの見た目
    └── reference.bib       # 引用文献
```

名前は日本語・英数字・ハイフン・アンダースコアを使用できます。空白や `/` は使いません。
タイトルも設定する場合は `new 名前 --title "発表タイトル"`。
既存の発表から作る場合は `new 新しい名前 --from 元の名前`。メモ・画像・HTML図もコピーされます。

新規作成の標準書式は、これまで使っていた大和田の書式です。
白背景・黒文字・16:9、中央の表紙タイトル、左上の本文見出し、右上のページ番号を使います。
本文の右16px移動も反映します。共通HTMLテーマは `shared/revealjs/default.scss`、
PowerPointテンプレートは `shared/pptx/owada-reference.pptx` です。

## 発表の下書きを書く

`memo.md` は、発表で話したい内容を文章で自由に書く場所です。
新規作成時は `# 発表の下書き` の下から本文を書き始められます。
末尾の `## 疑問・メモ` 欄には、疑問や気づき、相談で決めたことなどを自由に残します。
この欄の `### TODO: ここに相談・依頼したい内容を書く` を依頼内容に書き換えると、
VS CodeのCodex拡張が行の上に表示する「Implement with Codex」から送れます。`TODO:` は残してください。
表示されない場合は、エディター設定の `chatgpt.commentCodeLensEnabled` と `editor.codeLens` を有効にします。
基本情報の記入欄や定型の「全体の流れ」、ページごとの指定欄はありません。
最初からスライド単位に分ける必要はなく、必要に応じて見出しや図のメモを加えられます。

スライド化するときに、下書きの内容と流れをもとに `slides.qmd` へページ分けとレイアウトを反映します。
そのまま使いたい文章や図の指定がある場合は、下書き中に書き添えます。

## 文章の下に図を入れる

図が必要な箇所には、`memo.md` の本文に続けて図の意図を書き添えます。
アニメーションにしたい場合は、初期状態・各操作での変化・最終状態も必要に応じて書きます。
`slides.qmd` では `##` が1枚のスライドです。ページの役割をクラスで指定します。

```markdown
## 発表タイトル {.owada-title data-subtitle="発表者名" data-date="日付"}
## 背景 {.owada-section}
## この発表の問い {.owada}
```

本文ページは `{.owada}`、章の区切りは `{.owada-section}` です。

先行研究などの文献をタイトル右側に表示する場合は、見出しの下に
`title-refs` 欄を置きます。小さな薄いグレー文字で表示され、本文の開始位置は変わりません。
文献ごとに空行で区切り、リンクを付けたい場合は通常のMarkdownリンクを使えます。
この欄があるスライドだけ、タイトル幅を狭めて文献欄の場所を確保します。
HTML・PDF・PowerPointに対応しています。

```markdown
## 履歴から状態を表現する {.owada}

::: {.title-refs}
[1] 著者名, 年, 論文名

[2] 著者名, 年, 論文名
:::

ここにスライド本文を書く。
```

画像なら、ファイルを `assets/images/` に置いて次のように書きます。
`![](画像のパス)` のように `[]` を空にすると、画像の下に説明文を付けずに貼れます。

```markdown
## 履歴を使った状態の推測 {.owada}

過去の観測を参照することで、現在の状態を区別する。

![](assets/images/history.png)
```

画像だけを置く場合は、本文を書かずに画像の行だけを置きます。
説明文を付けたい場合だけ `![説明文](画像のパス)` と書きます。

画像はスライドの横方向の中央に揃います。複数枚を続けて書くと、
画像の間に余白を取り、幅に収まるよう縮小して横に並べ、全体を中央に揃えます。
空行を挟んでも同じまとまりになります。本文や見出しを挟むと別のまとまりになります。
HTML・PDF・PowerPointに同じ画像配置を反映します。

```markdown
![](assets/images/history.png)
![](assets/images/result.png)
```

HTML図の雛形は次のコマンドで作れます。

```sh
uv run scripts/slides.py animation 2026-11-01-seminar history
```

`assets/html/history/index.html` が作られます。表示されたiframe行を、QMDの文章の下に貼ります。

```html
<iframe src="assets/html/history/index.html" title="履歴から状態を区別する図"></iframe>
```

図のHTMLはCSS・JavaScriptを別ファイルに分けても構いません。共通の `shared/frame.js` を読み込み、
`registerAnimation({steps: 2, render(step) { /* step 0, 1, 2 の描画 */ }})` で段階を指定します。
`render(step)` は途中へのジャンプ・巻き戻しにも対応させます。タイマーによる自動進行は使いません。
静止HTML図はこのAPIがなくても表示できます。
このstep APIは `example` の専用プレイヤー向けです。
標準のReveal.js書式で段階表示を使う場合は、図の操作とReveal.jsを連動させる実装を追加します。

AIへの依頼例：

> `decks/2026-11-01-seminar/memo.md` をもとにスライドを作って。
> 下書きの内容と流れに沿ってページを分け、指定文章はそのまま使って。
> 図のメモがある箇所は、文章の下に図・アニメーションをHTMLで入れて。

## HTML・PDF・PowerPointを出力する

```sh
uv run scripts/slides.py build 2026-11-01-seminar
```

```text
output/
└── 2026-11-01-seminar/
    ├── 2026-11-01-seminar.html
    ├── 2026-11-01-seminar.pdf
    ├── 2026-11-01-seminar.pptx
    ├── 2026-11-01-seminar_files/
    ├── assets/
    └── styles/
```

標準書式はReveal.jsで出力します。HTMLを渡すときは発表名フォルダ全体を渡してください。
PDF・PowerPointは単体で渡せます。編集するのは `decks/` 内の原稿・アセットです。
生成中間物と確認画像は `.build/名前/revealjs/` に保存します。

- ←→、スペース：ページを進める／戻す（Reveal.js標準操作）
- Escape：スライド一覧
- F：全画面

既存の出力だけを再検査する場合は `uv run scripts/slides.py check 名前`。
build時にもブラウザエラー・外部通信・ページ数を検査します。

標準書式の動作例は `decks/2026-11-11-seminar/` と `output/2026-11-11-seminar/` です。
`decks/example/` は先輩の専用プレイヤー方式を確認するサンプルとして残しています。
このサンプルの方式では `#` が章、`##` が1枚で、HTMLは単体で閲覧できます。

## ファイルの役割

| 場所 | 用途 |
|---|---|
| `decks/` | 発表ごとの編集元 |
| `references/` | 自分で見返すための参考スライドの保管場所 |
| `templates/deck/` | newコマンドの雛形 |
| `shared/` | 全発表で共通の表示・操作・引用スタイル |
| `scripts/slides.py` | 新規作成・図の追加・ビルド・検査 |
| `output/` | 配布するHTML・PDF |
| `.build/` | ビルド中間物・検査画像（Git対象外） |
| `shared/revealjs/`・`shared/pptx/` | 既存資料の共通テーマとPowerPoint設定 |
| `output/archive/` | 移行前の出力と関連ファイル |

ローカルの画像・CSS・通常のJavaScript・静的なES moduleのimportを利用してください。
外部CDN、動的fetch、CSSの `@import`、`srcset` はこの内包処理では扱いません。
標準書式の数式はMathML、専用プレイヤーのサンプルは `plain` 設定です。
引用は `reference.bib` と `[@key]` を使用し、末尾に `## 参考文献 {#references}` を置きます。

## 既存資料の移行

既存資料も新規資料と同じく、発表ごとのフォルダへまとめました。
文章と図の指示を保ち、共通設定へのパスを更新しています。

```text
decks/
├── 2026-10-21/
│   ├── memo.md
│   ├── slides.qmd
│   ├── assets/
│   │   ├── images/       # 実験画像2枚、旧出力にあったQ-learning.png
│   │   └── html/
│   ├── styles/slides.css
│   └── reference.bib
├── NICT2026-10-06/       # 同じ構成（画像はまだ未登録）
└── example/             # 新方式の動作例
```

| 移行前 | 移行後 |
|---|---|
| `2026-10-21.qmd` | `decks/2026-10-21/slides.qmd` |
| `NICT2026-10-06.qmd` | `decks/NICT2026-10-06/slides.qmd` |
| `assets/2026-10-21/` | `decks/2026-10-21/assets/images/` |
| `default.scss` | `shared/revealjs/default.scss` |
| `owada-reference.pptx`・`pptx-style.lua` | `shared/pptx/` |
| `tools/` | `scripts/` |
| `slides/発表名/` | `output/archive/発表名/` |

### 既存資料の出力

新規資料と同じ入口を使います。QMD内のReveal.js設定を判別し、従来の書式で出力します。
Node.jsも必要です。

```sh
uv run scripts/slides.py build 2026-10-21
uv run scripts/slides.py build NICT2026-10-06
```

```text
output/
├── 2026-10-21/
│   ├── 2026-10-21.html
│   ├── 2026-10-21.pdf
│   ├── 2026-10-21.pptx
│   ├── 2026-10-21_files/
│   ├── assets/
│   └── styles/
├── NICT2026-10-06/       # 同じ構成
├── example/             # 新方式も発表ごとにまとめる
│   ├── example.html     # HTML自体は単体で閲覧可能
│   └── example.pdf
└── archive/             # 移行前の出力をそのまま保存
```

既存資料の手書き機能（Chalkboard）はQuartoの単一HTML出力に対応しないため、
HTMLを渡すときは `output/発表名/` 全体を渡してください。PDF・PPTXは単体で渡せます。
数式は外部CDNに依存しないMathMLで出力します。
HTMLアニメーションのstep操作は `example` の専用プレイヤー向けです。標準書式はReveal.js操作を使います。

`check 発表名` も両形式に対応しています。既存資料の確認画像は
`.build/発表名/revealjs/` に保存されます。
PowerPointは毎回共通テンプレートを再生成し、本文段落を編集可能なテキストボックスに分けます。
元のQMDフォルダに中間物を作らず、`.build/` 内で処理します。

従来のTypeScript入口を使う場合：

```sh
quarto run scripts/render-slides.ts decks/2026-10-21/slides.qmd
```

共通PowerPointテンプレートだけを作り直す場合：

```sh
node scripts/build-pptx-reference.mjs
```

10月21日資料は、移行前HTMLが21枚、現在のQMDが22枚です。
`output/2026-10-21/` は現在の原稿から生成し、以前の状態は `output/archive/2026-10-21/` に残しています。
原稿中の未作成の図・実験結果欄はそのままです。

生成・検査スクリプトと `shared/` のプレイヤーは、先輩のquarto-htmlの実装を元にしています。
参考用のローカルコピーは削除済みです。制作・ビルドには不要です。
参考元：<https://github.com/murata-lab/quarto-html>
