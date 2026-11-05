"""Keep the existing Reveal.js/PPTX format within the deck folder workflow."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile

import yaml
from playwright.sync_api import sync_playwright
from pypdf import PdfReader
from media_layout import center_media_rows, sync_pptx_images, validate_pptx_namespaces


def staged_source(root, deck):
    folder = root / 'decks' / deck
    build = root / '.build' / deck / 'revealjs'
    stage = build / 'source'
    shutil.copytree(folder, stage, dirs_exist_ok=True)
    _, front, body = (folder / 'slides.qmd').read_text().split('---', 2)
    metadata = yaml.safe_load(front)
    formats = metadata['format']
    if isinstance(formats, str):
        formats = metadata['format'] = {formats: {}}
    html = formats['revealjs'] or {}
    formats['revealjs'] = html
    # Browser-native math avoids Reveal.js's default CDN dependency.
    html.setdefault('html-math-method', 'mathml')
    # Reveal's auto-stretch collapses captionless images inside padded OWADA slides.
    html.setdefault('auto-stretch', False)
    # Resolve shared files relative to the real source, not the staging folder.
    theme = html.get('theme', 'default')
    theme = theme if isinstance(theme, list) else [theme]
    html['theme'] = [str((folder / value).resolve()) if (folder / value).is_file() else value for value in theme]
    css = html.get('css', [])
    css = css if isinstance(css, list) else [css]
    html['css'] = css + ['styles/slides.css']
    pptx = formats.get('pptx')
    if pptx is not None:
        metadata['owada-media-layout'] = True
        # Keep page boundaries identical to Reveal, including slides whose
        # only content is the optional title reference block.
        pptx.setdefault('slide-level', 2)
        if 'reference-doc' in pptx:
            pptx['reference-doc'] = str((folder / pptx['reference-doc']).resolve())
        pptx['filters'] = [str((folder / value).resolve()) for value in pptx.get('filters', [])]
    # The staged input is named after the deck, giving every output a unique name.
    source = stage / f'{deck}.qmd'
    source.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + '---' + body)
    return source, metadata


def build(root, deck):
    source, metadata = staged_source(root, deck)
    subprocess.run(['node', str(root / 'scripts/build-pptx-reference.mjs')], check=True, cwd=root)
    subprocess.run(['quarto', 'render', str(source), '--to', 'revealjs'], check=True, cwd=source.parent)
    center_media_rows(source.with_suffix('.html'))
    output = root / 'output' / deck
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source.with_suffix('.html'), output / f'{deck}.html')
    # Preserve Chalkboard and other native plugins, which Quarto cannot embed.
    for directory in (f'{deck}_files', 'assets', 'styles'):
        if (source.parent / directory).is_dir():
            shutil.copytree(source.parent / directory, output / directory, dirs_exist_ok=True)
    if 'pptx' in metadata['format']:
        subprocess.run(['quarto', 'render', str(source), '--to', 'pptx'], check=True, cwd=source.parent)
        pptx = source.with_suffix('.pptx')
        subprocess.run(['node', str(root / 'scripts/split-pptx-body-textboxes.mjs'), str(pptx)], check=True, cwd=root)
    title_refs = []
    layouts = verify(root, deck, export=True, title_refs=title_refs)
    if 'pptx' in metadata['format']:
        sync_pptx_images(pptx, layouts, output, title_refs=title_refs)
        validate_pptx_namespaces(pptx)
        shutil.copy2(pptx, output / f'{deck}.pptx')


def verify(root, deck, export=False, title_refs=None):
    output = root / 'output' / deck / f'{deck}.html'
    if not output.is_file():
        raise ValueError(f'出力がありません。先にbuildしてください: {output}')
    build = root / '.build' / deck / 'revealjs'
    build.mkdir(parents=True, exist_ok=True)
    errors, requests, overflow, layouts = [], [], [], []
    with tempfile.TemporaryDirectory(prefix='reveal-portable-') as temp, sync_playwright() as p:
        portable = Path(temp) / deck
        shutil.copytree(output.parent, portable)
        standalone = portable / output.name
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 810})
        def offline(route):
            requests.append(route.request.url)
            route.abort()
        context.route(re.compile(r'^https?://'), offline)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('requestfailed', lambda request: errors.append('Failed resource: ' + request.url))
        page.goto(standalone.as_uri())
        page.wait_for_function('window.Reveal && Reveal.isReady()')
        count = page.evaluate('Reveal.getTotalSlides()')
        for i in range(count):
            page.evaluate('(i)=>{const s=Reveal.getSlides()[i];const pos=Reveal.getIndices(s);Reveal.slide(pos.h,pos.v);}', i)
            page.wait_for_function('''() => [...Reveal.getCurrentSlide().querySelectorAll('img')]
                .filter(img => !img.closest('.notes'))
                .every(img => img.complete && img.naturalWidth > 0)''')
            layouts.append(page.evaluate('''() => {
                const s = Reveal.getCurrentSlide(), bounds = s.getBoundingClientRect();
                return [...s.querySelectorAll('img')].filter(img => !img.closest('.notes')).map(img => {
                    const box = img.getBoundingClientRect();
                    return {centered: !!img.closest('.image-row'),
                        existing: !!img.closest('a') || !!img.closest('figure')?.querySelector('figcaption'),
                        source: img.getAttribute('src'),
                        x: (box.x-bounds.x)/bounds.width, y: (box.y-bounds.y)/bounds.height,
                        width: box.width/bounds.width, height: box.height/bounds.height};
                });
            }'''))
            if title_refs is not None:
                title_refs.append(page.evaluate('''() => {
                    const slide = Reveal.getCurrentSlide();
                    const refs = slide.querySelector(':scope > .title-refs');
                    if (!refs) return null;
                    const bounds = slide.getBoundingClientRect();
                    const box = element => {
                        const r = element.getBoundingClientRect();
                        return {x: (r.x-bounds.x)/bounds.width, y: (r.y-bounds.y)/bounds.height,
                            width: r.width/bounds.width, height: r.height/bounds.height};
                    };
                    const runs = node => {
                        if (node.nodeType === Node.TEXT_NODE)
                            return [{text: node.textContent, href: node.parentElement.closest('a')?.href}];
                        if (node.nodeName === 'BR') return [{break: true}];
                        return [...node.childNodes].flatMap(runs);
                    };
                    return {heading: box(slide.querySelector(':scope > h2')),
                        blocks: [...refs.querySelectorAll(':scope > p')].map(p => ({...box(p),
                            fontSize: parseFloat(getComputedStyle(p).fontSize) / bounds.width,
                            lineHeight: parseFloat(getComputedStyle(p).lineHeight) / bounds.height,
                            runs: runs(p)}))};
                }'''))
            page.screenshot(path=str(build / f'{i+1:02}.png'))
            issues = page.evaluate('''() => {
                const s=Reveal.getCurrentSlide(), b=s.getBoundingClientRect();
                return [...s.querySelectorAll('h1,h2,h3,p,li,img,iframe')].filter(e=>{
                    const r=e.getBoundingClientRect();
                    return r.width && r.height && (r.left<b.left-2 || r.right>b.right+2 || r.top<b.top-2 || r.bottom>b.bottom+2);
                }).map(e=>e.textContent.slice(0,80));
            }''')
            overflow.extend(f'page {i+1}: {issue}' for issue in issues)
        page.evaluate('Reveal.slide(0)')
        page.keyboard.press('ArrowRight')
        if count > 1 and page.evaluate('Reveal.getIndices().h') != 1:
            raise ValueError('Reveal.jsのページ移動に失敗しました')
        if export:
            page.goto(standalone.as_uri() + '?print-pdf')
            page.wait_for_function('document.querySelectorAll(".pdf-page").length > 0')
            page.evaluate('document.fonts.ready')
            page.pdf(path=str(output.with_suffix('.pdf')), print_background=True, prefer_css_page_size=True)
            if len(PdfReader(output.with_suffix('.pdf')).pages) != count:
                raise ValueError('PDF page count mismatch')
        browser.close()
    report = {'format': 'revealjs', 'pages': count, 'browser_errors': errors,
              'external_requests': requests, 'source_layout_warnings': overflow}
    (build / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if errors or requests:
        raise ValueError(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'PASS: {count} pages; navigation, portable output folder' + (', PDF' if export else ''))
    if overflow:
        print(f'元の書式のはみ出し候補 {len(overflow)} 件: {build / "checks.json"}')
    print(output)
    return layouts
