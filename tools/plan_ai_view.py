"""Browser views of the AI tools & skills data (model["ai"] and item["ai"], built by tools/plan_ai_tools.py).

* SHARED_*  — the collapsible «AI Tools & Skills» block and the agent / skill filters of the shared task explorer
  embedded in every plan page (tools/plan_shared.py).
* MASTER_SECTION — the summary on the master plan: executors, skills by area, missing tools, architecture reviews,
  tasks ready for Codex, blocking dependencies. Everything is computed in the browser from the one embedded model.
"""

SHARED_CSS = r"""
.shared-ai{margin:8px 0 4px;border:1px solid #3b4050;border-radius:8px;background:#20232a;padding:0 9px}.shared-ai>summary{padding:7px 0;color:#9ec7ff;font-weight:600}
.shared-ai table{width:100%;border-collapse:collapse;font-size:12px;margin:4px 0 8px}.shared-ai td,.shared-ai th{border-bottom:1px solid #343841;padding:4px 5px;text-align:left;vertical-align:top}
.shared-ai th{color:#aeb2ba;font-weight:600}.ai-ok{color:#5fd38d}.ai-miss{color:#ff8f6b}.ai-k{display:inline-block;min-width:110px;color:#aeb2ba}
.shared-ai pre{white-space:pre-wrap;background:#16181d;border:1px solid #343841;border-radius:6px;padding:8px;font:12px/1.4 Consolas,monospace;max-height:260px;overflow:auto}
.shared-ai button{font:inherit;font-size:12px;color:#e9e7e4;background:#262931;border:1px solid #484c58;border-radius:6px;padding:4px 9px;cursor:pointer}
.shared-agent{border-color:#3d5778;color:#9ec7ff}
@media(max-width:620px){.shared-ai table,.shared-ai tbody,.shared-ai tr,.shared-ai td{display:block}.shared-ai thead{display:none}.shared-ai td{border:0;padding:2px 0}.shared-ai tr{border-bottom:1px solid #343841;padding:4px 0}}
"""

SHARED_CONTROLS = ('<select id="shared-agent-filter" aria-label="Исполнитель"><option value="all">Любой исполнитель</option>'
                   '<option value="claude">Claude Code</option><option value="codex">Codex</option><option value="joint">Совместно</option>'
                   '<option value="user">Пользователь</option><option value="codex-ready">Задачи для Codex · готовы</option>'
                   '<option value="missing">Без рекомендации</option></select>'
                   '<select id="shared-skill-filter" aria-label="Скилл"><option value="all">Любой скилл</option></select>')

