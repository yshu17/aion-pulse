"""Embed one generated, offline-capable task explorer in all five plan pages.

The source plans remain authoritative. The browser ledger contains personal status
overrides and history; exporting it is the way to move those notes to another device.
"""

from __future__ import annotations

import json
import re

from plan_ai_view import SHARED_CONTROLS, SHARED_CSS, SHARED_JS
import plan_states
import plan_verification


# motion tokens in ms (tools: application-motion-designer contract); CSS reads them as variables, JS as constants
MOTION = {"fast": 120, "open": 160, "close": 140, "flash": 600}

STYLE = r"""<style id="shared-plan-style">
.shared-plan{margin:12px 0 18px;border:1px solid #424650;border-radius:10px;background:#1c1e24;color:#e9e7e4;font:13px/1.45 'Segoe UI',system-ui,sans-serif}
.shared-plan summary{cursor:pointer;padding:10px 12px;font-weight:650;color:#ffb05c}
.shared-inner{padding:0 12px 12px}.shared-note{color:#aeb2ba;margin:0 0 9px}
.shared-controls{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.shared-controls input,.shared-controls select,.shared-controls button,.shared-status{font:inherit;color:#e9e7e4;background:#262931;border:1px solid #484c58;border-radius:7px;padding:7px;min-height:36px}
.shared-controls input[type=search]{flex:1;min-width:150px}.shared-controls button{cursor:pointer}.shared-controls button:hover{border-color:#ff8c1a}
.shared-chart{display:flex;height:11px;border-radius:9px;overflow:hidden;background:#353841;margin:9px 0 4px}.shared-chart span{display:block;height:100%}.shared-stats{color:#aeb2ba;font-size:12px}
.shared-list{max-height:490px;overflow:auto;border:1px solid #343841;border-radius:8px}.shared-task{border-bottom:1px solid #343841;padding:0 9px}.shared-task:last-child{border:0}.shared-task summary{display:flex;gap:7px;align-items:center;padding:8px 0;color:#e9e7e4;font-weight:500}.shared-task summary span:first-child{font:12px Consolas,monospace;color:#ffb05c;flex:none}.shared-task summary .shared-title{flex:1}.shared-task .shared-body{padding:0 0 9px 22px;color:#b8bbc2}.shared-task .shared-body p{margin:4px 0}.shared-task .shared-body a{color:#ffb05c}.shared-task .shared-status{margin-left:auto;max-width:115px}.shared-tag{color:#abb0b8;font-size:11px;border:1px solid #4b505a;border-radius:5px;padding:1px 4px;white-space:nowrap}.shared-new{color:#ffd16b;border-color:#846128;background:#493516}.shared-history{max-height:95px;overflow:auto}.shared-empty{padding:12px;color:#abb0b8}
.shared-children{margin:0 0 8px 20px;border-left:2px solid #484c58;padding-left:7px}
.shared-check{width:16px;height:16px;flex:none;cursor:pointer;accent-color:#5fd38d}
.shared-cancelled .shared-title{text-decoration:line-through}
.shared-controls>*{max-width:100%;min-width:0}
.shared-plan{--pm-fast:__M_FAST__ms;--pm-open:__M_OPEN__ms;--pm-flash:__M_FLASH__ms;--pm-out:cubic-bezier(.2,.7,.2,1)}
.shared-controls button,.shared-controls input,.shared-controls select,.shared-status{transition:border-color var(--pm-fast) ease}
.shared-task[open]>.shared-body{animation:shared-open var(--pm-open) var(--pm-out)}
.shared-flash{animation:shared-flash var(--pm-flash) var(--pm-out)}
@keyframes shared-open{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
@keyframes shared-flash{from{box-shadow:inset 3px 0 0 var(--flash);background:color-mix(in srgb,var(--flash) 18%,transparent)}to{box-shadow:inset 3px 0 0 transparent;background:transparent}}
@media (prefers-reduced-motion:reduce){.shared-plan *{animation:none!important;transition:none!important}}
__STATE_CSS__
__AI_CSS__@media(max-width:620px){.shared-task summary{flex-wrap:wrap}.shared-task summary .shared-title{flex-basis:calc(100% - 65px)}.shared-task .shared-status{margin-left:22px}}
</style>"""
STATE_CSS = "".join(f".shared-st-{key}{{color:{color}}}" for key, _label, color in plan_states.STATES)
STATE_CSS += ".shared-vf{font-size:11px;line-height:1;padding:2px 6px;border-radius:9px;border:1px solid currentColor;white-space:nowrap;flex:none}"
STATE_CSS += "".join(f".shared-vf-{key}{{color:{color}}}" for key, _label, color, _mark in plan_verification.STATES)
STYLE = (STYLE.replace("__STATE_CSS__", STATE_CSS).replace("__AI_CSS__", SHARED_CSS)
         .replace("__M_FAST__", str(MOTION["fast"])).replace("__M_OPEN__", str(MOTION["open"]))
         .replace("__M_FLASH__", str(MOTION["flash"])))

