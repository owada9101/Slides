# 2026-10-21 発表メモ

- 発表日：2026-10-21
- タイトル：部分観測環境における意思決定のための履歴表現学習
- 原稿：`slides.qmd`
- 形式：既存のReveal.js／PowerPoint書式を保持
- 対象読者・発表時間：未記入

## 構成

- 部分観測環境における / 意思決定のための履歴表現学習 {.owada-title data-subtitle="B4 大和田晃生" data-date="2026-10-21"}
- 前提知識 {.owada-section}
- 古典的な強化学習 {.owada}
- 部分観測環境における強化学習 {.owada}
- 履歴を用いた状態の推測 {.owada}
- 研究の背景・目的 {.owada-section}
- 履歴の扱い方には注意が必要 {.owada}
- 履歴を扱いやすくしたい {.owada}
- 本題 {.owada-section}
- 履歴から状態を表現する {.owada}
- 予備実験　{.owada}
- 実験結果 {.owada}
- 残った課題 {.owada}
- 予備実験からの仮説 {.owada}
- 出力クエリによる情報の読み出し {.owada}
- 出力クエリによる情報の読み出し {.owada}
- 実験設定 {.owada}
- モデル全体 {.owada}
- 実験結果 {.owada}
- まとめと今後の展望　{.owada}
- 参考文献 {.owada}
- Appendix　{.owada-section}

## 図・アニメーションの指示

原稿内の丸括弧による図の指示はそのまま残しています。
画像は `assets/images/`、HTML図は `assets/html/図名/` に配置します。

## 出力・確認

`uv run scripts/slides.py build 2026-10-21`

移行前のHTML・PowerPointと関連ファイルは `output/archive/2026-10-21/` に保存しています。
移行前HTMLは21枚、現在のQMDは22枚です。新しい出力は現在のQMDから生成します。
