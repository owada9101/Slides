# NICT2026-10-06 発表メモ

- 発表日：2026-10-06
- タイトル：部分観測環境における意思決定のための履歴表現学習
- 原稿：`slides.qmd`
- 形式：既存のReveal.js／PowerPoint書式を保持
- 対象読者・発表時間：未記入

## 構成

- 部分観測環境における / 意思決定のための履歴表現学習 {.owada-title data-subtitle="早稲田大学　　大和田晃生" data-date="2026-10-06"}
- 研究の背景・目的 {.owada-section}
- 強化学習が扱ってきた意思決定 {.owada}
- 強化学習の基本　{.owada}
- 状態の把握は難しい {.owada}
- 履歴を参照することで状態を推測 {.owada}
- 履歴の扱い方に注意が必要 {.owada}
- 研究目的 {.owada}
- 関連研究 {.owada-section}
- 履歴から状態を表現する {.owada}
- 細かすぎる履歴を圧縮　{.owada}
- 状態だけをまとめると行動選択が衝突する　{.owada}
- 状態と行動を同時に抽象化する {.owada}
- 従来手法での抽象化 {.owada}
- 本題 {.owada-section}
- 研究目標　{.owada}
- そのために目指す抽象化　{.owada}
- 実験設定 {.owada}
- モデル全体 {.owada}
- モデル比較 {.owada}
- モデル比較 {.owada}
- 実験結果　 {.owada}
- 実験結果　 {.owada}
- 実験結果　 {.owada}
- まとめと今後の展望　{.owada}
- 参考文献 {.owada}

## 図・アニメーションの指示

原稿内の丸括弧による図の指示はそのまま残しています。
画像は `assets/images/`、HTML図は `assets/html/図名/` に配置します。

## 出力・確認

`uv run scripts/slides.py build NICT2026-10-06`

移行前のHTML・PowerPointと関連ファイルは `output/archive/NICT2026-10-06/` に保存しています。
