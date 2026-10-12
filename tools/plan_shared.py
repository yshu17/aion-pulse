"""Embed one generated, offline-capable task explorer in all five plan pages.

The source plans remain authoritative. The browser ledger contains personal status
overrides and history; exporting it is the way to move those notes to another device.
"""

from __future__ import annotations

import json
import re

from plan_ai_view import SHARED_CONTROLS, SHARED_CSS, SHARED_JS


STYLE = r"""<style id="shared-plan-style">
.shared-plan{margin:12px 0 18px;border:1px solid #424650;border-radius:10px;background:#1c1e24;color:#e9e7e4;font:13px/1.45 'Segoe UI',system-ui,sans-serif}
.shared-plan summary{cursor:pointer;padding:10px 12px;font-weight:650;color:#ffb05c}
.shared-inner{padding:0 12px 12px}.shared-note{color:#aeb2ba;margin:0 0 9px}
.shared-controls{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.shared-controls input,.shared-controls select,.shared-controls button,.shared-status{font:inherit;color:#e9e7e4;background:#262931;border:1px solid #484c58;border-radius:7px;padding:7px;min-height:36px}
.shared-controls input[type=search]{flex:1;min-width:150px}.shared-controls button{cursor:pointer}.shared-controls button:hover{border-color:#ff8c1a}
.shared-chart{display:flex;height:11px;border-radius:9px;overflow:hidden;background:#353841;margin:9px 0 4px}.shared-chart span{display:block;height:100%}.shared-stats{color:#aeb2ba;font-size:12px}
.shared-list{max-height:490px;overflow:auto;border:1px solid #343841;border-radius:8px}.shared-task{border-bottom:1px solid #343841;padding:0 9px}.shared-task:last-child{border:0}.shared-task summary{display:flex;gap:7px;align-items:center;padding:8px 0;color:#e9e7e4;font-weight:500}.shared-task summary span:first-child{font:12px Consolas,monospace;color:#ffb05c;flex:none}.shared-task summary .shared-title{flex:1}.shared-task .shared-body{padding:0 0 9px 22px;color:#b8bbc2}.shared-task .shared-body p{margin:4px 0}.shared-task .shared-body a{color:#ffb05c}.shared-task .shared-status{margin-left:auto;max-width:115px}.shared-tag{color:#abb0b8;font-size:11px;border:1px solid #4b505a;border-radius:5px;padding:1px 4px;white-space:nowrap}.shared-new{color:#ffd16b;border-color:#846128;background:#493516}.shared-history{max-height:95px;overflow:auto}.shared-empty{padding:12px;color:#abb0b8}
.shared-children{margin:0 0 8px 20px;border-left:2px solid #484c58;padding-left:7px}
__AI_CSS__@media(max-width:620px){.shared-task summary{flex-wrap:wrap}.shared-task summary .shared-title{flex-basis:calc(100% - 65px)}.shared-task .shared-status{margin-left:22px}}
</style>"""
STYLE = STYLE.replace("__AI_CSS__", SHARED_CSS)

PANEL = """<details class="shared-plan" id="shared-plan"><summary>Общие задачи пяти планов · поиск, отметки, история</summary>
<div class="shared-inner"><p class="shared-note">Тексты и исходные статусы берутся из планов проекта. Изменения статусов здесь — личные отметки в этом браузере. Для переноса на телефон сохрани файл через «Экспорт» и загрузи его через «Импорт».</p>
<div class="shared-controls"><input id="shared-search" type="search" placeholder="Поиск задачи"><select id="shared-plan-filter" aria-label="План"></select><select id="shared-status-filter" aria-label="Статус"><option value="all">Все статусы</option><option value="todo">Не начато</option><option value="doing">В работе</option><option value="done">Готово</option></select><select id="shared-priority-filter" aria-label="Приоритет"><option value="all">Любой приоритет</option><option value="P0">P0</option><option value="P1">P1</option><option value="P2">P2</option><option value="P3">P3</option><option value="none">Без приоритета</option></select>__AI_CONTROLS__<button id="shared-expand">Развернуть всё</button><button id="shared-collapse">Свернуть всё</button><button id="shared-export">Экспорт</button><button id="shared-import">Импорт</button><input id="shared-file" type="file" accept=".json,application/json" hidden></div>
<div class="shared-chart" id="shared-chart" aria-label="Состояние задач"></div><div class="shared-stats" id="shared-stats"></div><div class="shared-list" id="shared-list"></div>
<details><summary>История и структура данных</summary><div id="shared-timeline" class="shared-history"></div><p class="shared-note">Планы карты и расписания (HTML) + планы UI/UX и Telegram (Markdown) → единая собранная модель <code>docs/plan-model.json</code> → пять страниц. Личные отметки и их история хранятся в браузере и переносятся экспортом.</p></details>
<div class="shared-note" id="shared-storage-note"></div></div></details>"""
PANEL = PANEL.replace("__AI_CONTROLS__", SHARED_CONTROLS)

