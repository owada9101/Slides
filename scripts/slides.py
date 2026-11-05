"""Adapted from murata-lab/quarto-html scripts/slides.py for deck-local assets.

uv run scripts/slides.py {new,animation,build,check} ..."""
from __future__ import annotations
import argparse, base64, copy, json, mimetypes, re, shutil, subprocess, tempfile
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter
import yaml
import revealjs

ROOT = Path(__file__).resolve().parents[1]

def is_revealjs(deck):
    source=ROOT/'decks'/deck/'slides.qmd'
    if not source.is_file(): raise ValueError(f'スライドがありません: {source}')
    metadata=yaml.safe_load(source.read_text().split('---',2)[1]) or {}
    formats=metadata.get('format',{})
    return formats == 'revealjs' or isinstance(formats,dict) and 'revealjs' in formats

def name(value):
    if not re.fullmatch(r'[\w-]+', value) or value.startswith('.'):
        raise argparse.ArgumentTypeError('名前には文字・数字・ハイフン・アンダースコアを使用してください')
    return value

def data_uri(path):
    return f'data:{mimetypes.guess_type(path)[0] or "application/octet-stream"};base64,' + base64.b64encode(path.read_bytes()).decode()

def local(base, value):
    if re.match(r'^(https?:|//)', value):
        raise ValueError(f'外部依存をローカルへ保存してください: {value}')
    path = (base / value.split('#')[0].split('?')[0]).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f'リポジトリ外のリソースは使用できません: {value}')
    return path

def css_inline(css, base):
    if '@import' in css:
        raise ValueError('CSS @import は使用せずローカルCSSにまとめてください')
    def replace(m):
        value=m[1].strip(' \"\'')
        if value.startswith(('data:', '#')): return m[0]
        return 'url("'+data_uri(local(base,value))+'")'
    return re.sub(r'url\(([^)]+)\)',replace,css)

def module_inline(path, stack=()):
    """Bundle local static ES module imports without a Node/npm build step."""
    if path in stack:
        raise ValueError(f'Circular module import: {path}')
    source=path.read_text()
    def replace(match):
        dep=local(path.parent,match[2])
        code=module_inline(dep,(*stack,path))
        uri='data:text/javascript;base64,'+base64.b64encode(code.encode()).decode()
        return match[1]+uri+match[3]
    return re.sub(r"(from\s*['\"])([^'\"]+)(['\"])",replace,source)


def bundle(soup, base):
    for el in list(soup.select('script[src],link[rel="stylesheet"],img[src],source[src],video[src],audio[src],iframe[src]')):
        attr='href' if el.name=='link' else 'src'; value=el[attr]
        if value.startswith('data:'): continue
        path=local(base,value)
        if el.name=='script':
            el.string=module_inline(path) if el.get('type')=='module' else path.read_text();del el['src']
        elif el.name=='link':
            style=soup.new_tag('style');style.string=css_inline(path.read_text(),path.parent);el.replace_with(style)
        elif el.name=='iframe':
            child=BeautifulSoup(path.read_text(),'html.parser');bundle(child,path.parent)
            el['srcdoc']=str(child);del el['src'];el['tabindex']='-1'
        else: el[attr]=data_uri(path)
    for style in soup.select('style'):
        style.string=css_inline(style.string or "",base)
    for el in soup.select('[style]'): el['style']=css_inline(el['style'],base)
    for el in soup.select('[srcset]'):
        raise ValueError('srcset は src に置き換えてください')


def create_deck(args):
    dest=ROOT/'decks'/args.name
    if dest.exists(): raise ValueError(f'既に存在します: {dest}')
    source=ROOT/'decks'/args.source if args.source else ROOT/'templates/deck'
    if not source.is_dir(): raise ValueError(f'コピー元がありません: {source}')
    # HTML figures and PDFs are source assets too; preserve them when cloning.
    shutil.copytree(source,dest,ignore=shutil.ignore_patterns('.build','.quarto','__pycache__'))
    if args.title:
        qmd=dest/'slides.qmd'
        text=qmd.read_text()
        text=text.replace('title: "発表タイトル"','title: '+json.dumps(args.title,ensure_ascii=False),1)
        qmd.write_text(text.replace('発表タイトル',args.title))
    print(dest/'slides.qmd')


