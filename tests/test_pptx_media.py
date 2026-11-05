"""Math compatibility declarations must survive editable image placement."""
import base64
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

from lxml import etree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from media_layout import sync_pptx_images, validate_pptx_namespaces

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
A14 = 'http://schemas.microsoft.com/office/drawing/2010/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
SLIDE = f'''<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:mc="{MC}"
 xmlns:a14="{A14}" xmlns:m="{M}" xmlns:future="urn:test:future" mc:Ignorable="future">
 <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/></p:nvGrpSpPr>
 <p:sp><p:nvSpPr><p:cNvPr id="2" name="Equation"/></p:nvSpPr>
 <p:txBody><mc:AlternateContent><mc:Choice Requires="a14"><a14:m>
 <m:oMath><m:r><m:t>Q(x)</m:t></m:r></m:oMath></a14:m></mc:Choice>
 <mc:Fallback><a:p><a:r><a:t>Q(x)</a:t></a:r></a:p></mc:Fallback>
 </mc:AlternateContent></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'''


def fixture(path, slide=SLIDE):
    with ZipFile(path, 'w') as archive:
        archive.writestr('ppt/presentation.xml', f'<p:presentation xmlns:p="{P}">'
                         '<p:sldIdLst><p:sldId id="256"/></p:sldIdLst>'
                         '<p:sldSz cx="14400000" cy="8100000"/></p:presentation>')
        archive.writestr('ppt/slides/slide1.xml', slide)
        archive.writestr('ppt/slides/_rels/slide1.xml.rels',
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
        archive.writestr('[Content_Types].xml',
                         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')


class PptxMediaTests(unittest.TestCase):
    def test_reference_only_slide_gets_small_gray_editable_text_and_links(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path = folder / 'fixture.pptx'
            fixture(path)
            refs = [{'heading': {'x': .06, 'y': .05, 'width': .34, 'height': .06},
                     'blocks': [{'x': .42, 'y': .05, 'width': .52, 'height': .03,
                                 'fontSize': 14/1440, 'lineHeight': 18.2/810,
                                 'runs': [{'text': '[1] Paper A', 'href': 'https://example.org/paper'}]},
                                {'x': .42, 'y': .08, 'width': .52, 'height': .03,
                                 'fontSize': 14/1440, 'lineHeight': 18.2/810,
                                 'runs': [{'text': '[2] Paper B'}]}]}]
            sync_pptx_images(path, [[]], folder, title_refs=refs)
            validate_pptx_namespaces(path)
            ns = {'p': P, 'a': A}
            with ZipFile(path) as archive:
                slide = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
                shapes = [s for s in slide.findall('p:cSld/p:spTree/p:sp', ns)
                          if s.find('p:nvSpPr/p:cNvPr', ns).get('name').startswith('Title reference')]
                self.assertEqual(len(shapes), 2)
                self.assertEqual([s.find('.//a:t', ns).text for s in shapes], ['[1] Paper A', '[2] Paper B'])
                for shape in shapes:
                    self.assertEqual(shape.find('.//a:srgbClr', ns).get('val'), '888888')
                    self.assertEqual(shape.find('.//a:rPr', ns).get('sz'), '1102')
                    self.assertEqual(shape.find('p:spPr/a:xfrm/a:off', ns).get('x'), '6048000')
                relations = ET.fromstring(archive.read('ppt/slides/_rels/slide1.xml.rels'))
                self.assertTrue(any(r.get('Target') == 'https://example.org/paper' for r in relations))

    def test_image_placement_preserves_math_and_unused_compatibility_prefixes(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path = folder / 'fixture.pptx'
            fixture(path)
            image = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC'
                                     'AAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
            (folder / 'image.png').write_bytes(image)
            layouts = [[{'centered': True, 'existing': False, 'source': 'image.png',
                         'x': 0.25, 'y': 0.3, 'width': 0.5, 'height': 0.2}]]
            sync_pptx_images(path, layouts, folder)
            validate_pptx_namespaces(path)
            with ZipFile(path) as archive:
                slide = ET.fromstring(archive.read('ppt/slides/slide1.xml'))
                choice = slide.find(f'.//{{{MC}}}Choice')
                self.assertEqual(choice.get('Requires'), 'a14')
                self.assertEqual(choice.nsmap['a14'], A14)
                self.assertEqual(slide.nsmap['future'], 'urn:test:future')
                self.assertEqual(slide.find(f'.//{{{M}}}t').text, 'Q(x)')
                ns = {'p': P, 'a': A}
                picture = slide.find('p:cSld/p:spTree/p:pic', ns)
                transform = picture.find('p:spPr/a:xfrm', ns)
                self.assertEqual(transform.find('a:off', ns).get('x'), '3600000')
                self.assertEqual(transform.find('a:ext', ns).get('cx'), '7200000')
                media = next(n for n in archive.namelist() if n.startswith('ppt/media/'))
                self.assertEqual(archive.read(media), image)

    def test_undefined_math_prefix_is_rejected_even_when_xml_is_well_formed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'broken.pptx'
            # This matches the old serializer: element prefixes change but
            # the string Requires="a14" remains unchanged.
            broken = SLIDE.replace('xmlns:a14=', 'xmlns:ns4=').replace('<a14:', '<ns4:').replace('</a14:', '</ns4:')
            fixture(path, broken)
            with self.assertRaisesRegex(ValueError, 'slide1.xml.*Requires="a14"'):
                validate_pptx_namespaces(path)


if __name__ == '__main__':
    unittest.main()
