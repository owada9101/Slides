import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

/**
 * QuartoのPowerPoint出力で使用する参照テンプレートを生成するスクリプト。
 * 変更後は uv run scripts/slides.py build <資料名> で反映できる。
 * quarto render を直接使う場合は、先にこのスクリプトを node で実行する。
 * HTMLプレビューの位置は default.scss 側で設定する。
 *
 * このファイルで設定しているもの:
 * - 通常スライドのタイトル位置・サイズ・書体
 * - 本文領域の位置・大きさ・文字サイズ・行間・段落間隔・書体
 * - PowerPoint全体のテーマフォント
 *
 * このファイルで設定していないもの:
 * - 表紙中央のタイトル・発表者名・日付
 * - 区切りスライドの大きな見出し
 * - 右上のページ番号
 *
 * 上記3項目は pptx-style.lua がスライド背景として生成している。
 *
 * PowerPoint XMLの主な単位:
 * - 座標・幅・高さ: EMU（1 inch = 914400 EMU）
 * - 文字サイズ: 1/100 pt（例: sz="1200" は12pt）
 */

// 最終的に生成する、Quartoの reference-doc 用PowerPointテンプレート。
const projectDir = path.resolve(import.meta.dirname, "..");
const outputPath = path.join(projectDir, "shared", "pptx", "owada-reference.pptx");

// 作業用ディレクトリ。既定テンプレートを展開・編集した後に削除する。
const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "owada-pptx-reference-"));
const sourcePath = path.join(tempDir, "reference.pptx");
const unpackedDir = path.join(tempDir, "unpacked");

function run(command, args, options = {}) {
  execFileSync(command, args, { stdio: "inherit", ...options });
}

// -----------------------------------------------------------------------------
// 本文領域の位置・大きさ
// -----------------------------------------------------------------------------
function replaceBodyPlaceholder(masterXml) {
  // スライドマスター内の「本文」プレースホルダーを探す。
  const shapePattern = /<p:sp>(?:(?!<p:sp>)[\s\S])*?<p:ph type="body" idx="1"\s*\/>[\s\S]*?<\/p:sp>/;
  const match = masterXml.match(shapePattern);
  if (!match) throw new Error("Body placeholder was not found in slideMaster1.xml");

  let shape = match[0];

  // 本文テキストボックスの配置。
  // a:off = 左上位置（x: 左から、y: 上から）
  // a:ext = テキストボックスの大きさ（cx: 幅、cy: 高さ）
  // 本文を右へ16px相当（101600 EMU）移動。本文幅・上下位置は維持する。
  shape = shape.replace(
    /<a:xfrm>[\s\S]*?<\/a:xfrm>/,
    `<a:xfrm>
            <a:off x="635000" y="1056000"/>
            <a:ext cx="8077200" cy="4064000"/>
          </a:xfrm>`,
  );

  // 本文テキストボックスの内部余白と縦方向の配置。
  // lIns/tIns/rIns/bIns="0" = 内側の余白なし。
  // anchor="t" = 本文をテキストボックス上端から配置する。
  shape = shape.replace(
    /<a:bodyPr[^>]*>/,
    `<a:bodyPr vert="horz" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0" anchor="t">`,
  );
  return masterXml.replace(shapePattern, shape);
}

// -----------------------------------------------------------------------------
// 通常スライドのタイトル領域の位置・大きさ
// -----------------------------------------------------------------------------
function replaceTitlePlaceholder(masterXml) {
  // スライドマスター内の「タイトル」プレースホルダーを探す。
  const shapePattern = /<p:sp>(?:(?!<p:sp>)[\s\S])*?<p:ph type="title"\s*\/>[\s\S]*?<\/p:sp>/;
  const match = masterXml.match(shapePattern);
  if (!match) throw new Error("Title placeholder was not found in slideMaster1.xml");

  let shape = match[0];

  // 通常スライドのタイトルテキストボックスの配置。
  // a:off = 左上位置、a:ext = 幅と高さ。
  // 表紙タイトルの位置ではない点に注意。表紙は pptx-style.lua 側で設定する。
  shape = shape.replace(
    /<a:xfrm>[\s\S]*?<\/a:xfrm>/,
    `<a:xfrm>
            <a:off x="433400" y="354000"/>
            <a:ext cx="8077200" cy="457200"/>
          </a:xfrm>`,
  );

  // タイトル枠の内部余白を0にし、文字を枠内で上下中央に置く。
  shape = shape.replace(
    /<a:bodyPr[^>]*>/,
    `<a:bodyPr vert="horz" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0" anchor="ctr">`,
  );
  return masterXml.replace(shapePattern, shape);
}