PANEL = """<details class="shared-plan" id="shared-plan"><summary>Общие задачи пяти планов · поиск, отметки, история</summary>
<div class="shared-inner"><p class="shared-note">Тексты и исходные статусы берутся из планов проекта. Изменения статусов здесь — личные отметки в этом браузере. Для переноса на телефон сохрани файл через «Экспорт» и загрузи его через «Импорт».</p>
<div class="shared-controls"><input id="shared-search" type="search" placeholder="Поиск задачи"><select id="shared-plan-filter" aria-label="План"></select><select id="shared-status-filter" aria-label="Статус"><option value="all">Все статусы</option><option value="todo">Не начато</option><option value="doing">В работе</option><option value="done">Готово</option></select><select id="shared-priority-filter" aria-label="Приоритет"><option value="all">Любой приоритет</option><option value="P0">P0</option><option value="P1">P1</option><option value="P2">P2</option><option value="P3">P3</option><option value="none">Без приоритета</option></select>__AI_CONTROLS__<button id="shared-expand">Развернуть всё</button><button id="shared-collapse">Свернуть всё</button><button id="shared-export">Экспорт</button><button id="shared-import">Импорт</button><button id="shared-restore" title="Вернуть отметки, какими они были до последнего импорта">Откатить импорт</button><input id="shared-file" type="file" accept=".json,application/json" hidden></div>
<div class="shared-chart" id="shared-chart" aria-label="Состояние задач"></div><div class="shared-stats" id="shared-stats"></div><div class="shared-stats" id="shared-verify-stats"></div><div class="shared-list" id="shared-list"></div>
<details><summary>История и структура данных</summary><div id="shared-timeline" class="shared-history"></div><p class="shared-note">Планы карты и расписания (HTML) + планы UI/UX и Telegram (Markdown) → единая собранная модель <code>docs/plan-model.json</code> → пять страниц. Личные отметки и их история хранятся в браузере и переносятся экспортом.</p></details>
<div class="shared-note" id="shared-storage-note"></div></div></details>"""
PANEL = PANEL.replace("__AI_CONTROLS__", SHARED_CONTROLS)
STATUS_OPTIONS = '<option value="all">Все статусы</option>' + "".join(
    f'<option value="{key}">{label}</option>' for key, label, _color in plan_states.STATES)
PRIORITY_OPTIONS = ('<option value="all">Любой приоритет</option>' + "".join(
    f'<option value="{p}">{p}</option>' for p in plan_states.PRIORITIES)
    + f'<option value="none">{plan_states.NOT_SET}</option>')
VERIFY_OPTIONS = ('<option value="all">Любое подтверждение</option>' + "".join(
    f'<option value="{key}">{label}</option>' for key, label, _color, _mark in plan_verification.STATES)
    + '<option value="none">Подтверждение не применимо</option>')
PANEL = re.sub(r'<select id="shared-status-filter".*?</select><select id="shared-priority-filter".*?</select>',
               lambda _m: '<select id="shared-status-filter" aria-label="Статус">' + STATUS_OPTIONS + '</select>'
               '<select id="shared-priority-filter" aria-label="Приоритет">' + PRIORITY_OPTIONS + '</select>'
               '<select id="shared-verify-filter" aria-label="Подтверждение">' + VERIFY_OPTIONS + '</select>',
               PANEL, count=1, flags=re.S)

