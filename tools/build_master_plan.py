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
import build_feature_drafts  # noqa: E402
from plan_common import MASTER, PLANS, RESOURCES, nav_html, owners, set_nav  # noqa: E402
from plan_task_meta import OLD_TASK_DATE, backfill_dates, load_task_meta, remember_known, register_new_tasks, register_source_changes, task_meta  # noqa: E402
import plan_states  # noqa: E402
import plan_verification  # noqa: E402
import plan_ai_tools  # noqa: E402
from plan_ai_view import MASTER_SECTION as AI_SECTION  # noqa: E402

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
    metadata = load_task_meta()
    map_page = (DOCS / "map-poi-plan.html").read_text(encoding="utf-8")
    for i, st in enumerate(js_steps(map_page, "STEPS3"), 1):
        items.append({"plan": "map", "id": str(i), "title": st["t"], "who": st.get("who", ""), "text": st.get("d", ""),
                      "note": st.get("note", ""), "status": st.get("s", "todo"), **task_meta(metadata, f"map:{i}")})
    sn_page = (DOCS / "schedule-notify-plan.html").read_text(encoding="utf-8")
    for i, st in enumerate(js_steps(sn_page, "STEPS"), 1):
        items.append({"plan": "sn", "id": f"SN-{i}", "title": st["t"], "who": st.get("who", ""),
                      "text": st.get("d", ""), "note": st.get("note", ""), "status": st.get("s", "todo"), **task_meta(metadata, f"sn:SN-{i}")})
    ui_lines = build_ui_ux_plan.SOURCE.read_text(encoding="utf-8").splitlines()
    ui_owners = build_ui_ux_plan.task_owners(ui_lines)
    ui_status = build_ui_ux_plan.task_status(ui_lines)
    ui_stage: dict[str, str] = {}  # task number -> id of the first stage that lists it (the old list's grouping)
    for stage in build_ui_ux_plan.stage_rows(ui_lines):
        for number in stage["tasks"]:
            ui_stage.setdefault(str(number), str(stage["id"]))
    for task in build_ui_ux_plan.task_rows(ui_lines):
        items.append({"plan": "ui", "id": f"UI #{task['id']}", "title": task["problem"],
                      "who": ui_owners.get(task["id"], ""), "text": f"{task['priority']} · {task['solution']}",
                      "note": ui_status.get(task["id"], ("todo", ""))[1], "status": ui_status.get(task["id"], ("todo", ""))[0], "priority": task["priority"],
                      "dependencies_text": task["dependencies"], "stage": ui_stage.get(task["id"], ""),
                      **task_meta(metadata, f"ui:{task['id']}")})
    tasks, _stages, _deferred = build_telegram_plan.parse_plan(build_telegram_plan.SOURCE.read_text(encoding="utf-8"))
    for task in tasks:
        who, _sep, title = task["title"].partition(" · ")
        if not owners(who):
            who, title = "Claude", task["title"]
        items.append({"plan": "tg", "id": f"TG {task['id']}", "title": title, "who": who, "text": "",
                      "note": "", "stage": str(task.get("stage", "")), "status": task["initial"], **task_meta(metadata, f"tg:{task['id']}")})
    draft_doc = build_feature_drafts.load()
    for draft in draft_doc["plans"]:
        for stage in draft.get("stages", []):
            # stages of a feature draft: investigation until the user approves the feature (status research)
            items.append({"plan": "draft", "id": stage["id"], "title": stage["title"], "who": "Claude",
                          "text": stage.get("result", ""), "note": "", "status": "research", "priority": "",
                          "added_at": draft_doc.get("added_at", ""),
                          "depends_on": [f"draft:{d}" for d in stage.get("depends_on", [])]})
    for item in items:
        item["key"] = f"{item['plan']}:{item['id'].removeprefix('UI #').removeprefix('TG ')}"
        item["priority"] = item.get("priority", "")
        item["stage"] = item.get("stage", "")
        item["dependencies_text"] = item.get("dependencies_text", "")
        item["parent"] = metadata.get("tasks", {}).get(item["key"], {}).get("parent", "")
        item["depends_on"] = metadata.get("tasks", {}).get(item["key"], {}).get("depends_on", [])
        if item["plan"] == "ui" and not item["depends_on"]:
            match = re.fullmatch(r"№\s*([\d, ]+)", item["dependencies_text"])
            if match:
                item["depends_on"] = [f"ui:{number}" for number in re.findall(r"\d+", match.group(1))]
        item["changed_at"] = metadata.get("tasks", {}).get(item["key"], {}).get("changed_at", "")
        item["history"] = metadata.get("tasks", {}).get(item["key"], {}).get("history", [])
        item["owners"] = owners(item["who"])
        item["is_new"] = item.get("is_latest", False) and item["status"] == "todo"
    keys = [item["key"] for item in items]
    if len(keys) != len(set(keys)):
        raise SystemExit("Duplicate task IDs in plan sources")
    return items