SCRIPT = r"""<script id="shared-plan-script">
(()=>{
const MODEL=JSON.parse(document.getElementById('shared-plan-data').textContent);
const PAGE='__PAGE__', KEY='aion-shared-plan-ledger-v1', VALID=new Set(MODEL.items.map(i=>i.key));
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let ledger={schema_version:1,statuses:{},history:[]};
try{const saved=JSON.parse(localStorage.getItem(KEY)||'null');if(saved&&saved.schema_version===1&&saved.statuses&&Array.isArray(saved.history))ledger=saved}catch(_e){}
const $=id=>document.getElementById(id), plan=k=>MODEL.plans.find(p=>p.key===k);
function nativeStatus(i){try{if(i.plan==='ui')return JSON.parse(localStorage.getItem('aion-ui-ux-plan-status-v1')||'{}')[i.id.replace('UI #','')];if(i.plan==='tg')return JSON.parse(localStorage.getItem('aion-telegram-plan-status-v1')||'{}')[i.id.replace('TG ','')]}catch(_e){}return null}
function status(i){return ledger.statuses[i.key]||nativeStatus(i)||i.status}
window.planState={status,statusByKey:k=>{const i=MODEL.items.find(x=>x.key===k);return i?status(i):null},model:MODEL};
function save(){try{localStorage.setItem(KEY,JSON.stringify(ledger));$('shared-storage-note').textContent='Личные отметки сохранены в этом браузере.';return true}catch(_e){$('shared-storage-note').textContent='Браузер запретил сохранение. Экспортируй отметки перед закрытием страницы.';return false}}
function setStatus(key,next,origin='план'){const i=MODEL.items.find(x=>x.key===key);if(!i||!['todo','doing','done'].includes(next))return;
  const old=status(i);if(old===next)return;ledger.statuses[key]=next;ledger.history.push({key,from:old,to:next,at:new Date().toISOString(),origin});
  if(i.plan==='ui'||i.plan==='tg'){const legacy=i.plan==='ui'?'aion-ui-ux-plan-status-v1':'aion-telegram-plan-status-v1';try{const obj=JSON.parse(localStorage.getItem(legacy)||'{}');obj[i.id.replace(/^UI #|^TG /,'')]=next;localStorage.setItem(legacy,JSON.stringify(obj))}catch(_e){}}
  save();draw();window.dispatchEvent(new Event('plan-shared-change'));
}
window.planSharedChange=setStatus;
window.planSharedReset=planKey=>{for(const i of MODEL.items)if(i.plan===planKey)delete ledger.statuses[i.key];save();draw();window.dispatchEvent(new Event('plan-shared-change'))};
__AI_JS__
const numberSort=(a,b)=>{const aa=a.id.match(/\d+/g).map(Number),bb=b.id.match(/\d+/g).map(Number);for(let x=0;x<Math.max(aa.length,bb.length);x++){const d=(bb[x]||0)-(aa[x]||0);if(d)return d}return 0};
const human=s=>({todo:'Не начато',doing:'В работе',done:'Готово'}[s]||s);
function rows(){const q=$('shared-search').value.trim().toLocaleLowerCase('ru'),p=$('shared-plan-filter').value,s=$('shared-status-filter').value,pr=$('shared-priority-filter').value;
  return MODEL.items.filter(i=>(p==='all'||p===i.plan)&&(s==='all'||status(i)===s)&&(pr==='all'||(pr==='none'?!i.priority:i.priority===pr))&&aiMatch(i)&&(!q||`${i.key} ${i.title} ${i.text} ${i.who}`.toLocaleLowerCase('ru').includes(q))).sort((a,b)=>{const newest=MODEL.items.find(i=>i.key===MODEL.latest&&status(i)==='todo');const order=i=>i.plan===newest?.plan?-1:MODEL.plans.findIndex(x=>x.key===i.plan);return order(a)-order(b)||numberSort(a,b)});}
function body(i){const hist=[...(i.history||[]),...ledger.history.filter(x=>x.key===i.key)].sort((a,b)=>String(b.at||'').localeCompare(String(a.at||'')));
  const child=MODEL.items.filter(x=>x.parent===i.key).map(x=>`<a href="${esc(plan(x.plan).page)}#task-${esc(x.key.replace(':','-'))}">${esc(x.id)}</a>`).join(', ');
  return `<div class="shared-body"><p>${esc(i.text)}</p><p>Исполнитель: ${esc(i.who||'не указан')}${i.priority?' · приоритет '+esc(i.priority):' · приоритет не указан'}</p>
  ${i.added_at?`<p>Добавлено: ${esc(i.added_at)}</p>`:''}${i.changed_at?`<p>Изменено в исходнике: ${esc(i.changed_at)}</p>`:''}
  ${i.dependencies_text?`<p>Зависимости в исходном плане: ${esc(i.dependencies_text)}</p>`:''}${i.depends_on?.length?`<p>Зависит от: ${i.depends_on.map(key=>{const t=MODEL.items.find(x=>x.key===key);return t?`<a href="${esc(plan(t.plan).page)}#task-${esc(key.replace(':','-'))}">${esc(key)}</a>`:esc(key)}).join(', ')}</p>`:''}
  ${i.parent?`<p>Родитель: ${esc(i.parent)}</p>`:''}${child?`<p>Дочерние: ${child}</p>`:''}
  ${aiBlock(i)}<p><a href="${esc(plan(i.plan).page)}#task-${esc(i.key.replace(':','-'))}">Открыть в ${esc(plan(i.plan).title)}</a></p>
  <div class="shared-history">${hist.length?hist.map(h=>`<div>${esc(h.at||'')} · ${h.event?esc(h.event):`${esc(h.from||'')} → ${esc(h.to||'')}`} ${esc(h.origin||'')}</div>`).join(''):'История изменений пока пуста'}</div></div>`}
function draw(){const all=MODEL.items,c={todo:0,doing:0,done:0};all.forEach(i=>c[status(i)]++);$('shared-chart').innerHTML=[['done','#5fd38d'],['doing','#ff8c1a'],['todo','#69707c']].map(([s,color])=>`<span style="width:${100*c[s]/all.length}%;background:${color}" title="${human(s)}: ${c[s]}"></span>`).join('');$('shared-stats').textContent=`${all.length} задач · ${c.done} готово · ${c.doing} в работе · ${c.todo} не начато`;
  const timeline=[...MODEL.items.flatMap(i=>(i.history||[]).map(h=>({...h,key:i.key}))),...ledger.history].sort((a,b)=>String(b.at||'').localeCompare(String(a.at||''))).slice(0,12);
  $('shared-timeline').innerHTML=timeline.length?timeline.map(h=>`<div>${esc(h.at)} · ${esc(h.key)} · ${h.event?esc(h.event):`${human(h.from)} → ${human(h.to)}`}</div>`).join(''):'Изменений пока нет.';
  const found=rows(),byKey=new Map(found.map(i=>[i.key,i])),shown=new Set();
  function card(i,path=new Set()){if(path.has(i.key)||shown.has(i.key))return '';shown.add(i.key);const next=new Set(path);next.add(i.key);const children=found.filter(x=>x.parent===i.key).map(x=>card(x,next)).join('');
    return `<details class="shared-task" id="task-${esc(i.key.replace(':','-'))}"><summary><span>${esc(i.key)}</span><span class="shared-title">${esc(i.title)}</span>${i.key===MODEL.latest&&status(i)==='todo'?'<span class="shared-tag shared-new">НОВОЕ</span>':''}${i.priority?`<span class="shared-tag">${esc(i.priority)}</span>`:''}${aiTag(i)}<select class="shared-status" data-key="${esc(i.key)}" aria-label="Статус ${esc(i.key)}">${['todo','doing','done'].map(s=>`<option value="${s}" ${s===status(i)?'selected':''}>${human(s)}</option>`).join('')}</select></summary>${body(i)}${children?`<div class="shared-children">${children}</div>`:''}</details>`}
  const roots=found.filter(i=>!byKey.has(i.parent)),tree=roots.map(i=>card(i)).join('')+found.filter(i=>!shown.has(i.key)).map(i=>card(i)).join('');$('shared-list').innerHTML=found.length?tree:'<div class="shared-empty">Совпадений нет</div>';
  $('shared-list').querySelectorAll('.shared-status').forEach(el=>{el.onclick=e=>e.stopPropagation();el.onchange=e=>{e.stopPropagation();setStatus(el.dataset.key,el.value,'общий обзор')}});
}
const pf=$('shared-plan-filter');pf.innerHTML='<option value="all">Все планы</option>'+MODEL.plans.map(p=>`<option value="${esc(p.key)}">${esc(p.title)}</option>`).join('');pf.value=PAGE==='all'?'all':PAGE;
['shared-search','shared-plan-filter','shared-status-filter','shared-priority-filter'].forEach(id=>$(id).addEventListener(id==='shared-search'?'input':'change',draw));
$('shared-expand').onclick=()=>$('shared-list').querySelectorAll('details').forEach(x=>x.open=true);$('shared-collapse').onclick=()=>$('shared-list').querySelectorAll('details').forEach(x=>x.open=false);
$('shared-export').onclick=()=>{const blob=new Blob([JSON.stringify(ledger,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='aion-plan-status-backup.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
$('shared-import').onclick=()=>$('shared-file').click();$('shared-file').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{const data=JSON.parse(await file.text());if(data.schema_version!==1||!data.statuses||!Array.isArray(data.history))throw Error('Неверный формат');for(const [key,s] of Object.entries(data.statuses))if(VALID.has(key)&&['todo','doing','done'].includes(s))ledger.statuses[key]=s;ledger.history.push(...data.history.filter(x=>VALID.has(x.key)&&x.at&&x.to));save();draw();window.dispatchEvent(new Event('plan-shared-change'))}catch(err){$('shared-storage-note').textContent='Импорт не выполнен: '+err.message}e.target.value=''};
document.addEventListener('change',e=>{const el=e.target;if(!el.matches('.task .status'))return;const card=el.closest('.task'),id=card?.dataset.task||card?.dataset.id;if(id&&['ui','tg'].includes(PAGE))setStatus(`${PAGE}:${id}`,el.value,'страница плана')},true);
window.addEventListener('storage',e=>{if(e.key===KEY){try{const value=JSON.parse(e.newValue);if(value?.schema_version===1)ledger=value}catch(_e){}draw();window.dispatchEvent(new Event('plan-shared-change'))}});
window.addEventListener('plan-shared-change',()=>{if(['all','ui','tg'].includes(PAGE)&&typeof window.render==='function')window.render()});
aiInit();draw();if(['all','ui','tg'].includes(PAGE)&&typeof window.render==='function')window.render();
})();
</script>"""
SCRIPT = SCRIPT.replace("__AI_JS__", SHARED_JS)


def inject_shared_explorer(page_html: str, model: dict, current: str) -> str:
    """Idempotently add the shared view without changing a plan's own task markup."""
    page_html = re.sub(r"<!--SHARED_START-->.*?<!--SHARED_END-->\r?\n?", "", page_html, flags=re.S)
    page_html = re.sub(r"<!--SHARED_SCRIPT_START-->.*?<!--SHARED_SCRIPT_END-->\r?\n?", "", page_html, flags=re.S)
    payload = json.dumps(model, ensure_ascii=False).replace("<", "\\u003c")
    block = "<!--SHARED_START-->" + STYLE + PANEL + "<!--SHARED_END-->"
    script = ("<!--SHARED_SCRIPT_START-->" + f'<script type="application/json" id="shared-plan-data">{payload}</script>'
              + SCRIPT.replace("__PAGE__", current) + "<!--SHARED_SCRIPT_END-->")
    if "<!--/NAV-->" not in page_html:
        raise ValueError("Plan navigation marker missing")
    page_html = page_html.replace("<!--/NAV-->", "<!--/NAV-->\n" + block, 1)
    return page_html.replace("</body>", script + "\n</body>", 1)