SHARED_JS = r"""
const AI_SHORT={claude:'Claude',codex:'Codex',joint:'Совместно',user:'Пользователь'};
function aiMatch(i){const a=$('shared-agent-filter').value,k=$('shared-skill-filter').value,ai=i.ai||{};
  if(a==='missing'&&ai.state!=='missing')return false;
  if(a==='codex-ready'&&!(ai.state==='recommended'&&ai.handoff==='ready'&&status(i)!=='done'))return false;
  if(['claude','codex','joint','user'].includes(a)&&ai.agent!==a)return false;
  if(k!=='all'&&!(ai.skills||[]).some(r=>r.name===k))return false;return true}
function aiTag(i){const ai=i.ai||{};return ai.state==='recommended'?`<span class="shared-tag shared-agent" title="Рекомендуемый исполнитель">${esc(AI_SHORT[ai.agent])}</span>`:''}
function aiBlock(i){const ai=i.ai||{};
  if(ai.state==='retro')return `<details class="shared-ai"><summary>AI Tools &amp; Skills / Инструменты разработки</summary><p>Задача выполнена. Исполнитель по факту: ${esc(i.who||'не указан')}. Рекомендация не требуется.</p></details>`;
  if(ai.state!=='recommended')return `<details class="shared-ai"><summary>AI Tools &amp; Skills / Инструменты разработки</summary><p class="ai-miss">Рекомендации ещё нет — Claude добавит её в docs/plan-ai-tools.json (скилл project-master-planner).</p></details>`;
  const rows=ai.skills.map(r=>`<tr><td><code>${esc(r.name)}</code><br><small>${esc(r.area)}</small></td><td>${esc(r.role_label)}</td><td>${esc(r.purpose)}</td><td class="${r.available?'ai-ok':'ai-miss'}">${esc(r.availability_label)}<br><small>${esc(r.codex_label)}</small></td></tr>`).join('');
  const sp=ai.split||{},files=Object.entries(ai.files||{}).map(([w,f])=>`${esc(w)}: ${f.map(x=>`<code>${esc(x)}</code>`).join(', ')}`).join('<br>');
  const codex=ai.codex_text?`<details><summary>Задание для Codex (текст для передачи)</summary><pre>${esc(ai.codex_text)}</pre><button type="button" data-copy="${esc(i.key)}">Копировать</button></details>`:'';
  return `<details class="shared-ai"><summary>AI Tools &amp; Skills / Инструменты разработки · ${esc(ai.agent_label)}</summary>
  <p><span class="ai-k">Исполнитель</span>${esc(ai.agent_label)} · проверяет ${esc(AI_SHORT[ai.reviewer]||ai.reviewer)} · ${esc(ai.category)}</p>
  <table><thead><tr><th>Скилл</th><th>Роль</th><th>Зачем</th><th>Доступность</th></tr></thead><tbody>${rows}</tbody></table>
  <p><span class="ai-k">Проектирование</span>${esc(sp.design||'')}<br><span class="ai-k">Реализация</span>${esc(sp.build||'')}<br><span class="ai-k">Тестирование</span>${esc(sp.test||'')}<br><span class="ai-k">Утверждение</span>${esc(sp.approve||'')}</p>
  <p><span class="ai-k">Передача</span>${esc(ai.handoff_label)} · архитектура: ${esc(ai.arch_label)}</p>
  ${files?`<p><span class="ai-k">Владение файлами</span><br>${files}</p>`:''}${ai.contract?`<p><span class="ai-k">Контракт</span>${esc(ai.contract)}</p>`:''}
  <p><span class="ai-k">Готово, когда</span></p><ul>${ai.done.map(d=>`<li>${esc(d)}</li>`).join('')}</ul>
  <p><span class="ai-k">Тесты</span>${(ai.tests||[]).map(t=>`<code>${esc(t)}</code>`).join(' · ')}</p>
  ${ai.missing_tools.length?`<p class="ai-miss">Нет инструмента: ${ai.missing_tools.map(esc).join(', ')}</p>`:''}${ai.note?`<p>${esc(ai.note)}</p>`:''}${codex}</details>`}
function aiInit(){const sf=$('shared-skill-filter');sf.innerHTML='<option value="all">Любой скилл</option>'+(MODEL.ai?.skills||[]).map(k=>`<option value="${esc(k.name)}">${esc(k.title)}</option>`).join('');
  ['shared-agent-filter','shared-skill-filter'].forEach(id=>$(id).addEventListener('change',draw));
  $('shared-list').addEventListener('click',e=>{const b=e.target.closest('[data-copy]');if(!b)return;const i=MODEL.items.find(x=>x.key===b.dataset.copy);
    const done=()=>{b.textContent='Скопировано'};try{navigator.clipboard.writeText(i.ai.codex_text).then(done,()=>{b.textContent='Выдели текст и скопируй'})}catch(_e){b.textContent='Выдели текст и скопируй'}})}
"""