def create_animation(args):
    folder=ROOT/'decks'/args.deck
    if not (folder/'slides.qmd').is_file(): raise ValueError(f'スライドがありません: {folder}')
    dest=folder/'assets/html'/args.name
    dest.mkdir(parents=True,exist_ok=False)
    (dest/'index.html').write_text('''<!doctype html><html lang="ja"><meta charset="utf-8">
<style>body{margin:0;font:28px sans-serif;color:#182b3a}main{padding:35px} .item{padding:20px;border-left:5px solid #007d88;margin:12px} [hidden]{display:none}</style>
<main><div class="item">入力</div><div class="item" data-show="1">処理</div><div class="item" data-show="2">結果</div></main>
<script src="../../../../../shared/frame.js"></script><script>
registerAnimation({steps:2,render(step){document.querySelectorAll('[data-show]').forEach(e=>e.hidden=Number(e.dataset.show)>step);}});
</script></html>''')
    print(f'<iframe src="assets/html/{args.name}/index.html" title="図の説明"></iframe>')


def render(deck):
    folder=ROOT/'decks'/deck
    if not (folder/'slides.qmd').exists(): raise ValueError(f'スライドがありません: {folder}')
    build=ROOT/'.build'/deck; build.mkdir(parents=True,exist_ok=True)
    # Render a staged source so Quarto intermediates never enter the slide folder.
    source=folder/'slides.qmd';raw=source.read_text()
    metadata={'format':{'html':{'theme':'none','minimal':True,'embed-resources':False,'section-divs':False,'html-math-method':'plain','toc':False}},'bibliography':str(folder/'reference.bib'),'csl':str(ROOT/'shared/numeric.csl'),'citeproc':True,'link-citations':True,'link-bibliography':True,'lang':'ja'}
    (build/'config.yml').write_text(yaml.safe_dump(metadata,allow_unicode=True))
    # Keep relative resource paths rooted at the original deck during packaging.
    (build/'slides.qmd').write_text(raw)
    subprocess.run(['quarto','render',str(build/'slides.qmd'),'--metadata-file',str(build/'config.yml')],check=True,cwd=ROOT)
    doc=BeautifulSoup((build/'slides.html').read_text(),'html.parser')
    refs={e['id']:copy.copy(e) for e in doc.select('.csl-entry')}
    for e in doc.select('#refs,header#title-block-header'):e.decompose()
    main=doc.select_one('main') or doc.body
    slides=[];current=None;group=''
    for child in list(main.children):
        if getattr(child,'name',None) in ('h1','h2'):
            is_section=child.name=='h1'
            if is_section:group=child.get_text(' ',strip=True)
            current=doc.new_tag('section');current['class']=['slide']+child.get('class',[])
            if child.get('id'):current['id']=child['id'];del child['id']
            current['data-group']=group;current['data-section-start']=str(is_section).lower()
            if is_section:current['class'].append('section-slide')
            slides.append(current)
        if current is not None:current.append(child.extract())
    if not slides:raise ValueError('## 見出しが必要です')
    # A bibliography is a default output, even when QMD omits its heading.
    if refs:
        placeholder=next((s for s in slides if s.get('id')=='references'),None)
        if placeholder is not None:slides.remove(placeholder)
        entries=list(refs.values())
        for offset in range(0,len(entries),5):
            section=doc.new_tag('section',attrs={'class':['slide','references-slide'],'data-group':'参考文献','data-section-start':str(offset==0).lower()})
            heading=doc.new_tag('h2');heading.string='参考文献'+(f'（{offset//5+1}）' if offset else '')
            section.append(heading)
            for entry in entries[offset:offset+5]:section.append(copy.copy(entry))
            slides.append(section)
    chapter=0
    for i,s in enumerate(slides):
        if "section-slide" in s.get("class",[]):
            chapter+=1;s["data-chapter"]=f"{chapter:02d}"
        footer=doc.new_tag('footer');footer['class']='citations';seen=set()
        for citation in s.select('[data-cites]'):
            for key in citation['data-cites'].split():
                if key in seen:continue
                seen.add(key);entry=refs.get('ref-'+key)
                if entry is None:raise ValueError(f'参考文献が見つかりません: {key}')
                p=doc.new_tag('p');p.string=entry.get_text(' ',strip=True);footer.append(p)
        if seen:s.append(footer)
        n=doc.new_tag('span');n['class']='page-number';n.string=f'{i+1} / {len(slides)}';s.append(n)
        # Citations are fully printed on this page; no broken bibliography jumps.
        for a in s.select('a[role="doc-biblioref"]'):a.unwrap()
    title=doc.title.get_text() if doc.title else deck
    shell=BeautifulSoup('<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title></title></head><body><div class="reveal"><main id="stage" class="slides"></main></div><nav id="toolbar" aria-label="スライド操作"><button id="menu" aria-label="スライド一覧">☰</button><button id="fullscreen" aria-label="全画面">⛶</button></nav><aside id="overview" aria-label="スライド一覧" role="dialog" aria-modal="true" hidden><button id="close">閉じる</button><p id="help">↑↓ ページ · ←→ step · 左右長押しで先頭／最後 · 画面左30%で戻る／それ以外で進む</p></aside></body></html>','html.parser')
    shell.title.string=title
    style=shell.new_tag('style');style.string=(ROOT/'shared/slides.css').read_text()+'\n'+(ROOT/'shared/original-slides.css').read_text()+'\n'+(ROOT/'shared/player-layout.css').read_text()+'\n'+css_inline((folder/'styles/slides.css').read_text(),folder/'styles');shell.head.append(style)
    for s in slides:shell.select_one('#stage').append(s)
    for iframe in shell.select('iframe'):
        wrapper=shell.new_tag('div',attrs={'class':'animation loaded'})
        iframe.wrap(wrapper)
    bundle(shell,folder)
    script=shell.new_tag('script');script.string=(ROOT/'shared/player.js').read_text();shell.body.append(script)
    out=ROOT/'output'/deck/f'{deck}.html';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(str(shell))
    return out