SCRIPT = r"""<script id="shared-plan-script">
(()=>{
const MODEL=JSON.parse(document.getElementById('shared-plan-data').textContent);
const PAGE='__PAGE__', KEY='aion-shared-plan-ledger-v1', VALID=new Set(MODEL.items.map(i=>i.key));
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let ledger={schema_version:1,statuses:{},history:[]};
try{const saved=JSON.parse(localStorage.getItem(KEY)||'null');if(saved&&saved.schema_version===1&&saved.statuses&&Array.isArray(saved.history))ledger=saved}catch(_e){}
const $=id=>document.getElementById(id), plan=k=>MODEL.plans.find(p=>p.key===k);
const STATES=MODEL.states, LABEL=Object.fromEntries(STATES.map(s=>[s.key,s.label]));
const MOTION=__MOTION_JSON__, reduced=()=>window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let lastChanged=null;
const norm=s=>s==='todo'?'planned':(LABEL[s]?s:'planned');
const nativeOf=s=>s==='doing'||s==='done'?s:'todo';
const afterCheckbox=(cur,checked)=>checked?'done':(cur==='done'?'review':cur);
const VF=Object.fromEntries((MODEL.verification||[]).map(v=>[v.key,v]));
// verification is stored apart from the status: a task done in the data keeps its recorded state (legacy by default);
// a task the user just ticked, or sent back to review, waits for a check
const vstate=i=>{const s=status(i);if(s==='review')return 'pending';if(s!=='done')return '';return i.status==='done'?(i.verification||'legacy'):'pending'};
function nativeStatus(i){try{if(i.plan==='ui')return JSON.parse(localStorage.getItem('aion-ui-ux-plan-status-v1')||'{}')[i.id.replace('UI #','')];if(i.plan==='tg')return JSON.parse(localStorage.getItem('aion-telegram-plan-status-v1')||'{}')[i.id.replace('TG ','')]}catch(_e){}return null}
function status(i){return norm(ledger.statuses[i.key]||nativeStatus(i)||i.status)}
window.planState={status,statusByKey:k=>{const i=MODEL.items.find(x=>x.key===k);return i?nativeOf(status(i)):null},model:MODEL};
function save(){try{localStorage.setItem(KEY,JSON.stringify(ledger));$('shared-storage-note').textContent='Личные отметки сохранены в этом браузере.';return true}catch(_e){$('shared-storage-note').textContent='Браузер запретил сохранение. Экспортируй отметки перед закрытием страницы.';return false}}
function setStatus(key,next,origin='план'){const i=MODEL.items.find(x=>x.key===key);if(!i||!LABEL[next])return;
  // «Выполнено» only by the checkbox (or by a plan's own checkbox): the status list cannot set it
  const viaBox=origin==='чекбокс'||origin==='страница плана';
  if((next==='done'||status(i)==='done')&&!viaBox)return;
  const old=status(i);if(old===next)return;ledger.statuses[key]=next;ledger.history.push({key,from:old,to:next,at:new Date().toISOString(),origin});
  if(i.plan==='ui'||i.plan==='tg'){const legacy=i.plan==='ui'?'aion-ui-ux-plan-status-v1':'aion-telegram-plan-status-v1';try{const obj=JSON.parse(localStorage.getItem(legacy)||'{}');obj[i.id.replace(/^UI #|^TG /,'')]=nativeOf(next);/* the old key stays valid for the old pages: todo/doing/done only */localStorage.setItem(legacy,JSON.stringify(obj))}catch(_e){}}
  lastChanged=key;save();draw();window.dispatchEvent(new Event('plan-shared-change'));
}
window.planSharedChange=setStatus;
window.planSharedReset=planKey=>{for(const i of MODEL.items)if(i.plan===planKey)delete ledger.statuses[i.key];save();draw();window.dispatchEvent(new Event('plan-shared-change'))};
__AI_JS__
const numberSort=(a,b)=>{const aa=a.id.match(/\d+/g).map(Number),bb=b.id.match(/\d+/g).map(Number);for(let x=0;x<Math.max(aa.length,bb.length);x++){const d=(bb[x]||0)-(aa[x]||0);if(d)return d}return 0};
const human=s=>LABEL[norm(s)]||s;
function verifyMatch(i){const v=$('shared-verify-filter').value;return v==='all'||(v==='none'?!vstate(i):vstate(i)===v)}
function rows(){const q=$('shared-search').value.trim().toLocaleLowerCase('ru'),p=$('shared-plan-filter').value,s=$('shared-status-filter').value,pr=$('shared-priority-filter').value;
  return MODEL.items.filter(i=>(p==='all'||p===i.plan)&&(s==='all'||status(i)===s)&&(pr==='all'||(pr==='none'?!i.priority:i.priority===pr))&&aiMatch(i)&&verifyMatch(i)&&(!q||`${i.key} ${i.title} ${i.text} ${i.who}`.toLocaleLowerCase('ru').includes(q))).sort((a,b)=>{const newest=MODEL.items.find(i=>i.key===MODEL.latest&&status(i)==='todo');const order=i=>i.plan===newest?.plan?-1:MODEL.plans.findIndex(x=>x.key===i.plan);return order(a)-order(b)||numberSort(a,b)});}
function body(i){const hist=[...(i.history||[]),...ledger.history.filter(x=>x.key===i.key)].sort((a,b)=>String(b.at||'').localeCompare(String(a.at||'')));
  const child=MODEL.items.filter(x=>x.parent===i.key).map(x=>`<a href="${esc(plan(x.plan).page)}#task-${esc(x.key.replace(':','-'))}">${esc(x.id)}</a>`).join(', ');
  return `<div class="shared-body"><p>${esc(i.text)}</p><p>Исполнитель: ${esc(i.who||'не указан')}${' · приоритет '+esc(i.priority||'Не определён')}${vstate(i)?' · подтверждение: '+esc(VF[vstate(i)]?.label||''):''}${(i.verification_evidence||[]).length&&i.status==='done'?`<br>Доказательства: ${(i.verification_evidence||[]).map(e=>esc(e.kind+': '+e.ref)).join('; ')}`:''}</p>
  ${i.added_at?`<p>Добавлено: ${esc(i.added_at)}</p>`:''}${i.changed_at?`<p>Изменено в исходнике: ${esc(i.changed_at)}</p>`:''}
  ${i.dependencies_text?`<p>Зависимости в исходном плане: ${esc(i.dependencies_text)}</p>`:''}${i.depends_on?.length?`<p>Зависит от: ${i.depends_on.map(key=>{const t=MODEL.items.find(x=>x.key===key);return t?`<a href="${esc(plan(t.plan).page)}#task-${esc(key.replace(':','-'))}">${esc(key)}</a>`:esc(key)}).join(', ')}</p>`:''}
  ${i.parent?`<p>Родитель: ${esc(i.parent)}</p>`:''}${child?`<p>Дочерние: ${child}</p>`:''}
  ${aiBlock(i)}<p><a href="${esc(plan(i.plan).page)}#task-${esc(i.key.replace(':','-'))}">Открыть в ${esc(plan(i.plan).title)}</a></p>
  <div class="shared-history">${hist.length?hist.map(h=>`<div>${esc(h.at||'')} · ${h.event?esc(h.event):`${esc(h.from||'')} → ${esc(h.to||'')}`} ${esc(h.origin||'')}</div>`).join(''):'История изменений пока пуста'}</div></div>`}
function draw(){const all=MODEL.items,c=Object.fromEntries(STATES.map(s=>[s.key,0]));all.forEach(i=>c[status(i)]++);
  const counted=all.length-c.cancelled, pct=counted?Math.round(100*c.done/counted):0;
  $('shared-chart').innerHTML=STATES.filter(s=>c[s.key]).map(s=>`<span style="width:${100*c[s.key]/all.length}%;background:${s.color}" title="${esc(s.label)}: ${c[s.key]}"></span>`).join('');
  const vc={verified:0,legacy:0,pending:0};all.forEach(i=>{const v=vstate(i);if(v)vc[v]++});
  $('shared-verify-stats').textContent=`Подтверждено проверками: ${vc.verified} из ${c.done} выполненных · ранее отмечено без нового подтверждения ${vc.legacy} · ожидает проверки ${vc.pending}`;
  $('shared-stats').textContent=`Выполнено ${c.done} из ${counted} (${pct}%) · в работе ${c.doing} · на проверке ${c.review} · заблокировано ${c.blocked} · запланировано ${c.planned} · исследование ${c.research} · отложено ${c.deferred} · отменено ${c.cancelled}`;
  const timeline=[...MODEL.items.flatMap(i=>(i.history||[]).map(h=>({...h,key:i.key}))),...ledger.history].sort((a,b)=>String(b.at||'').localeCompare(String(a.at||''))).slice(0,12);
  $('shared-timeline').innerHTML=timeline.length?timeline.map(h=>`<div>${esc(h.at)} · ${esc(h.key)} · ${h.event?esc(h.event):`${human(h.from)} → ${human(h.to)}`}</div>`).join(''):'Изменений пока нет.';
  const found=rows(),byKey=new Map(found.map(i=>[i.key,i])),shown=new Set();
  function card(i,path=new Set()){if(path.has(i.key)||shown.has(i.key))return '';shown.add(i.key);const next=new Set(path);next.add(i.key);const children=found.filter(x=>x.parent===i.key).map(x=>card(x,next)).join('');
    return `<details class="shared-task${status(i)==='cancelled'?' shared-cancelled':''}" id="task-${esc(i.key.replace(':','-'))}"><summary><input type="checkbox" class="shared-check" data-key="${esc(i.key)}" ${status(i)==='done'?'checked':''} aria-label="Выполнено: ${esc(i.key)}"><span>${esc(i.key)}</span><span class="shared-title">${esc(i.title)}</span>${i.key===MODEL.latest&&status(i)==='planned'?'<span class="shared-tag shared-new">НОВОЕ</span>':''}<span class="shared-tag">${esc(i.priority||'Не определён')}</span>${vstate(i)?`<span class="shared-vf shared-vf-${vstate(i)}" title="${esc(VF[vstate(i)]?.label||'')}">${esc(VF[vstate(i)]?.mark||'')}</span>`:''}${aiTag(i)}<select class="shared-status shared-st-${status(i)}" data-key="${esc(i.key)}" aria-label="Статус ${esc(i.key)}">${STATES.filter(x=>x.key!=='done'||status(i)==='done').map(x=>`<option value="${x.key}" ${x.key===status(i)?'selected':''} ${x.key==='done'?'disabled':''}>${esc(x.label)}</option>`).join('')}</select></summary>${body(i)}${children?`<div class="shared-children">${children}</div>`:''}</details>`}
  const roots=found.filter(i=>!byKey.has(i.parent)),tree=roots.map(i=>card(i)).join('')+found.filter(i=>!shown.has(i.key)).map(i=>card(i)).join('');$('shared-list').innerHTML=found.length?tree:'<div class="shared-empty">Совпадений нет</div>';
  $('shared-list').querySelectorAll('.shared-status').forEach(el=>{el.onclick=e=>e.stopPropagation();el.onchange=e=>{e.stopPropagation();setStatus(el.dataset.key,el.value,'общий обзор')}});
  $('shared-list').querySelectorAll('.shared-check').forEach(el=>{el.onclick=e=>e.stopPropagation();el.onchange=e=>{e.stopPropagation();const i=MODEL.items.find(x=>x.key===el.dataset.key);const cur=status(i),next=afterCheckbox(cur,el.checked);if(next!==cur)setStatus(el.dataset.key,next,'чекбокс')}});
  if(lastChanged){const changed=MODEL.items.find(x=>x.key===lastChanged),card=changed&&$('task-'+lastChanged.replace(':','-'));
    if(card&&!reduced()){card.style.setProperty('--flash',(STATES.find(x=>x.key===status(changed))||{}).color||'#ffffff');card.classList.add('shared-flash')}lastChanged=null}
}
// closing a card: 140 ms fade; a second click while it closes finishes the first one (no stacked animations)
$('shared-list').addEventListener('click',e=>{const sum=e.target.closest('summary');if(!sum||e.target.closest('.shared-check,.shared-status'))return;
  const d=sum.parentElement;if(!d.classList.contains('shared-task')||!d.open||reduced())return;
  e.preventDefault();if(d._closing){d._closing.finish();return}
  const body=d.querySelector(':scope > .shared-body');if(!body){d.open=false;return}
  d._closing=body.animate([{opacity:1,transform:'none'},{opacity:0,transform:'translateY(-4px)'}],{duration:MOTION.close,easing:'cubic-bezier(.4,0,1,1)'});
  d._closing.onfinish=()=>{d.open=false;d._closing=null}});
const pf=$('shared-plan-filter');pf.innerHTML='<option value="all">Все планы</option>'+MODEL.plans.map(p=>`<option value="${esc(p.key)}">${esc(p.title)}</option>`).join('');pf.value=PAGE==='all'?'all':PAGE;
['shared-search','shared-plan-filter','shared-status-filter','shared-priority-filter','shared-verify-filter'].forEach(id=>$(id).addEventListener(id==='shared-search'?'input':'change',draw));
$('shared-expand').onclick=()=>$('shared-list').querySelectorAll('details').forEach(x=>x.open=true);$('shared-collapse').onclick=()=>$('shared-list').querySelectorAll('details').forEach(x=>x.open=false);
const KEYS=['aion-ui-ux-plan-status-v1','aion-telegram-plan-status-v1','aion-master-plan-filters-v1'],BACKUP='aion-backup-last-v1';
function readNative(){const o={};for(const k of KEYS){try{const v=localStorage.getItem(k);if(v!==null)o[k]=JSON.parse(v)}catch(_e){}}return o}
function snapshot(){return {at:new Date().toISOString(),ledger:JSON.parse(JSON.stringify(ledger)),native:readNative()}}
$('shared-export').onclick=()=>{const blob=new Blob([JSON.stringify({...ledger,native:readNative(),exported_at:new Date().toISOString()},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='aion-plan-status-backup.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
$('shared-import').onclick=()=>$('shared-file').click();
$('shared-restore').onclick=()=>{try{const b=JSON.parse(localStorage.getItem(BACKUP)||'null');if(!b)throw Error('резервной копии нет');ledger=b.ledger;for(const k of KEYS){if(b.native&&b.native[k]!==undefined)localStorage.setItem(k,JSON.stringify(b.native[k]));else localStorage.removeItem(k)}save();draw();window.dispatchEvent(new Event('plan-shared-change'));$('shared-storage-note').textContent='Отметки возвращены к состоянию до последнего импорта.'}catch(err){$('shared-storage-note').textContent='Откат не выполнен: '+err.message}};
$('shared-file').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{const data=JSON.parse(await file.text());if(data.schema_version!==1||!data.statuses||!Array.isArray(data.history))throw Error('Неверный формат');
  // the state before the import is kept first, so the import can be undone
  try{localStorage.setItem(BACKUP,JSON.stringify(snapshot()))}catch(_e){throw Error('не удалось сохранить резервную копию, импорт остановлен')}
  let n=0;for(const [key,s] of Object.entries(data.statuses))if(VALID.has(key)&&LABEL[norm(s)]){ledger.statuses[key]=norm(s);n++}
  ledger.history.push(...data.history.filter(x=>VALID.has(x.key)&&x.at&&x.to));
  if(data.native&&typeof data.native==='object'){for(const k of KEYS){const v=data.native[k];if(v&&typeof v==='object'){let cur={};try{cur=JSON.parse(localStorage.getItem(k)||'{}')||{}}catch(_e){}localStorage.setItem(k,JSON.stringify(k.includes('filters')?{...v,...cur}:{...cur,...v}))}}}
  save();draw();window.dispatchEvent(new Event('plan-shared-change'));$('shared-storage-note').textContent=`Импортировано отметок: ${n}. Состояние до импорта сохранено: «Откатить импорт» вернёт его.`}catch(err){$('shared-storage-note').textContent='Импорт не выполнен: '+err.message}e.target.value=''};
document.addEventListener('change',e=>{const el=e.target;if(!el.matches('.task .status'))return;const card=el.closest('.task'),id=card?.dataset.task||card?.dataset.id;if(id&&['ui','tg'].includes(PAGE))setStatus(`${PAGE}:${id}`,el.value,'страница плана')},true);
window.addEventListener('storage',e=>{if(e.key===KEY){try{const value=JSON.parse(e.newValue);if(value?.schema_version===1)ledger=value}catch(_e){}draw();window.dispatchEvent(new Event('plan-shared-change'))}});
window.addEventListener('plan-shared-change',()=>{if(['all','ui','tg'].includes(PAGE)&&typeof window.render==='function')window.render()});
aiInit();draw();if(['all','ui','tg'].includes(PAGE)&&typeof window.render==='function')window.render();
})();
</script>"""
SCRIPT = SCRIPT.replace("__AI_JS__", SHARED_JS).replace("__MOTION_JSON__", json.dumps(MOTION))


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