MASTER_SECTION = r"""<h2>AI-разработка · скиллы и исполнители</h2>
<style>
.ai-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:9px;margin:0 0 10px}.ai-tiles div{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:9px 12px}.ai-tiles b{display:block;font-size:21px}
.ai-box{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:0 12px;margin:8px 0}.ai-box>summary{cursor:pointer;padding:10px 0;font-weight:650}.ai-box[open]>summary{color:#ffb05c}
.ai-row{display:grid;grid-template-columns:96px minmax(0,1fr) auto;gap:9px;padding:6px 0;border-top:1px solid var(--border);font-size:14px}.ai-row small{color:var(--muted)}
.ai-miss{color:#ff8f6b}.ai-ok{color:var(--ok)}.ai-area{margin:6px 0 10px}.ai-area b{display:block;margin-bottom:3px}
@media(max-width:640px){.ai-row{grid-template-columns:minmax(0,1fr)}}
</style>
<p class="tag">Рекомендации Claude из <code>docs/plan-ai-tools.json</code>; доступность скиллов проверена по файлам при сборке. Подробности — в карточке задачи, блок «AI Tools &amp; Skills». Считаются только открытые задачи.</p>
<div class="ai-tiles" id="aiTiles"></div>
<div class="tools"><select id="aiAgent"><option value="all">Любой исполнитель</option><option value="claude">Claude Code</option><option value="codex">Codex</option><option value="joint">Совместно</option><option value="user">Пользователь</option></select><select id="aiSkill"><option value="all">Любой скилл</option></select></div>
<details class="ai-box" open><summary>Готово к передаче Codex <span id="aiReadyN" class="tag"></span></summary><div id="aiReady"></div></details>
<details class="ai-box"><summary>Ожидают архитектурной проверки Claude <span id="aiArchN" class="tag"></span></summary><div id="aiArch"></div></details>
<details class="ai-box"><summary>Блокирующие зависимости <span id="aiBlockN" class="tag"></span></summary><div id="aiBlock"></div></details>
<details class="ai-box"><summary>Недостающие инструменты <span id="aiMissN" class="tag"></span></summary><div id="aiMiss"></div></details>
<details class="ai-box"><summary>Навыки по направлениям</summary><div id="aiAreas"></div></details>
<details class="ai-box"><summary>Черновики DRAFT-01…06 · этапы <span id="aiDraftN" class="tag"></span></summary><div id="aiDrafts"></div></details>
<script>
document.addEventListener("DOMContentLoaded",()=>{const AI=DATA.ai||{skills:[],drafts:[]},$=id=>document.getElementById(id),st=i=>itemStatus(i);
const AG={claude:"Claude Code",codex:"Codex",joint:"Совместно",user:"Пользователь"};
$("aiSkill").innerHTML+=AI.skills.map(k=>`<option value="${esc(k.name)}">${esc(k.title)}</option>`).join("");
const link=i=>{const p=plan(i.plan);return `<a href="${p.page}">${esc(p.title)} · ${esc(i.id)}</a>`};
const row=(i,extra)=>`<div class="ai-row"><div>${link(i)}</div><div>${md(i.title)}${extra?`<br><small>${extra}</small>`:""}</div><div class="tag">${esc(i.ai.agent_label||"")}</div></div>`;
function pick(){const a=$("aiAgent").value,k=$("aiSkill").value;return DATA.items.filter(i=>st(i)!=="done"&&i.ai&&i.ai.state==="recommended"&&(a==="all"||i.ai.agent===a)&&(k==="all"||i.ai.skills.some(r=>r.name===k)))}
function fill(id,rows,empty){$(id).innerHTML=rows.join("")||`<div class="ai-row"><div class="tag">${empty}</div></div>`;$(id+"N").textContent=rows.length?`· ${rows.length}`:""}
function draw(){const open=DATA.items.filter(i=>st(i)!=="done"),its=pick(),c=a=>open.filter(i=>i.ai?.agent===a).length,miss=open.filter(i=>i.ai?.state==="missing").length;
  $("aiTiles").innerHTML=[[c("claude"),"Claude Code"],[c("codex"),"Codex"],[c("joint"),"совместно"],[c("user"),"пользователь"],[miss,"без рекомендации"]].map(([b,s])=>`<div><b>${b}</b><span class="tag">${s}</span></div>`).join("");
  fill("aiReady",its.filter(i=>i.ai.handoff==="ready").map(i=>row(i,"Текст задания — в карточке задачи, «Задание для Codex»")),"Нет задач, готовых к передаче");
  fill("aiArch",its.filter(i=>i.ai.arch_review==="pending").map(i=>row(i,esc(i.ai.handoff_label))),"Нет задач на архитектурной проверке");
  const byKey=new Map(DATA.items.map(i=>[i.key,i]));
  fill("aiBlock",its.filter(i=>(i.depends_on||[]).some(k=>byKey.has(k)&&st(byKey.get(k))!=="done")||["gated","blocked"].includes(i.ai.handoff)).map(i=>{const wait=(i.depends_on||[]).filter(k=>byKey.has(k)&&st(byKey.get(k))!=="done");return row(i,(wait.length?"ждёт: "+wait.map(esc).join(", "):"")+(["gated","blocked"].includes(i.ai.handoff)?(wait.length?" · ":"")+esc(i.ai.handoff_label):""))}),"Блокировок нет");
  const missing=AI.skills.filter(k=>!k.available);
  fill("aiMiss",missing.map(k=>{const users=its.filter(i=>i.ai.skills.some(r=>r.name===k.name));return `<div class="ai-row"><div><code>${esc(k.name)}</code></div><div>${esc(k.title)} — <span class="ai-miss">${esc(k.availability_label)}</span>${k.note?`<br><small>${esc(k.note)}</small>`:""}</div><div class="tag">${users.length} задач</div></div>`}),"Все рекомендованные инструменты найдены");
  const areas=[...new Set(AI.skills.map(k=>k.area))];
  $("aiAreas").innerHTML=areas.map(a=>`<div class="ai-area"><b>${esc(a)}</b>${AI.skills.filter(k=>k.area===a).map(k=>{const n=its.filter(i=>i.ai.skills.some(r=>r.name===k.name)).length;return `<span class="chip" title="${esc(k.availability_label)} · ${esc(k.codex_label)}"><span class="${k.available?"ai-ok":"ai-miss"}">●</span> ${esc(k.title)} · ${n}</span>`}).join(" ")}</div>`).join("");
  const dr=AI.drafts.filter(d=>d.ai.state==="recommended");
  $("aiDrafts").innerHTML=dr.map(d=>`<div class="ai-row"><div class="tag">${esc(d.id)}</div><div>${esc(d.plan_title)} · ${esc(d.title)}<br><small>${d.ai.skills.map(r=>esc(r.title)).join(", ")} · ${esc(d.ai.handoff_label)}</small></div><div class="tag">${esc(d.ai.agent_label)}</div></div>`).join("");
  $("aiDraftN").textContent=`· ${dr.length} из ${AI.drafts.length} с рекомендацией`}
["aiAgent","aiSkill"].forEach(id=>$(id).addEventListener("change",draw));window.addEventListener("plan-shared-change",draw);draw()});
</script>"""
