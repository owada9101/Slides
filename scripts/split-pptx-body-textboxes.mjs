import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// 空行で区切られた本文テキストボックス同士の間隔。
// 1pt = 12700 EMU。PowerPoint上で個別に移動・編集できる図形へ変換する。
const TEXT_BOX_GAP_PT = 13;
const TEXT_BOX_MARKER = "OWADA_PPTX_TEXT_BOX_START_7E3F";
const EMU_PER_PT = 12700;

function run(command, args, options = {}) {
  execFileSync(command, args, { stdio: "inherit", ...options });
}

function shapeBlocks(xml) {
  return xml.match(/<p:sp>(?:(?!<p:sp>)[\s\S])*?<\/p:sp>/g) ?? [];
}

function bodyMasterShape(masterXml) {
  const shape = shapeBlocks(masterXml).find((candidate) =>
    /<p:ph\b[^>]*\btype="body"[^>]*\/>/.test(candidate),
  );
  if (!shape) throw new Error("Body placeholder was not found in slideMaster1.xml");
  return shape;
}

function attribute(xml, element, name) {
  const tag = xml.match(new RegExp(`<${element}\\b[^>]*>`))?.[0];
  const value = tag?.match(new RegExp(`\\b${name}="([^"]+)"`))?.[1];
  if (value === undefined) throw new Error(`${element}.${name} was not found`);
  return Number(value);
}

function masterSettings(masterXml) {
  const bodyShape = bodyMasterShape(masterXml);
  const xfrm = bodyShape.match(/<a:xfrm>[\s\S]*?<\/a:xfrm>/)?.[0];
  const bodyPr = bodyShape.match(/<a:bodyPr\b[^>]*>[\s\S]*?<\/a:bodyPr>/)?.[0]
    ?? bodyShape.match(/<a:bodyPr\b[^>]*\/>/)?.[0];
  const bodyStyle = masterXml.match(/<p:bodyStyle>([\s\S]*?)<\/p:bodyStyle>/)?.[1];
  if (!xfrm || !bodyPr || !bodyStyle) {
    throw new Error("Body geometry or text style was not found in slideMaster1.xml");
  }

  // 箱同士の距離で段落間隔を管理するため、分割後の箱内では段落後を0ptにする。
  const splitBodyStyle = bodyStyle.replace(
    /<a:spcAft>[\s\S]*?<\/a:spcAft>/g,
    '<a:spcAft><a:spcPts val="0"/></a:spcAft>',
  );
  const firstLevel = splitBodyStyle.match(/<a:lvl1pPr\b[\s\S]*?<\/a:lvl1pPr>/)?.[0] ?? "";
  const fontSizePt = Number(firstLevel.match(/<a:defRPr\b[^>]*\bsz="(\d+)"/)?.[1] ?? 1650) / 100;
  const lineSpacing = Number(firstLevel.match(/<a:spcPct\b[^>]*\bval="(\d+)"/)?.[1] ?? 110000) / 100000;

  return {
    x: attribute(xfrm, "a:off", "x"),
    y: attribute(xfrm, "a:off", "y"),
    width: attribute(xfrm, "a:ext", "cx"),
    height: attribute(xfrm, "a:ext", "cy"),
    bodyPr,
    listStyle: `<a:lstStyle>${splitBodyStyle}</a:lstStyle>`,
    fontSizePt,
    lineSpacing,
  };
}

function removeMarker(paragraphXml) {
  const exactMarkerRun = new RegExp(
    `<a:r>(?:(?!<a:r>)[\\s\\S])*?<a:t>${TEXT_BOX_MARKER}<\\/a:t>[\\s\\S]*?<\\/a:r>`,
    "g",
  );
  return paragraphXml.replace(exactMarkerRun, "").replaceAll(TEXT_BOX_MARKER, "");
}

function paragraphGroups(shapeXml) {
  const paragraphs = shapeXml.match(/<a:p(?:\s[^>]*)?>[\s\S]*?<\/a:p>/g) ?? [];
  if (paragraphs.filter((paragraph) => paragraph.includes(TEXT_BOX_MARKER)).length < 2) {
    return [];
  }

  const groups = [];
  let current = [];
  for (const paragraph of paragraphs) {
    const startsTextBox = paragraph.includes(TEXT_BOX_MARKER);
    if (startsTextBox && current.length > 0) {
      groups.push(current);
      current = [];
    }
    current.push(removeMarker(paragraph));
  }
  if (current.length > 0) groups.push(current);
  return groups;
}

function decodedText(xml) {
  return xml
    .replace(/<[^>]+>/g, "")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&apos;", "'")
    .replaceAll("&amp;", "&");
}

function displayUnits(text) {
  let units = 0;
  for (const character of Array.from(text)) {
    if (/\s/u.test(character)) units += 0.35;
    else if (character.codePointAt(0) <= 0x7f) units += 0.55;
    else units += 1;
  }
  return units;
}

function estimatedLines(group, settings) {
  const widthPt = settings.width / EMU_PER_PT;
  const charactersPerLine = Math.max(1, widthPt / settings.fontSizePt);
  return group.reduce((total, paragraph) => {
    const units = displayUnits(decodedText(paragraph));
    return total + Math.max(1, Math.ceil(units / charactersPerLine));
  }, 0);
}

