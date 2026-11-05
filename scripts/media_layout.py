"""Center standalone media rows and preserve their placement in PowerPoint."""
from zipfile import ZipFile
from lxml import etree as ET
from pathlib import Path
from urllib.parse import unquote, urlparse
import base64
import hashlib
import mimetypes

from bs4 import BeautifulSoup, Comment, Tag


def validate_pptx_namespaces(path):
    """Check prefixes stored as compatibility attribute values, not XML names."""
    mc = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
    compatibility_attributes = {'Ignorable', 'MustUnderstand', 'ProcessContent',
                                'PreserveElements', 'PreserveAttributes'}
    with ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.endswith(('.xml', '.rels')):
                continue
            root = ET.fromstring(archive.read(name))
            for element in root.iter():
                for attribute, value in element.attrib.items():
                    qname = ET.QName(attribute)
                    if ((element.tag == f'{{{mc}}}Choice' and attribute == 'Requires') or
                            (qname.namespace == mc and qname.localname in compatibility_attributes)):
                        for item in value.split():
                            prefix = item.split(':', 1)[0]
                            if prefix not in element.nsmap:
                                raise ValueError(f'PPTX互換性情報の未定義プレフィックス: {name}: '
                                                 f'{qname.localname}="{value}" ({prefix})')


def center_media_rows(path):
    soup = BeautifulSoup(path.read_text(), 'html.parser')
    for slide in soup.select('section.owada'):
        row = None
        for node in list(slide.children):
            if isinstance(node, Comment):
                continue
            if not isinstance(node, Tag):
                if str(node).strip():
                    row = None
                continue
            items = []
            if node.name in ('img', 'iframe', 'video'):
                items = [node]
            elif node.name == 'p' and not node.get_text(strip=True):
                children = [c for c in node.children if isinstance(c, Tag) and c.name != 'br']
                if children and all(c.name in ('img', 'iframe', 'video') or
                                    (c.name == 'a' and c.find('img')) for c in children):
                    items = children
            elif node.name == 'figure' and node.find('img'):
                items = [node]
            elif 'quarto-figure' in node.get('class', []) and node.find('img'):
                items = [node]
            if not items:
                row = None
                continue
            if row is None:
                row = soup.new_tag('div', attrs={'class': 'image-row'})
                node.insert_before(row)
            for item in items:
                cell = soup.new_tag('div', attrs={'class': 'image-item'})
                cell.append(item.extract())
                row.append(cell)
            if node.parent is not None and node not in items:
                node.decompose()
            row['style'] = f'--image-count: {len(row.select(":scope > .image-item"))}'
    path.write_text(str(soup))