def refresh_task_meta_page(name: str) -> None:
    path = DOCS / name
    text = path.read_text(encoding="utf-8")
    meta = load_task_meta()
    payload = json.dumps({"latest": meta.get("latest", ""), "tasks": meta.get("tasks", {})},
                         ensure_ascii=False).replace("</", "<\\/")
    pattern = r"/\*TASK_META_START\*/.*?/\*TASK_META_END\*/"
    updated, count = re.subn(pattern, lambda _m: "/*TASK_META_START*/" + payload + "/*TASK_META_END*/", text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"missing task metadata markers in {path}")
    path.write_text(updated, encoding="utf-8")


def main() -> int:
    build_feature_drafts.main()
    items = collect()
    # draft stages are dated by their file, not registered as new tasks (that would move the NEW badge)
    added = register_new_tasks([item["key"] for item in items if item["plan"] != "draft"])
    changed = register_source_changes(items)
    if added or changed:
        build_ui_ux_plan.main()
        build_telegram_plan.main()
        items = collect()
    dates = {item["key"]: (OLD_TASK_DATE, "Дата создания не была записана; проставлена 08.10.2026 по решению пользователя (12.10.2026)")
             for item in items if item["plan"] != "draft"}
    dates.update({item["key"]: (item["added_at"], "Дата этапа — дата набора черновиков (feature-drafts.json)")
                  for item in items if item["plan"] == "draft" and item["added_at"]})
    known = remember_known([item["key"] for item in items if item["plan"] == "draft"])
    if backfill_dates(dates) or known:
        items = collect()
    # normalise only now: the source-change hashes above must see the raw source values
    for item in items:
        item["status"] = plan_states.normalize_status(item["status"])
        item["priority"] = plan_states.normalize_priority(item["priority"])
        item["is_new"] = item.get("is_latest", False) and item["status"] == "planned"
    # how sure we are that "done" is true: a separate state, never derived from the status alone
    verification = plan_verification.load()
    for item in items:
        item["verification"], item["verification_evidence"] = plan_verification.resolve(
            item["status"], verification["tasks"].get(item["key"]))
    plans = [{"key": k, "title": t, "page": p, "gate": g} for k, t, p, g in PLANS]
    needs = [{"plan": key, "title": title, "detail": detail, "link": link}
             for key, *_ in PLANS for kind, title, detail, link in RESOURCES.get(key, []) if kind == "need"]
    ai_data = plan_ai_tools.load()
    ai_skills = plan_ai_tools.resolve_skills(ai_data)
    plan_ai_tools.annotate(items, ai_data, ai_skills)
    model = {"schema_version": 1, "plans": plans, "items": items, "needs": needs,
             "latest": load_task_meta().get("latest", ""), "built": date.today().strftime("%d.%m.%Y"),
             "states": [{"key": k, "label": l, "color": c} for k, l, c in plan_states.STATES],
             "priorities": plan_states.PRIORITIES, "priority_not_set": plan_states.NOT_SET,
             "stages": {"ui": [{"id": str(st["id"]), "name": st["name"], "ready": st.get("ready", "")}
                               for st in build_ui_ux_plan.stage_rows(build_ui_ux_plan.SOURCE.read_text(encoding="utf-8").splitlines())],
                        "tg": [{"id": str(st["id"]), "name": st["name"]} for st in build_telegram_plan.parse_plan(
                            build_telegram_plan.SOURCE.read_text(encoding="utf-8"))[1]]},
             "verification": [{"key": k, "label": l, "color": c, "mark": m} for k, l, c, m in plan_verification.STATES],
             "ai": {"updated_at": ai_data.get("updated_at", ""), "skills": list(ai_skills.values()),
                    "drafts": plan_ai_tools.draft_items(build_feature_drafts.load(), ai_data, ai_skills)}}
    (ROOT / "docs" / "AI_SKILLS_TASK_MAPPING.md").write_text(
        plan_ai_tools.mapping_markdown(items, ai_skills, model["ai"]["drafts"]), encoding="utf-8")
    (DOCS / "plan-model.json").write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    data = json.dumps(model,
                      ensure_ascii=False).replace("</", "<\\/")
    page = (TEMPLATE.replace("__NAV__", f"<!--NAV-->{nav_html('master')}<!--/NAV-->")
            .replace("__DRAFTS__", build_feature_drafts.master_section(build_feature_drafts.load()))
            .replace("__AI__", AI_SECTION)
            .replace("__DATA__", data))
    (DOCS / MASTER).write_text(page, encoding="utf-8")
    refresh_task_meta_page("map-poi-plan.html")
    refresh_task_meta_page("schedule-notify-plan.html")
    nav_targets = [(key, DOCS / name) for key, _title, name, _gate in PLANS]
    nav_targets += [("draft", path) for path in sorted(DOCS.glob("feature-*.html")) if path.name != "feature-drafts.html"]
    for key, path in nav_targets:
        text = path.read_text(encoding="utf-8")
        updated = set_nav(text, key)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
    from plan_shared import inject_shared_explorer
    # every plan page and every feature-draft page gets the same shared Task Card (one template, plan_shared.py)
    targets = [(key, DOCS / name) for key, _title, name, _gate in PLANS]
    targets += [("draft", path) for path in sorted(DOCS.glob("feature-*.html")) if path.name != "feature-drafts.html"]
    for key, path in targets:
        path.write_text(inject_shared_explorer(path.read_text(encoding="utf-8"), model, key), encoding="utf-8")
    master_path = DOCS / MASTER
    master_path.write_text(inject_shared_explorer(master_path.read_text(encoding="utf-8"), model, "all"), encoding="utf-8")
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
.empty{padding:20px;text-align:center;color:var(--muted)}.new-badge{display:inline-block;border-radius:999px;padding:1px 8px;background:#493516;color:#ffd16b;border:1px solid #846128;font-size:10px;font-weight:800;letter-spacing:.04em}
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

  __DRAFTS__

  __AI__

  <h2>Ждёт тебя</h2>
  <div class="you" id="you"></div>

  <div class="native-list">
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
function itemStatus(i){if(window.planState)return window.planState.status(i);try{if(i.plan==="ui")return JSON.parse(localStorage.getItem("aion-ui-ux-plan-status-v1")||"{}")[i.id.replace("UI #","")]||i.status;if(i.plan==="tg")return JSON.parse(localStorage.getItem("aion-telegram-plan-status-v1")||"{}")[i.id.replace("TG ","")]||i.status}catch(e){}return i.status}
function itemIsNew(i){return i.is_latest&&itemStatus(i)==="planned"}
document.getElementById("built").textContent=DATA.built;
function totals(){const all=DATA.items,done=all.filter(i=>itemStatus(i)==="done").length,open=all.length-done;
  const verified=all.filter(i=>itemStatus(i)==="done"&&i.status==="done"&&i.verification==="verified").length;
  const mine=o=>all.filter(i=>itemStatus(i)!=="done"&&i.owners.includes(o)).length;
  document.getElementById("total").innerHTML=[[`${done} / ${all.length}`,"выполнено"],[`${verified} / ${done}`,"из выполненных подтверждено проверками"],[open,"открыто"],[mine("Claude"),"открыто у Claude"],[mine("Кодекс"),"открыто у Кодекса"]]
    .map(([b,s])=>`<div><b>${b}</b><span class="tag">${s}</span></div>`).join("");}
function plans(){document.getElementById("plans").innerHTML=DATA.plans.map(p=>{const its=DATA.items.filter(i=>i.plan===p.key),
  done=its.filter(i=>itemStatus(i)==="done").length,pct=its.length?Math.round(done/its.length*100):0,
  open=o=>its.filter(i=>itemStatus(i)!=="done"&&i.owners.includes(o)).length,doing=its.filter(i=>itemStatus(i)==="doing");
  return `<div class="plan"><h3><a href="${p.page}">${esc(p.title)} →</a></h3><span class="gate ${p.gate==="в работе"?"go":""}">${esc(p.gate)}</span>
  <div class="bar"><i style="width:${pct}%"></i></div><div class="split"><span><b>${done}</b> из ${its.length} готово</span><span>Claude <b>${open("Claude")}</b></span><span>Кодекс <b>${open("Кодекс")}</b></span><span>ты <b>${open("Ты")}</b></span></div>
  ${doing.length?`<div class="tag">в работе: ${doing.map(i=>esc(i.id+". "+i.title)).join("; ")}</div>`:""}</div>`}).join("");}
function you(){const gates=DATA.plans.filter(p=>p.gate!=="в работе").map(p=>`<div><b>${esc(p.title)}</b> — ${esc(p.gate)} · <a href="${p.page}">открыть план</a></div>`);
  const steps=DATA.items.filter(i=>itemStatus(i)!=="done"&&i.owners.includes("Ты")).map(i=>`<div><b>${esc(plan(i.plan).title)} · ${esc(i.id)}.</b> ${md(i.title)}</div>`);
  const needs=DATA.needs.map(n=>`<div style="border-color:#4aa3ff"><b>${esc(plan(n.plan).title)} · файл / ресурс:</b> ${n.link?`<a href="${esc(n.link)}">${esc(n.title)}</a>`:esc(n.title)} — <span class="tag">${esc(n.detail)}</span></div>`);
  document.getElementById("you").innerHTML=gates.concat(steps,needs).join("")||'<div>Ничего — всё у Claude и Кодекса.</div>';}
function chips(){const pc=document.getElementById("planChips"),oc=document.getElementById("ownerChips");
  pc.innerHTML=DATA.plans.map(p=>`<span class="chip ${f.plans.includes(p.key)?"on":""}" data-p="${p.key}">${esc(p.title)}</span>`).join(" ");
  oc.innerHTML=Object.keys(OWN).map(o=>`<span class="chip ${f.owners.includes(o)?"on":""}" data-o="${o}">${o}</span>`).join(" ");
  pc.querySelectorAll("[data-p]").forEach(c=>c.onclick=()=>{const k=c.dataset.p;f.plans=f.plans.includes(k)?f.plans.filter(x=>x!==k):[...f.plans,k];save();render()});
  oc.querySelectorAll("[data-o]").forEach(c=>c.onclick=()=>{const k=c.dataset.o;f.owners=f.owners.includes(k)?f.owners.filter(x=>x!==k):[...f.owners,k];save();render()});}
function list(){const q=f.q.trim().toLocaleLowerCase("ru");
  const its=DATA.items.filter(i=>(!f.plans.length||f.plans.includes(i.plan))&&(!f.owners.length||i.owners.some(o=>f.owners.includes(o)))
    &&(f.status==="all"||(f.status==="done")===(itemStatus(i)==="done"))&&(!q||`${i.id} ${i.title} ${i.text} ${i.who}`.toLocaleLowerCase("ru").includes(q)))
    .sort((a,b)=>{const newest=DATA.latest&&DATA.items.find(i=>i.key===DATA.latest&&itemStatus(i)==="planned");
      const order=i=>i.plan===newest?.plan?-1:DATA.plans.findIndex(p=>p.key===i.plan);
      const group=order(a)-order(b);if(group)return group;
      const aa=a.id.match(/\d+/g).map(Number),bb=b.id.match(/\d+/g).map(Number);
      for(let j=0;j<Math.max(aa.length,bb.length);j++){const delta=(bb[j]||0)-(aa[j]||0);if(delta)return delta}return 0});
  document.getElementById("shown").textContent=`Показано ${its.length} из ${DATA.items.length}`;
  if(!its.length){document.getElementById("list").innerHTML='<div class="empty">Ничего не найдено</div>';return}
  let html="",cur="";
  its.forEach(i=>{if(i.plan!==cur){cur=i.plan;const p=plan(cur);html+=`<div class="group"><a href="${p.page}">${esc(p.title)}</a></div>`}
    const active=itemStatus(i),m=MARK[active]||MARK.todo;
    html+=`<div class="item ${active==="done"?"done":""}"><div class="mark" style="color:${m[1]}">${m[0]}</div><div class="id">${esc(i.id)}</div>
      <div><div class="t">${md(i.title)} ${itemIsNew(i)?'<span class="new-badge">НОВОЕ</span>':""}</div>${i.added_at?`<div class="d">Добавлено: ${esc(i.added_at)}</div>`:""}${i.text?`<div class="d">${md(i.text)}</div>`:""}</div>
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
