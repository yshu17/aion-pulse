"""Build docs/index.html — the master plan: every plan's steps in one page — and refresh the plan bar on all pages.

Sources (the plans stay the single source of truth, this page only collects them):
  docs/map-poi-plan.html        STEPS3 array (map v3–v4, numbers = PAIR.md task numbers)
  docs/schedule-notify-plan.html STEPS array (SN-1 …)
  UI_UX_IMPROVEMENT_PLAN.md      tasks and owners, via tools/build_ui_ux_plan.py
  docs/telegram-bridge-plan.md   tasks, via tools/build_telegram_plan.py
Run after changing any plan:  python tools/build_master_plan.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_telegram_plan  # noqa: E402
import build_ui_ux_plan  # noqa: E402
from plan_common import MASTER, PLANS, RESOURCES, nav_html, owners, set_nav  # noqa: E402

FIELD = re.compile(r'(\w+):"((?:[^"\\]|\\.)*)"')


def js_steps(page: str, name: str) -> list[dict[str, str]]:
    """The objects of `const NAME=[ {t:"…",who:"…",d:"…",s:"…"}, … ];` in a plan page, in order."""
    match = re.search(rf"const {name}=\[(.*?)\n\];", page, re.S)
    if not match:
        raise SystemExit(f"no const {name}=[…] in the page")
    steps = []
    for line in match.group(1).splitlines():
        if line.strip().startswith("{t:"):
            steps.append({k: v.replace('\\"', '"') for k, v in FIELD.findall(line)})
    return steps


def collect() -> list[dict]:
    items: list[dict] = []
    map_page = (DOCS / "map-poi-plan.html").read_text(encoding="utf-8")
    for i, st in enumerate(js_steps(map_page, "STEPS3"), 1):
        items.append({"plan": "map", "id": str(i), "title": st["t"], "who": st.get("who", ""), "text": st.get("d", ""),
                      "status": st.get("s", "todo")})
    sn_page = (DOCS / "schedule-notify-plan.html").read_text(encoding="utf-8")
    for i, st in enumerate(js_steps(sn_page, "STEPS"), 1):
        items.append({"plan": "sn", "id": f"SN-{i}", "title": st["t"], "who": st.get("who", ""),
                      "text": st.get("d", ""), "status": st.get("s", "todo")})
    ui_lines = build_ui_ux_plan.SOURCE.read_text(encoding="utf-8").splitlines()
    ui_owners = build_ui_ux_plan.task_owners(ui_lines)
    ui_status = build_ui_ux_plan.task_status(ui_lines)
    for task in build_ui_ux_plan.task_rows(ui_lines):
        items.append({"plan": "ui", "id": f"UI #{task['id']}", "title": task["problem"],
                      "who": ui_owners.get(task["id"], ""), "text": f"{task['priority']} · {task['solution']}",
                      "status": ui_status.get(task["id"], ("todo", ""))[0]})
    tasks, _stages, _deferred = build_telegram_plan.parse_plan(build_telegram_plan.SOURCE.read_text(encoding="utf-8"))
    for task in tasks:
        who, _sep, title = task["title"].partition(" · ")
        if not owners(who):
            who, title = "Claude", task["title"]
        items.append({"plan": "tg", "id": f"TG {task['id']}", "title": title, "who": who, "text": "",
                      "status": task["initial"]})
    for item in items:
        item["owners"] = owners(item["who"])
    return items


def main() -> int:
    items = collect()
    plans = [{"key": k, "title": t, "page": p, "gate": g} for k, t, p, g in PLANS]
    needs = [{"plan": key, "title": title, "detail": detail, "link": link}
             for key, *_ in PLANS for kind, title, detail, link in RESOURCES.get(key, []) if kind == "need"]
    data = json.dumps({"plans": plans, "items": items, "needs": needs, "built": date.today().strftime("%d.%m.%Y")},
                      ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.replace("__NAV__", f"<!--NAV-->{nav_html('master')}<!--/NAV-->").replace("__DATA__", data)
    (DOCS / MASTER).write_text(page, encoding="utf-8")
    for key, _title, name, _gate in PLANS:
        path = DOCS / name
        text = path.read_text(encoding="utf-8")
        updated = set_nav(text, key)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
    counts = {k: sum(1 for i in items if i["plan"] == k) for k, *_ in PLANS}
    print(f"{DOCS / MASTER}: {len(items)} steps {counts}")
    return 0


TEMPLATE = r'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Мастер-план</title>
<style>
:root{--bg:#141519;--surface:#1c1e24;--surface2:#262931;--border:#363a45;--text:#e9e7e4;--muted:#8c919c;--accent:#ff8c1a;--ok:#5fd38d;--warn:#e5484d;--info:#4aa3ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:30px 0 12px}
.sub,.tag{color:var(--muted)}.tag{font-size:12px}
a{color:#ffb05c}
.plans{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}
.plan{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:6px}
.plan h3{margin:0;font-size:16px}.plan h3 a{color:var(--text);text-decoration:none}.plan h3 a:hover{color:var(--accent)}
.gate{display:inline-block;font-size:12px;padding:1px 8px;border-radius:7px;border:1px solid var(--border);color:var(--muted)}
.gate.go{border-color:#375b48;color:var(--ok)}
.bar{height:8px;background:var(--surface2);border-radius:8px;overflow:hidden}.bar i{display:block;height:100%;background:var(--accent)}
.split{display:flex;gap:10px;flex-wrap:wrap;font-size:13px;color:var(--muted)}.split b{color:var(--text)}
.total{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:14px 0 0}
.total div{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:10px 12px}.total b{display:block;font-size:22px}
@media(max-width:640px){.total{grid-template-columns:repeat(2,1fr)}}
.you{display:grid;gap:8px}.you div{border-left:3px solid var(--accent);background:var(--surface);padding:8px 12px;border-radius:0 8px 8px 0}
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
.chip{padding:4px 10px;border-radius:8px;background:var(--surface2);border:1px solid var(--border);cursor:pointer;font-size:13px;user-select:none}
.chip.on{background:#3a2a12;border-color:var(--accent);color:var(--accent)}
input[type=search],select{background:var(--surface2);border:1px solid var(--border);border-radius:8px;color:var(--text);padding:6px 10px;font:inherit}
input[type=search]{flex:1;min-width:180px}
.list{background:var(--surface);border:1px solid var(--border);border-radius:12px}
.group{padding:8px 12px 4px;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--border)}
.item{display:grid;grid-template-columns:22px 76px minmax(0,1fr) auto;gap:10px;padding:9px 12px;border-bottom:1px solid var(--border);align-items:start}
.item:last-child{border-bottom:0}.item.done{opacity:.55}
.mark{text-align:center;font-size:16px}.id{font:12px Consolas,monospace;color:var(--muted);padding-top:3px}
.item .t{font-weight:600}.item .d{font-size:13px;color:var(--muted);overflow-wrap:anywhere}
.who{display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end}
.who span{font-size:12px;padding:1px 7px;border-radius:7px;background:var(--surface2);border:1px solid var(--border)}
.who .c{border-color:#5a4024}.who .k{border-color:#24425a}.who .y{border-color:#375b48}
@media(max-width:640px){.item{grid-template-columns:22px minmax(0,1fr)}.item .id{display:none}.who{grid-column:2;justify-content:flex-start}}
.empty{padding:20px;text-align:center;color:var(--muted)}
code{background:var(--surface2);border-radius:4px;padding:0 4px;font-size:13px}
</style>
</head>
<body>
<div class="wrap">
__NAV__
  <h1>Мастер-план</h1>
  <div class="sub">Aion Chat Watcher · все планы в одном месте · собран <span id="built"></span> из самих планов (<code>python tools/build_master_plan.py</code>) — правки делаются в планах, здесь только сводка</div>
  <div class="total" id="total"></div>

  <h2>Планы</h2>
  <div class="plans" id="plans"></div>

  <h2>Ждёт тебя</h2>
  <div class="you" id="you"></div>

  <h2>Все шаги</h2>
  <div class="tools">
    <span id="planChips"></span>
    <span id="ownerChips"></span>
    <select id="status"><option value="open">Открытые</option><option value="all">Все</option><option value="done">Готовые</option></select>
    <input id="q" type="search" placeholder="Поиск по шагам…">
  </div>
  <div class="tag" id="shown" style="margin-bottom:6px"></div>
  <div class="list" id="list"></div>
</div>
<script>
const DATA=__DATA__;
const MARK={done:["✓","#5fd38d"],doing:["▶","#ff8c1a"],todo:["○","#8c919c"]};
const OWN={"Claude":"c","Кодекс":"k","Ты":"y"};
const esc=v=>String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const md=v=>esc(v).replace(/`([^`]+)`/g,"<code>$1</code>");
const KEY="aion-master-plan-filters-v1";
let f={plans:[],owners:[],status:"open",q:""};
try{Object.assign(f,JSON.parse(localStorage.getItem(KEY)||"{}"))}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(f))}catch(e){}};
const plan=k=>DATA.plans.find(p=>p.key===k);
document.getElementById("built").textContent=DATA.built;
function totals(){const all=DATA.items,done=all.filter(i=>i.status==="done").length,open=all.length-done;
  const mine=o=>all.filter(i=>i.status!=="done"&&i.owners.includes(o)).length;
  document.getElementById("total").innerHTML=[[`${done} / ${all.length}`,"шагов готово"],[open,"открыто"],[mine("Claude"),"открыто у Claude"],[mine("Кодекс"),"открыто у Кодекса"]]
    .map(([b,s])=>`<div><b>${b}</b><span class="tag">${s}</span></div>`).join("");}
function plans(){document.getElementById("plans").innerHTML=DATA.plans.map(p=>{const its=DATA.items.filter(i=>i.plan===p.key),
  done=its.filter(i=>i.status==="done").length,pct=its.length?Math.round(done/its.length*100):0,
  open=o=>its.filter(i=>i.status!=="done"&&i.owners.includes(o)).length,doing=its.filter(i=>i.status==="doing");
  return `<div class="plan"><h3><a href="${p.page}">${esc(p.title)} →</a></h3><span class="gate ${p.gate==="в работе"?"go":""}">${esc(p.gate)}</span>
  <div class="bar"><i style="width:${pct}%"></i></div><div class="split"><span><b>${done}</b> из ${its.length} готово</span><span>Claude <b>${open("Claude")}</b></span><span>Кодекс <b>${open("Кодекс")}</b></span><span>ты <b>${open("Ты")}</b></span></div>
  ${doing.length?`<div class="tag">в работе: ${doing.map(i=>esc(i.id+". "+i.title)).join("; ")}</div>`:""}</div>`}).join("");}
function you(){const gates=DATA.plans.filter(p=>p.gate!=="в работе").map(p=>`<div><b>${esc(p.title)}</b> — ${esc(p.gate)} · <a href="${p.page}">открыть план</a></div>`);
  const steps=DATA.items.filter(i=>i.status!=="done"&&i.owners.includes("Ты")).map(i=>`<div><b>${esc(plan(i.plan).title)} · ${esc(i.id)}.</b> ${md(i.title)}</div>`);
  const needs=DATA.needs.map(n=>`<div style="border-color:#4aa3ff"><b>${esc(plan(n.plan).title)} · файл / ресурс:</b> ${n.link?`<a href="${esc(n.link)}">${esc(n.title)}</a>`:esc(n.title)} — <span class="tag">${esc(n.detail)}</span></div>`);
  document.getElementById("you").innerHTML=gates.concat(steps,needs).join("")||'<div>Ничего — всё у Claude и Кодекса.</div>';}
function chips(){const pc=document.getElementById("planChips"),oc=document.getElementById("ownerChips");
  pc.innerHTML=DATA.plans.map(p=>`<span class="chip ${f.plans.includes(p.key)?"on":""}" data-p="${p.key}">${esc(p.title)}</span>`).join(" ");
  oc.innerHTML=Object.keys(OWN).map(o=>`<span class="chip ${f.owners.includes(o)?"on":""}" data-o="${o}">${o}</span>`).join(" ");
  pc.querySelectorAll("[data-p]").forEach(c=>c.onclick=()=>{const k=c.dataset.p;f.plans=f.plans.includes(k)?f.plans.filter(x=>x!==k):[...f.plans,k];save();render()});
  oc.querySelectorAll("[data-o]").forEach(c=>c.onclick=()=>{const k=c.dataset.o;f.owners=f.owners.includes(k)?f.owners.filter(x=>x!==k):[...f.owners,k];save();render()});}
function list(){const q=f.q.trim().toLocaleLowerCase("ru");
  const its=DATA.items.filter(i=>(!f.plans.length||f.plans.includes(i.plan))&&(!f.owners.length||i.owners.some(o=>f.owners.includes(o)))
    &&(f.status==="all"||(f.status==="done")===(i.status==="done"))&&(!q||`${i.id} ${i.title} ${i.text} ${i.who}`.toLocaleLowerCase("ru").includes(q)));
  document.getElementById("shown").textContent=`Показано ${its.length} из ${DATA.items.length}`;
  if(!its.length){document.getElementById("list").innerHTML='<div class="empty">Ничего не найдено</div>';return}
  let html="",cur="";
  its.forEach(i=>{if(i.plan!==cur){cur=i.plan;const p=plan(cur);html+=`<div class="group"><a href="${p.page}">${esc(p.title)}</a></div>`}
    const m=MARK[i.status]||MARK.todo;
    html+=`<div class="item ${i.status==="done"?"done":""}"><div class="mark" style="color:${m[1]}">${m[0]}</div><div class="id">${esc(i.id)}</div>
      <div><div class="t">${md(i.title)}</div>${i.text?`<div class="d">${md(i.text)}</div>`:""}</div>
      <div class="who">${(i.owners.length?i.owners:["—"]).map(o=>`<span class="${OWN[o]||""}">${o}</span>`).join("")}</div></div>`});
  document.getElementById("list").innerHTML=html;}
const st=document.getElementById("status"),qi=document.getElementById("q");st.value=f.status;qi.value=f.q;
st.onchange=()=>{f.status=st.value;save();list()};qi.oninput=()=>{f.q=qi.value;save();list()};
function render(){totals();plans();you();chips();list()}
render();
</script>
</body>
</html>
'''


if __name__ == "__main__":
    sys.exit(main())
