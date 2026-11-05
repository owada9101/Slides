(() => {
const slides=[...document.querySelectorAll('.slide')], stage=document.querySelector('#stage'), overview=document.querySelector('#overview');
let index=0, step=0, held=null, timer=null, long=false, lastInput=-Infinity;
const frames=s=>[...s.querySelectorAll('iframe')];
function maxStep(){return Math.max(0,...frames(slides[index]).map(f=>f.contentWindow.animation?.steps||0),...[...slides[index].querySelectorAll('[data-step],[data-highlight-step]')].map(e=>Number(e.dataset.step||e.dataset.highlightStep)));}
function paint(animate=false){slides.forEach((s,i)=>{s.classList.toggle('active',i===index);s.setAttribute('aria-hidden',String(i!==index));frames(s).forEach(f=>f.contentWindow.animation?.setVisible?.(i===index));}); frames(slides[index]).forEach(f=>f.contentWindow.animation?.setStep(step,animate));slides[index].querySelectorAll('[data-step]').forEach(e=>e.classList.toggle('pending',Number(e.dataset.step)>step)); slides[index].querySelectorAll('[data-highlight-step]').forEach(e=>{e.classList.toggle('animate-highlight',animate);e.classList.toggle('is-highlighted',Number(e.dataset.highlightStep)<=step);}); history.replaceState(null,'',`#${index+1}/${step}`);}
function go(i,n=0,animate=false){index=Math.max(0,Math.min(slides.length-1,i));step=Math.max(0,Math.min(maxStep(),n));paint(animate);}
function move(dir){const now=performance.now(),animate=now-lastInput>300;lastInput=now;if(dir>0){step<maxStep()?go(index,step+1,animate):go(index+1);}else{step>0?go(index,step-1,animate):(index>0&&go(index-1,Infinity));}}
function jump(dir){go(index,dir>0?Infinity:0);}
function resize(){let scale=Math.min(innerWidth/1280,innerHeight/720)*.95;stage.style.transform=`scale(${scale})`;stage.style.left=`${(innerWidth-1280*scale)/2}px`;stage.style.top=`${(innerHeight-720*scale)/2}px`;}
function close(){overview.hidden=true;document.querySelector('#menu').focus();}
function menu(){overview.hidden=false;overview.querySelectorAll('.thumb').forEach((b,i)=>b.setAttribute('aria-current',String(i===index)));overview.querySelector('#close').focus();}
const grouped=slides.some(s=>s.dataset.sectionStart==='true');
let row;
slides.forEach((s,i)=>{if(!row||s.dataset.sectionStart==='true'){if(grouped){const h=document.createElement('h2');h.textContent=s.dataset.group||'表紙';overview.append(h);}row=document.createElement('div');row.className=grouped?'overview-row':'overview-grid';overview.append(row);}const b=document.createElement('button');b.className='thumb';const num=document.createElement('span');num.textContent=String(i+1).padStart(2,'0');b.append(num,document.createTextNode(s.querySelector('h1,h2')?.textContent||'Slide'));b.onclick=()=>{go(i);close();};row.append(b);});
document.querySelector('#menu').onclick=menu;document.querySelector('#close').onclick=close;
async function fullscreen(){try {if(document.fullscreenElement)await document.exitFullscreen();else if(document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen();else document.querySelector('#fullscreen').textContent='全画面非対応';}catch{document.querySelector('#fullscreen').textContent='全画面非対応';}}
document.querySelector('#fullscreen').onclick=fullscreen;
function cancel(){clearTimeout(timer);held=null;long=false;}
addEventListener('keydown',e=>{if(e.target.closest('input,textarea,select'))return;if(!overview.hidden){if(e.key==='Escape')close();if(e.key==='Tab'){const items=[...overview.querySelectorAll('button')];if(e.shiftKey&&document.activeElement===items[0]){e.preventDefault();items.at(-1).focus();}else if(!e.shiftKey&&document.activeElement===items.at(-1)){e.preventDefault();items[0].focus();}}return;}if(e.target.closest('button,a')&&(e.key===' '||e.key==='Enter'))return;
if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();if(held)return;held=e.key;long=false;timer=setTimeout(()=>{long=true;jump(e.key==='ArrowRight'?1:-1);},450);return;}
if(e.repeat)return;if(['ArrowDown','ArrowUp',' ','Escape','o','f'].includes(e.key))e.preventDefault();if(e.key==='ArrowDown')go(index+1);if(e.key==='ArrowUp')go(index-1);if(e.key===' ')move(1);if(e.key==='Escape'||e.key==='o')menu();if(e.key==='f')fullscreen();});
addEventListener('keyup',e=>{if(e.key===held){if(!long)move(e.key==='ArrowRight'?1:-1);cancel();}});addEventListener('blur',cancel);document.addEventListener('visibilitychange',cancel);
stage.addEventListener('click',e=>{if(e.target.closest('a,button,input')||!overview.hidden)return;const r=stage.getBoundingClientRect();move(e.clientX-r.left<r.width*.3?-1:1);});
window.deck={go,move,jump,maxStep,get index(){return index},get step(){return step},get count(){return slides.length}};
addEventListener('resize',resize);resize();
Promise.all([...document.querySelectorAll('iframe')].map(f=>new Promise(resolve=>{if(f.contentWindow?.animation)resolve();else f.addEventListener('load',resolve,{once:true});}))).then(()=>{const m=location.hash.match(/^#(\d+)(?:\/(\d+))?$/);go(m?Number(m[1])-1:0,m?Number(m[2]||0):0);window.deckReady=true;});
})();