function replaceTextBody(shapeXml, paragraphs, settings) {
  let result = shapeXml
    .replace(/<p:nvPr>[\s\S]*?<\/p:nvPr>/, "<p:nvPr/>")
    .replace(/<p:cNvSpPr(?:\s[^>]*)?>/, '<p:cNvSpPr txBox="1">')
    .replace(/<a:bodyPr\b[^>]*>[\s\S]*?<\/a:bodyPr>|<a:bodyPr\b[^>]*\/>/, settings.bodyPr)
    .replace(/<a:lstStyle>[\s\S]*?<\/a:lstStyle>|<a:lstStyle\s*\/>/, settings.listStyle);

  const paragraphRegion = /<a:p(?:\s[^>]*)?>[\s\S]*<\/a:p>/;
  if (!paragraphRegion.test(result)) throw new Error("Paragraph region was not found in body shape");
  result = result.replace(paragraphRegion, paragraphs.join(""));
  return result;
}

function positionedShape(shapeXml, paragraphs, geometry, settings, id, index) {
  const spPr = `<p:spPr>
<a:xfrm>
<a:off x="${geometry.x}" y="${geometry.y}"/>
<a:ext cx="${geometry.width}" cy="${geometry.height}"/>
</a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
<a:noFill/>
<a:ln><a:noFill/></a:ln>
</p:spPr>`;

  return replaceTextBody(shapeXml, paragraphs, settings)
    .replace(/<p:cNvPr\b[^>]*>/, (tag) => tag
      .replace(/\bid="\d+"/, `id="${id}"`)
      .replace(/\bname="[^"]*"/, `name="Body Text Box ${index + 1}"`))
    .replace(/<p:spPr>[\s\S]*?<\/p:spPr>|<p:spPr\s*\/>/, spPr);
}

function splitSlideBodyTextBoxes(slideXml, settings) {
  const bodyShape = shapeBlocks(slideXml).find((shape) => shape.includes(TEXT_BOX_MARKER));
  if (!bodyShape) return { xml: slideXml, count: 0 };

  const groups = paragraphGroups(bodyShape);
  if (groups.length < 2) {
    return { xml: slideXml.replaceAll(TEXT_BOX_MARKER, ""), count: 0 };
  }

  const maxId = Math.max(
    1,
    ...Array.from(slideXml.matchAll(/<p:cNvPr\b[^>]*\bid="(\d+)"/g), (match) => Number(match[1])),
  );
  const gap = Math.round(TEXT_BOX_GAP_PT * EMU_PER_PT);
  const availableHeight = settings.height - gap * (groups.length - 1);
  if (availableHeight <= 0) throw new Error("Text box gaps exceed the body placeholder height");

  const lineCounts = groups.map((group) => estimatedLines(group, settings));
  const naturalLineHeight = settings.fontSizePt * settings.lineSpacing * EMU_PER_PT;
  const naturalHeights = lineCounts.map((count) => Math.ceil(count * naturalLineHeight));
  const naturalTotal = naturalHeights.reduce((sum, height) => sum + height, 0);
  const scale = naturalTotal > availableHeight ? availableHeight / naturalTotal : 1;

  let y = settings.y;
  const shapes = groups.map((group, index) => {
    const isLast = index === groups.length - 1;
    const height = isLast
      ? Math.min(Math.round(naturalHeights[index] * scale), settings.y + settings.height - y)
      : Math.round(naturalHeights[index] * scale);
    const xml = positionedShape(
      bodyShape,
      group,
      { x: settings.x, y, width: settings.width, height },
      settings,
      maxId + index + 1,
      index,
    );
    y += height + gap;
    return xml;
  });

  return { xml: slideXml.replace(bodyShape, shapes.join("")), count: groups.length };
}

function processPresentation(pptxPath) {
  const absolutePath = path.resolve(pptxPath);
  if (!fs.existsSync(absolutePath)) throw new Error(`PPTX was not found: ${absolutePath}`);

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "owada-pptx-textboxes-"));
  const unpackedDir = path.join(tempDir, "unpacked");
  const stagedPath = path.join(path.dirname(absolutePath), `.${path.basename(absolutePath)}.${process.pid}.tmp`);
  let splitSlides = 0;
  let createdTextBoxes = 0;

  try {
    fs.mkdirSync(unpackedDir);
    run("unzip", ["-q", absolutePath, "-d", unpackedDir]);
    const masterXml = fs.readFileSync(
      path.join(unpackedDir, "ppt/slideMasters/slideMaster1.xml"),
      "utf8",
    );
    const settings = masterSettings(masterXml);
    const slidesDir = path.join(unpackedDir, "ppt/slides");
    const slideFiles = fs.readdirSync(slidesDir)
      .filter((filename) => /^slide\d+\.xml$/.test(filename))
      .sort((left, right) => Number(left.match(/\d+/)[0]) - Number(right.match(/\d+/)[0]));

    for (const filename of slideFiles) {
      const slidePath = path.join(slidesDir, filename);
      const source = fs.readFileSync(slidePath, "utf8");
      const result = splitSlideBodyTextBoxes(source, settings);
      if (result.xml !== source) fs.writeFileSync(slidePath, result.xml);
      if (result.count > 0) {
        splitSlides += 1;
        createdTextBoxes += result.count;
      }
    }

    run("zip", ["-q", "-r", stagedPath, "."], { cwd: unpackedDir });
    fs.renameSync(stagedPath, absolutePath);
    console.log(
      `Split body paragraphs into ${createdTextBoxes} text boxes across ${splitSlides} slides: ${absolutePath}`,
    );
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
    fs.rmSync(stagedPath, { force: true });
  }
}

if (process.argv.length < 3) {
  console.error("Usage: node scripts/split-pptx-body-textboxes.mjs <file.pptx> [more.pptx ...]");
  process.exit(2);
}

for (const pptxPath of process.argv.slice(2)) processPresentation(pptxPath);
