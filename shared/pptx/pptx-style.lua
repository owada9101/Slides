-- Keep the reveal.js template chrome when Pandoc writes PowerPoint.
--
-- PowerPoint does not understand the SCSS. This filter therefore creates the
-- cover, section divider, and page number as SVG backgrounds. Body slide
-- titles and body copy remain editable PowerPoint text and use
-- owada-reference.pptx for their placement and style.

if FORMAT ~= "pptx" then
  return {}
end

local slide_number = 0
local text_box_marker = "OWADA_PPTX_TEXT_BOX_START_7E3F"

local function escape_xml(value)
  return value:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
    :gsub('"', "&quot;"):gsub("'", "&apos;")
end

local function svg_title_lines(value)
  -- The cover title is rendered into SVG for PPTX, so translate an explicit
  -- marker into separate SVG lines rather than relying on HTML whitespace.
  local normalized = value:gsub("||", "\n"):gsub("<br%s*/?>", "\n")
  local lines = {}
  for line in (normalized .. "\n"):gmatch("(.-)\n") do
    lines[#lines + 1] = "<tspan x=\"720\" dy=\"1.15em\">" .. escape_xml(line) .. "</tspan>"
  end
  if #lines > 0 then lines[1] = lines[1]:gsub(' dy="1.15em"', "") end
  return table.concat(lines)
end

local function title_text(element)
  for _, inline in ipairs(element.content) do
    if inline.t == "Str" then
      local value = inline.text:gsub("||", "\n"):gsub("<br%s*/?>", "\n")
      return value
    end
  end
  return pandoc.utils.stringify(element.content)
end

local function has_class(element, wanted)
  for _, class_name in ipairs(element.classes) do
    if class_name == wanted then return true end
  end
  return false
end

local function contains_image(inlines)
  for _, inline in ipairs(inlines) do
    if inline.t == "Image" then return true end
    if inline.content and contains_image(inline.content) then return true end
  end
  return false
end

local function write_background(title, subtitle, date, kind, page_number)
  local temporary_name = os.tmpname()
  os.remove(temporary_name)
  local filename = temporary_name .. ".svg"
  local file = assert(io.open(filename, "w"))
  local font = "Yu Gothic, YuGothic, Hiragino Sans, Noto Sans JP, sans-serif"
  local svg

  if kind == "title" then
    svg = string.format([[
<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="810" viewBox="0 0 1440 810">
  <rect width="1440" height="810" fill="#ffffff"/>
  <text x="720" y="337" text-anchor="middle" fill="#1f1f1f" font-family="%s" font-size="58" font-weight="700">%s</text>
  <text x="720" y="461" text-anchor="middle" fill="#1f1f1f" font-family="%s" font-size="32">%s</text>
  <text x="720" y="514" text-anchor="middle" fill="#1f1f1f" font-family="%s" font-size="28">%s</text>
  <text x="1416" y="39" text-anchor="end" fill="#777777" font-family="Arial, sans-serif" font-size="18">%d</text>
</svg>
]], font, svg_title_lines(title), font, escape_xml(subtitle), font, escape_xml(date), page_number)
  elseif kind == "section" then
    svg = string.format([[
<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="810" viewBox="0 0 1440 810">
  <rect width="1440" height="810" fill="#ffffff"/>
  <text x="84" y="430" fill="#1f1f1f" font-family="%s" font-size="72" font-weight="700">%s</text>
  <text x="1416" y="39" text-anchor="end" fill="#777777" font-family="Arial, sans-serif" font-size="18">%d</text>
</svg>
]], font, escape_xml(title), page_number)
  else
    svg = string.format([[
<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="810" viewBox="0 0 1440 810">
  <rect width="1440" height="810" fill="#ffffff"/>
  <text x="1416" y="39" text-anchor="end" fill="#777777" font-family="Arial, sans-serif" font-size="18">%d</text>
</svg>
]], page_number)
  end

  file:write(svg)
  file:close()
  return filename
end

function Header(element)
  if element.level ~= 2 then return nil end

  slide_number = slide_number + 1
  local title = title_text(element)
  local is_title = has_class(element, "owada-title")
  local is_section = has_class(element, "owada-section")
  local kind = is_title and "title" or (is_section and "section" or "body")
  element.attributes["background-image"] = write_background(
    title,
    element.attributes["data-subtitle"] or "",
    element.attributes["data-date"] or "",
    kind,
    slide_number
  )

  -- Title and section text are drawn in the SVG to use their dedicated layout.
  if is_title or is_section then element.content = {} end
  return element
end

function Pandoc(document)
  if document.meta["owada-media-layout"] then
    -- The build places these as editable text beside the title, using the
    -- rendered HTML coordinates. Keep them out of Pandoc's body placeholder.
    document = document:walk({Div = function(element)
      if has_class(element, "title-refs") then return {} end
    end})
    local blocks, body_slide = {}, false
    for _, block in ipairs(document.blocks) do
      if block.t == "Header" then body_slide = has_class(block, "owada") end
      local remove, count = body_slide and block.t == "Para", 0
      if remove then
        for _, inline in ipairs(block.content) do
          if inline.t == "Image" and #inline.caption == 0 then
            count = count + 1
          elseif inline.t ~= "Space" and inline.t ~= "SoftBreak" and inline.t ~= "LineBreak" then
            remove = false
          end
        end
      end
      -- The build inserts standalone media as editable pictures. Avoid the
      -- PPTX writer's automatic extra slides for multiple image paragraphs.
      if not remove or count == 0 then blocks[#blocks + 1] = block end
    end
    document.blocks = blocks
  end
  -- Markdownでは、空行で区切った本文だけがトップレベルのParaになる。
  -- そのParaへ目印を付け、PPTX生成後に独立したテキストボックスへ分割する。
  -- 単なる1回の改行（SoftBreak）や、画像だけの段落は分割対象にしない。
  for _, block in ipairs(document.blocks) do
    if block.t == "Para"
      and not contains_image(block.content)
      and pandoc.utils.stringify(block.content):match("%S") then
      table.insert(block.content, 1, pandoc.Str(text_box_marker))
    end
  end
  return document
end