# Check real layout boxes in every step, including each iframe document.
LAYOUT = '''() => {
const issues=[];const root=document.querySelector('.slide.active')||document.body;
const bounds=root.getBoundingClientRect();
const els=[...root.querySelectorAll('h1,h2,h3,p,li,table,iframe,img,svg,text,.item,.page-number')].filter(e=>{const s=getComputedStyle(e);let visible=true;for(let a=e;a&&a!==root.parentElement;a=a.parentElement){if(Number(getComputedStyle(a).opacity)===0)visible=false;}if(e.tagName==='text'){const r=e.getBoundingClientRect(),top=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);if(top!==e&&!e.contains(top))visible=false;}return visible&&s.visibility!=='hidden'&&s.display!=='none'&&e.getBoundingClientRect().width>0});
for(const e of els){const r=e.getBoundingClientRect();if(r.left<bounds.left-2||r.right>bounds.right+2||r.top<bounds.top-2||r.bottom>bounds.bottom+2)issues.push('overflow: '+e.textContent.slice(0,70));}
const footer=root.querySelector('.citations');if(footer){const f=footer.getBoundingClientRect();for(const e of els){if(footer.contains(e))continue;const r=e.getBoundingClientRect();if(r.bottom>f.top&&r.top<f.bottom&&r.right>f.left&&r.left<f.right)issues.push('footer overlap: '+e.textContent.slice(0,70));}}
for(let i=0;i<els.length;i++)for(let j=i+1;j<els.length;j++){const a=els[i],b=els[j];if(a.contains(b)||b.contains(a)||((a.closest('svg')||b.closest('svg'))&&!(a.tagName==='text'&&b.tagName==='text')))continue;const x=a.getBoundingClientRect(),y=b.getBoundingClientRect();if(Math.min(x.right,y.right)-Math.max(x.left,y.left)>3&&Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top)>3)issues.push('overlap: '+a.tagName+' '+a.textContent.slice(0,45)+' / '+b.tagName+' '+b.textContent.slice(0,45));}
return [...new Set(issues)];}'''