// -----------------------------------------------------------------------------
// 本文の文字スタイル
// -----------------------------------------------------------------------------
function bodyStyleXml() {
  // PowerPointには箇条書きレベル1〜9があるため、全レベルに同じ本文設定を適用する。
  const levels = Array.from({ length: 9 }, (_, index) => {
    const level = index + 1;

    // 本文設定の対応関係:
    // - marL="0" / indent="0": 箇条書きによる左インデントをなくす
    // - algn="l": 左揃え
    // - spcPct val="110000": 行間110%
    // - spcPts val="800": 段落後の間隔8pt
    // - buNone: 本文段落に既定の箇条書き記号を付けない
    // - defRPr sz="1650": 本文の文字サイズ16.5pt
    // - 色は固定せず、PowerPointテーマの本文色を継承する
    // - latin/ea/cs typeface: 本文の書体を Noto Sans JP にする
    return `      <a:lvl${level}pPr marL="0" indent="0" algn="l" defTabSz="342900" rtl="0" eaLnBrk="1" latinLnBrk="0" hangingPunct="1">
        <a:lnSpc><a:spcPct val="110000"/></a:lnSpc>
        <a:spcAft><a:spcPts val="800"/></a:spcAft>
        <a:buNone/>
        <a:defRPr sz="1650" kern="1200">
          <a:latin typeface="Noto Sans JP"/>
          <a:ea typeface="Noto Sans JP"/>
          <a:cs typeface="Noto Sans JP"/>
        </a:defRPr>
      </a:lvl${level}pPr>`;
  }).join("\n");
  return `    <p:bodyStyle>\n${levels}\n    </p:bodyStyle>`;
}

// -----------------------------------------------------------------------------
// スライドマスターへ、タイトル・本文の設定をまとめて適用
// -----------------------------------------------------------------------------
function patchMaster(masterXml) {
  let result = replaceTitlePlaceholder(masterXml);
  result = replaceBodyPlaceholder(result);

  // 通常スライドのタイトル文字スタイル。
  // - algn="l": 左揃え
  // - buNone: 箇条書き記号なし
  // - sz="3000": 30pt（長めの日本語見出しも1行に収めやすい）
  // - b="1": 太字
  // - 色は固定せず、PowerPointテーマの見出し色を継承する
  // - typeface="Yu Gothic": 游ゴシック
  result = result.replace(
    /<p:titleStyle>[\s\S]*?<\/p:titleStyle>/,
    `<p:titleStyle>
      <a:lvl1pPr algn="l" defTabSz="342900" rtl="0" eaLnBrk="1" latinLnBrk="0" hangingPunct="1">
        <a:buNone/>
        <a:defRPr sz="2200" b="1" kern="1200">
          <a:latin typeface="Yu Gothic"/>
          <a:ea typeface="Yu Gothic"/>
          <a:cs typeface="Yu Gothic"/>
        </a:defRPr>
      </a:lvl1pPr>
    </p:titleStyle>`,
  );

  // 上の bodyStyleXml() で作った本文スタイルへ置換する。
  result = result.replace(/<p:bodyStyle>[\s\S]*?<\/p:bodyStyle>/, bodyStyleXml().trim());
  if (result === masterXml) throw new Error("Slide master was not modified");
  return result;
}

// -----------------------------------------------------------------------------
// PowerPoint全体のテーマフォント
// -----------------------------------------------------------------------------
function patchTheme(themeXml) {
  // latin = 英数字、ea = 東アジア文字、cs = 複雑文字、Jpan = 日本語。
  // majorFont = 見出し用、minorFont = 本文用。
  // 本文をNoto Sans JPにする設定を、後処理ではなくPPTXテーマへ組み込む。
  const replaceFontGroup = (groupXml, typeface) => groupXml
    .replace(/<a:latin typeface="[^"]*"\/>/, `<a:latin typeface="${typeface}"/>`)
    .replace(/<a:ea typeface="[^"]*"\/>/, `<a:ea typeface="${typeface}"/>`)
    .replace(/<a:cs typeface="[^"]*"\/>/, `<a:cs typeface="${typeface}"/>`)
    .replace(/<a:font script="Jpan" typeface="[^"]*"\/>/, `<a:font script="Jpan" typeface="${typeface}"/>`);

  return themeXml
    .replace(/<a:majorFont>[\s\S]*?<\/a:majorFont>/, (group) => replaceFontGroup(group, "Yu Gothic"))
    .replace(/<a:minorFont>[\s\S]*?<\/a:minorFont>/, (group) => replaceFontGroup(group, "Noto Sans JP"));
}

try {
  // Quarto/Pandocが持つ標準のPowerPoint参照テンプレートを取得する。
  run("quarto", ["pandoc", "-o", sourcePath, "--print-default-data-file", "reference.pptx"]);

  // PPTXはZIP形式なので、一度展開して中のXMLを編集する。
  fs.mkdirSync(unpackedDir);
  run("unzip", ["-q", sourcePath, "-d", unpackedDir]);

  // slideMaster1.xml = タイトル・本文の領域と文字スタイル。
  // theme1.xml = PowerPoint全体のテーマフォント。
  const masterPath = path.join(unpackedDir, "ppt/slideMasters/slideMaster1.xml");
  const themePath = path.join(unpackedDir, "ppt/theme/theme1.xml");
  fs.writeFileSync(masterPath, patchMaster(fs.readFileSync(masterPath, "utf8")));
  fs.writeFileSync(themePath, patchTheme(fs.readFileSync(themePath, "utf8")));

  // 編集したXML一式を再度ZIP化し、参照テンプレートとして保存する。
  fs.rmSync(outputPath, { force: true });
  run("zip", ["-q", "-r", outputPath, "."], { cwd: unpackedDir });
  console.log(`Created ${outputPath}`);
} finally {
  // 成否にかかわらず作業用ディレクトリを削除する。
  fs.rmSync(tempDir, { recursive: true, force: true });
}