def sync_pptx_images(path, layouts, asset_root, title_refs=None):
    """Use rendered slide coordinates while keeping the original editable pictures."""
    ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
          'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
    # Preserve namespace declarations, including prefixes used only in attribute
    # values such as mc:Choice Requires="a14". ElementTree renames/drops them
    # while leaving Requires unchanged, making PowerPoint repair math slides.
    with ZipFile(path) as archive:
        entries = [(entry, archive.read(entry.filename)) for entry in archive.infolist()]
    files = {entry.filename: data for entry, data in entries}
    presentation = ET.fromstring(files['ppt/presentation.xml'])
    if len(presentation.find('p:sldIdLst', ns)) != len(layouts):
        raise ValueError('HTMLとPowerPointのページ数が一致しません')
    size = presentation.find('p:sldSz', ns)
    width, height = int(size.get('cx')), int(size.get('cy'))
    rel_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    content_ns = 'http://schemas.openxmlformats.org/package/2006/content-types'
    types = ET.fromstring(files['[Content_Types].xml'])
    for index, images in enumerate(layouts, 1):
        refs = title_refs[index - 1] if title_refs else None
        if not any(image['centered'] for image in images) and not refs:
            continue
        name = f'ppt/slides/slide{index}.xml'
        slide = ET.fromstring(files[name])
        tree = slide.find('p:cSld/p:spTree', ns)
        ids = [int(node.get('id')) for node in tree.findall('.//p:cNvPr', ns)]
        shape_id = max(ids, default=1)
        rel_name = f'ppt/slides/_rels/slide{index}.xml.rels'
        relations = ET.fromstring(files[rel_name])
        native_pictures = iter(tree.findall('p:pic', ns))
        for image in images:
            existing = next(native_pictures, None) if image.get('existing') or not image['centered'] else None
            if not image['centered']:
                continue
            if image.get('existing'):
                if existing is None:
                    raise ValueError(f'画像の配置を対応できません: {name}')
                transform = existing.find('p:spPr/a:xfrm', ns)
                offset, extent = transform.find('a:off', ns), transform.find('a:ext', ns)
                offset.set('x', str(round(image['x'] * width)))
                offset.set('y', str(round(image['y'] * height)))
                extent.set('cx', str(round(image['width'] * width)))
                extent.set('cy', str(round(image['height'] * height)))
                continue
            source = image['source']
            if source.startswith('data:'):
                header, data = source.split(',', 1)
                mime = header[5:].split(';')[0]
                data = base64.b64decode(data) if ';base64' in header else unquote(data).encode()
                extension = mimetypes.guess_extension(mime).lstrip('.')
            else:
                parsed = urlparse(source)
                asset = Path(unquote(parsed.path))
                if not asset.is_absolute():
                    asset = asset_root / asset
                data = asset.read_bytes()
                extension = asset.suffix.lstrip('.').lower()
                mime = mimetypes.guess_type(asset)[0] or 'application/octet-stream'
            media_name = f'owada-{hashlib.sha256(data).hexdigest()[:20]}.{extension}'
            files[f'ppt/media/{media_name}'] = data
            if not any(node.get('Extension') == extension for node in types):
                ET.SubElement(types, f'{{{content_ns}}}Default', Extension=extension, ContentType=mime)
            relation_id = f'rIdOwadaImage{shape_id + 1}'
            ET.SubElement(relations, f'{{{rel_ns}}}Relationship', Id=relation_id,
                          Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/image',
                          Target=f'../media/{media_name}')
            shape_id += 1
            x, y = round(image['x'] * width), round(image['y'] * height)
            cx, cy = round(image['width'] * width), round(image['height'] * height)
            picture = ET.fromstring(f'''<p:pic xmlns:p="{ns['p']}" xmlns:a="{ns['a']}"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <p:nvPicPr><p:cNvPr id="{shape_id}" name="Image {shape_id}"/>
                <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>
              <p:blipFill><a:blip r:embed="{relation_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
              <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
            </p:pic>''')
            tree.append(picture)
        if refs:
            # Only slides with this optional field reserve room beside the title.
            title = next((shape for shape in tree.findall('p:sp', ns)
                          if shape.find('p:nvSpPr/p:nvPr/p:ph[@type="title"]', ns) is not None), None)
            def set_box(properties, box):
                transform = properties.find('a:xfrm', ns)
                if transform is None:
                    transform = ET.Element(f'{{{ns["a"]}}}xfrm')
                    properties.insert(0, transform)
                    ET.SubElement(transform, f'{{{ns["a"]}}}off')
                    ET.SubElement(transform, f'{{{ns["a"]}}}ext')
                offset, extent = transform.find('a:off', ns), transform.find('a:ext', ns)
                offset.set('x', str(round(box['x'] * width)))
                offset.set('y', str(round(box['y'] * height)))
                extent.set('cx', str(round(box['width'] * width)))
                extent.set('cy', str(round(box['height'] * height)))
            if title is not None:
                set_box(title.find('p:spPr', ns), refs['heading'])
            for block in refs['blocks']:
                shape_id += 1
                shape = ET.fromstring(f'''<p:sp xmlns:p="{ns['p']}" xmlns:a="{ns['a']}">
                  <p:nvSpPr><p:cNvPr id="{shape_id}" name="Title reference {shape_id}"/>
                    <p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
                  <p:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/>
                    <a:ln><a:noFill/></a:ln></p:spPr>
                  <p:txBody><a:bodyPr wrap="square" anchor="t" lIns="0" rIns="0" tIns="0" bIns="0">
                    <a:normAutofit/></a:bodyPr><a:lstStyle/></p:txBody>
                </p:sp>''')
                set_box(shape.find('p:spPr', ns), block)
                paragraph = ET.SubElement(shape.find('p:txBody', ns), f'{{{ns["a"]}}}p')
                properties = ET.SubElement(paragraph, f'{{{ns["a"]}}}pPr', algn='l')
                line_spacing = ET.SubElement(properties, f'{{{ns["a"]}}}lnSpc')
                ET.SubElement(line_spacing, f'{{{ns["a"]}}}spcPts',
                              val=str(round(block['lineHeight'] * height / 12700 * 100)))
                ET.SubElement(properties, f'{{{ns["a"]}}}buNone')
                for run_index, run in enumerate(block['runs']):
                    if run.get('break'):
                        ET.SubElement(paragraph, f'{{{ns["a"]}}}br')
                        continue
                    text_run = ET.SubElement(paragraph, f'{{{ns["a"]}}}r')
                    style = ET.SubElement(text_run, f'{{{ns["a"]}}}rPr', b='0',
                                          sz=str(round(block['fontSize'] * width / 12700 * 100)))
                    fill = ET.SubElement(style, f'{{{ns["a"]}}}solidFill')
                    ET.SubElement(fill, f'{{{ns["a"]}}}srgbClr', val='888888')
                    ET.SubElement(style, f'{{{ns["a"]}}}latin', typeface='Noto Sans JP')
                    ET.SubElement(style, f'{{{ns["a"]}}}ea', typeface='Noto Sans JP')
                    if run.get('href'):
                        style.set('u', 'sng')
                        relation_id = f'rIdTitleRef{shape_id}_{run_index}'
                        ET.SubElement(relations, f'{{{rel_ns}}}Relationship', Id=relation_id,
                                      Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',
                                      Target=run['href'], TargetMode='External')
                        ET.SubElement(style, f'{{{ns["a"]}}}hlinkClick',
                                      {'{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id': relation_id})
                    text = ET.SubElement(text_run, f'{{{ns["a"]}}}t')
                    text.text = run['text']
                tree.append(shape)
        files[name] = ET.tostring(slide, encoding='utf-8', xml_declaration=True)
        files[rel_name] = ET.tostring(relations, encoding='utf-8', xml_declaration=True)
    files['[Content_Types].xml'] = ET.tostring(types, encoding='utf-8', xml_declaration=True)
    with ZipFile(path, 'w') as archive:
        for entry, _ in entries:
            archive.writestr(entry, files.pop(entry.filename))
        for name, data in files.items():
            archive.writestr(name, data)