def verify(deck, export=False):
    out=ROOT/'output'/deck/f'{deck}.html';build=ROOT/'.build'/deck;build.mkdir(parents=True,exist_ok=True)
    issues=[];warnings=[];errors=[];requests=[]
    with tempfile.TemporaryDirectory(prefix="quarto-portable-") as portable, sync_playwright() as p:
        standalone=Path(portable)/out.name
        shutil.copy2(out,standalone)
        browser=p.chromium.launch();context=browser.new_context(viewport={'width':1280,'height':720},device_scale_factor=1)
        context.route(re.compile(r'^https?://'),lambda route:(requests.append(route.request.url),route.abort()))
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('requestfailed',lambda request:errors.append('Failed resource: '+request.url))
        page.goto(standalone.as_uri());page.wait_for_function('window.deckReady === true')
        page.evaluate("document.body.classList.add('export')")
        count=page.evaluate('deck.count');writer=PdfWriter()
        for i in range(count):
            page.evaluate('(i)=>deck.go(i)',i)
            for step in range(page.evaluate('deck.maxStep()')+1):
                page.evaluate('([i,s])=>deck.go(i,s)',[i,step]);page.wait_for_timeout(20)
                for frame in page.frames:
                    if frame==page.main_frame or frame.frame_element().is_visible():
                        for x in frame.evaluate(LAYOUT):
                            issues.append(f'page {i+1}, step {step}: {x}')
            page.screenshot(path=str(build/f'{i+1:02d}.png'))
            if export:
                # One visible page per PDF: keeps native text and the final iframe state.
                pdf=page.pdf(width='1280px',height='720px',print_background=True,page_ranges='1')
                import io
                writer.append(PdfReader(io.BytesIO(pdf)))
        if export:
            with (out.with_suffix('.pdf')).open('wb') as f:writer.write(f)
        page.evaluate("document.body.classList.remove('export');deck.go(0)")
        page.keyboard.press('ArrowDown');assert page.evaluate('deck.index')==min(1,count-1)
        page.keyboard.press('ArrowUp');assert page.evaluate('deck.index')==0
        animated=page.evaluate("[...document.querySelectorAll('.slide')].findIndex(s=>[...s.querySelectorAll('iframe')].some(f=>(f.contentWindow.animation?.steps||0)>0))")
        if animated>=0:
            page.evaluate('(i)=>deck.go(i)',animated)
            page.keyboard.press('ArrowRight');assert page.evaluate('deck.step')==1
            page.keyboard.down('ArrowRight');page.wait_for_timeout(520);page.keyboard.up('ArrowRight')
            assert page.evaluate('deck.step===deck.maxStep()') and page.evaluate('deck.index')==animated
            page.keyboard.down('ArrowLeft');page.wait_for_timeout(520);page.keyboard.up('ArrowLeft')
            assert page.evaluate('deck.step')==0
        page.click('#fullscreen');page.wait_for_function('!!document.fullscreenElement')
        page.click('#fullscreen');page.wait_for_function('!document.fullscreenElement')
        page.click('#menu');assert page.locator('#overview').is_visible();page.screenshot(path=str(build/'overview.png'));page.click('.thumb >> nth=0');assert page.evaluate('deck.index')==0
        mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,device_scale_factor=1)
        mobile.route(re.compile(r'^https?://'),lambda route:(requests.append(route.request.url),route.abort()))
        mp=mobile.new_page();mp.on('pageerror',lambda error:errors.append(str(error)));mp.goto(standalone.as_uri());mp.wait_for_function('window.deckReady')
        if animated>=0:
            mp.evaluate('(i)=>deck.go(i)',animated);box=mp.locator('#stage').bounding_box()
            mp.touchscreen.tap(box['x']+box['width']*.7,box['y']+box['height']*.5);assert mp.evaluate('deck.step')==1
            mp.touchscreen.tap(box['x']+box['width']*.1,box['y']+box['height']*.5);assert mp.evaluate('deck.step')==0
        mp.locator('#menu').tap();assert mp.locator('#overview').is_visible();mp.locator('#close').tap()
        mp.screenshot(path=str(build/'mobile.png'))
        mobile.close();browser.close()
    report={'pages':count,'layout_issues':issues,'reference_warnings':warnings,'browser_errors':errors,'external_requests':requests}
    (build/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if issues or errors or requests:raise ValueError(json.dumps(report,ensure_ascii=False,indent=2))
    if export and len(PdfReader(out.with_suffix('.pdf')).pages)!=count:raise ValueError('PDF page count mismatch')
    if warnings: print('Reference warnings: '+json.dumps(warnings,ensure_ascii=False))
    print(f'PASS: {count} pages; desktop/mobile, steps, offline, layout\n{out}\n{out.with_suffix(".pdf")}')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    new=sub.add_parser('new');new.add_argument('name',type=name);new.add_argument('--from',dest='source',type=name);new.add_argument('--title')
    anim=sub.add_parser('animation');anim.add_argument('deck',type=name);anim.add_argument('name',type=name)
    for cmd in ('build','check'):
        p=sub.add_parser(cmd);p.add_argument('name',type=name)
    args=parser.parse_args()
    try:
        if args.command=='new':create_deck(args)
        elif args.command=='animation':create_animation(args)
        elif args.command=='build':
            if is_revealjs(args.name):revealjs.build(ROOT,args.name)
            else:render(args.name);verify(args.name,export=True)
        else:
            if is_revealjs(args.name):revealjs.verify(ROOT,args.name)
            else:verify(args.name)
    except (ValueError,FileNotFoundError) as error:parser.exit(1,str(error)+'\n')
if __name__=='__main__':main()
