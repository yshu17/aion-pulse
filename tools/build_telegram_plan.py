"""Build an interactive Telegram bridge plan from its Markdown source."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "telegram-bridge-plan.md"
OUTPUT = ROOT / "docs" / "telegram-bridge-plan.html"


def parse_plan(text: str) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    tasks: list[dict[str, str]] = []
    stages: dict[str, dict[str, str]] = {}
    deferred: list[str] = []
    current_stage = "0"
    future = False

    for line in text.splitlines():
        heading = re.match(r"^#{2,3}\s+(.+)$", line)
        if heading:
            title = heading.group(1).strip()
            match = re.match(r"Этап\s+(\d+)\s*[—-]\s*(.+)", title)
            if match:
                current_stage = match.group(1)
                stages[current_stage] = {"id": current_stage, "name": match.group(2).strip()}
                future = False
            elif title == "Готово":
                current_stage = "0"
                stages[current_stage] = {"id": "0", "name": "Подготовлено"}
                future = False
            elif title.startswith("Позже"):
                future = True
            else:
                future = False
            continue

        task = re.match(r"^\s*-\s+\[([ xX])\]\s+\*\*(\d+(?:\.\d+)*)\*\*\s+(.+)$", line)
        if task:
            number = task.group(2)
            stage_id = number.split(".", 1)[0]
            if stage_id not in stages:
                stages[stage_id] = {"id": stage_id, "name": "Подготовлено" if stage_id == "0" else f"Этап {stage_id}"}
            tasks.append({
                "id": number,
                "stage": stage_id,
                "title": task.group(3).strip(),
                "initial": "done" if task.group(1).lower() == "x" else "todo",
            })
            continue

        if future and line.strip().startswith("-"):
            deferred.append(line.strip()[1:].strip().rstrip("."))

    return tasks, [stages[key] for key in sorted(stages, key=int)], deferred


sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_common import set_nav  # noqa: E402
from plan_task_meta import load_task_meta, task_meta  # noqa: E402


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    tasks, stages, deferred = parse_plan(source)
    if not tasks or not stages or len({task["id"] for task in tasks}) != len(tasks):
        raise SystemExit("Telegram plan has no tasks/stages or contains duplicate task IDs")
    metadata = load_task_meta()
    for task in tasks:
        task.update(task_meta(metadata, f"tg:{task['id']}"))
    data = json.dumps({"tasks": tasks, "stages": stages, "deferred": deferred, "latest_task": metadata.get("latest")}, ensure_ascii=False).replace("</", "<\\/")
    OUTPUT.write_text(set_nav(TEMPLATE.replace("__PLAN_DATA__", data), "tg"), encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)} ({len(tasks)} tasks, {len(stages)} stages)")


TEMPLATE = r'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Telegram — интерактивный план</title>
<style>
:root{--bg:#141519;--surface:#1c1e24;--surface2:#262931;--border:#363a45;--text:#e9e7e4;--muted:#a1a5ae;--accent:#ff8c1a;--ok:#5fd38d;--warn:#f5b544;--danger:#ff8585}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 "Segoe UI",system-ui,sans-serif}.wrap{max-width:1160px;margin:auto;padding:26px 18px 50px}h1{font-size:28px;line-height:1.2;margin:0 0 7px}h2{font-size:19px;margin:28px 0 12px}h3{font-size:16px;margin:0}.sub,.muted{color:var(--muted)}a{color:#ffb05c}code{font:13px Consolas,monospace;color:#ffd09a}.head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px}.banner{margin:16px 0;border-color:#705a2b;background:#28241b}.banner b{color:#ffd16b}.hero{margin:12px 0}.bar{height:9px;background:var(--surface2);border-radius:9px;overflow:hidden;margin:9px 0 3px}.bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .25s}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin-top:13px}.stat{background:var(--surface2);border-radius:8px;padding:9px 11px}.stat b{display:block;font-size:20px}.stat span{font-size:12px;color:var(--muted)}.button{background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:8px 11px;font:inherit;cursor:pointer}.button:hover{border-color:var(--accent)}.layout{display:grid;grid-template-columns:245px minmax(0,1fr);gap:12px;align-items:start}.stages{position:sticky;top:12px}.stage{padding:10px 2px;border-bottom:1px solid var(--border)}.stage:last-child{border:0}.stage button{width:100%;background:none;border:0;color:inherit;text-align:left;padding:0;font:inherit;cursor:pointer}.stage.selected{background:#29241e;margin:0 -8px;padding:10px 9px;border-radius:8px}.stline{display:flex;justify-content:space-between;gap:8px;font-weight:600}.tag{font-size:12px;color:var(--muted)}.stage .bar{height:5px;margin:6px 0}.toolbar{display:grid;grid-template-columns:minmax(200px,1fr) 175px auto;gap:8px;margin-bottom:12px}.toolbar input,.toolbar select{min-width:0;background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:8px 10px;font:inherit}.tasks{display:grid;gap:9px}.task.done{border-color:#375b48}.task-head{display:grid;grid-template-columns:54px minmax(0,1fr) 130px 20px;align-items:center;gap:10px;cursor:pointer}.task-id{color:var(--muted);font:13px Consolas,monospace}.task-title{font-weight:600}.status{width:130px;background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:7px;padding:6px;font:13px "Segoe UI",system-ui,sans-serif}.task-detail{display:none;border-top:1px solid var(--border);margin:12px 0 0 64px;padding-top:10px;color:#d3d2d0}.task.open .task-detail{display:block}.chev{color:var(--muted)}.empty{color:var(--muted);text-align:center;padding:22px}.cols{display:grid;grid-template-columns:1fr 1fr;gap:10px}.cols .card{background:var(--surface2)}.list{margin:6px 0 0;padding-left:20px}.list li{margin:5px 0}.flow{font-family:Consolas,monospace;color:#d8c4a3;overflow-wrap:anywhere}.notice{font-size:13px;color:var(--muted);margin-top:10px}.future{display:flex;flex-wrap:wrap;gap:8px}.pill{border:1px solid var(--border);background:var(--surface2);border-radius:8px;padding:7px 10px;color:var(--muted)}.foot{margin-top:13px;color:var(--muted);font-size:12px}
@media(max-width:760px){.layout{grid-template-columns:1fr}.stages{position:static}.toolbar{grid-template-columns:1fr 1fr}.toolbar input{grid-column:1/-1}.stats{grid-template-columns:repeat(2,1fr)}}@media(max-width:520px){.wrap{padding:18px 10px}.head{display:block}.task-head{grid-template-columns:42px minmax(0,1fr) 20px}.task-head .status{grid-column:2;grid-row:2}.task-detail{margin-left:0}.toolbar{grid-template-columns:1fr}.toolbar input{grid-column:auto}.cols{grid-template-columns:1fr}}
.freshness{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin:5px 0 0 64px;font-size:12px;color:var(--muted)}.new-badge{display:inline-block;border-radius:999px;padding:1px 8px;background:#493516;color:#ffd16b;border:1px solid #846128;font-size:10px;font-weight:800;letter-spacing:.04em}
</style></head><body><main class="wrap">
<header class="head"><div><h1>Telegram: интерактивный план</h1><div class="sub">Aion Chat Watcher · исходный документ: <a href="telegram-bridge-plan.md">telegram-bridge-plan.md</a></div></div><button class="button native-only" id="reset">Сбросить статусы</button></header>
<section class="card banner"><b>Реализацию не начинать до команды пользователя «делаем».</b><div>Отправка в Telegram станет ещё одним выходом общего центра уведомлений — <a href="schedule-notify-plan.html">план расписания и уведомлений</a>, шаг SN-1; правила «не беспокоить» и источники будут общими.</div><div>Статусы на этой странице — личная отметка прогресса в браузере и не являются разрешением на разработку или отправку сообщений.</div></section>
<section class="card hero"><b id="progressText"></b><span class="tag"> · статусы сохраняются в этом браузере</span><div class="bar"><i id="progressBar"></i></div><div class="stats"><div class="stat"><b id="done">0</b><span>готово</span></div><div class="stat"><b id="doing">0</b><span>в работе</span></div><div class="stat"><b id="todo">0</b><span>не начато</span></div><div class="stat"><b id="total">0</b><span>задач в плане</span></div></div></section>
<h2 class="native-list">Этапы</h2><div class="layout native-list"><aside class="card stages" id="stages"></aside><section><div class="toolbar"><input id="search" type="search" placeholder="Поиск по задачам…"><select id="stageFilter"><option value="">Все этапы</option></select><button class="button" id="expand">Раскрыть видимые</button></div><div class="tag" id="resultCount"></div><div class="tasks" id="tasks"></div></section></div>
<h2>Схема и правила передачи</h2><div class="card"><div class="flow">Chat.log → Aion Chat Watcher → [3.Поиск группы] → пачки → закрытая группа<br>Поиск совпадений → отдельное сообщение → личка пользователя</div><div class="cols" style="margin-top:13px"><section class="card"><h3>Группа</h3><ul class="list"><li>Только канал <b>3.Поиск группы</b>, включая вариант с битой кодировкой канала.</li><li>Пачки без звука, максимум 20 сообщений за любое окно 60 секунд.</li><li>Собственный слушатель лога работает по галочке независимо от Start и вкладки.</li><li>Исторические строки не отправляются.</li></ul></section><section class="card"><h3>Личка</h3><ul class="list"><li>Только новые совпадения после Start, по одному сообщению.</li><li>Совпадения из истории не отправляются; уведомление со звуком.</li><li>Для начала нужно один раз открыть бота и отправить <code>/start</code>.</li><li>Очередь личных сообщений соблюдает ограничение Telegram на частоту отправки.</li></ul></section></div><div class="notice">Подготовленная логика пачек уже реализована в <code>watcher/tgbatch.py</code> и покрыта тестами. Остальная отправка ещё не реализована.</div></div>
<h2>Что понадобится от пользователя</h2><section class="card"><ol class="list"><li>Создать бота через <code>@BotFather</code> и получить токен.</li><li>Для группового чата создать закрытую группу, добавить бота и написать туда сообщение.</li><li>Для личных уведомлений открыть бота и отправить <code>/start</code>.</li><li>В будущем интерфейсе нажать «Найти чаты» и выбрать адресатов.</li></ol><p class="notice">Токен — пароль: хранить только в локальном <code>config.json</code>, не в Git и не вместе с exe.</p></section>
<h2>Безопасность и ограничения</h2><section class="card"><ul class="list"><li>Бот пишет только в два явно выбранных чата.</li><li>Группа должна быть закрытой: в неё передаются сообщения других игроков из выбранного канала.</li><li>При отсутствии сети строки временно копятся в ограниченной очереди до 500; при переполнении удаляются самые старые.</li><li>Ошибки Telegram и <code>429</code> обрабатываются с ожиданием, указанным сервером.</li><li>Используется стандартная библиотека Python <code>urllib</code>, без новых зависимостей.</li></ul></section>
<h2>Отложено</h2><section class="card future" id="deferred"></section>
<p class="foot">Интерактивные статусы не записываются обратно в Markdown. Для изменения исходного содержания редактируй файл и пересобирай страницу: <code>python tools/build_telegram_plan.py</code>.</p>
</main><script>
const DATA=__PLAN_DATA__;const KEY="aion-telegram-plan-status-v1";let state=load();
function load(){try{return JSON.parse(localStorage.getItem(KEY)||"{}")}catch{return {}}}function save(){localStorage.setItem(KEY,JSON.stringify(state));render()}
function esc(v){return String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]))}
function md(v){return esc(v).replace(/`([^`]+)`/g,"<code>$1</code>")}
function who(t){const m=t.title.match(/^(Claude|Кодекс) · (.+)$/);return m?{owner:m[1],title:m[2]}:{owner:"Claude",title:t.title}}
function stat(t){return window.planState?.statusByKey(`tg:${t.id}`)||state[t.id]||t.initial}function renderStages(){const box=document.getElementById("stages");box.innerHTML=DATA.stages.map(s=>{const ts=DATA.tasks.filter(t=>t.stage===s.id),done=ts.filter(t=>stat(t)==="done").length,pct=ts.length?Math.round(done/ts.length*100):0;return `<div class="stage ${document.getElementById("stageFilter").value===s.id?"selected":""}"><button data-stage="${s.id}"><div class="stline"><span>${esc(s.id==="0"?"Подготовлено":`Этап ${s.id}: ${s.name}`)}</span><span class="tag">${done}/${ts.length}</span></div><div class="bar"><i style="width:${pct}%"></i></div></button></div>`}).join("");box.querySelectorAll("[data-stage]").forEach(b=>b.onclick=()=>{document.getElementById("stageFilter").value=b.dataset.stage;render()})}
function renderTasks(){const q=document.getElementById("search").value.trim().toLocaleLowerCase("ru"),s=document.getElementById("stageFilter").value,list=DATA.tasks.filter(t=>(!q||`${t.id} ${t.title}`.toLocaleLowerCase("ru").includes(q))&&(!s||t.stage===s)).sort((a,b)=>{const aa=a.id.split(".").map(Number),bb=b.id.split(".").map(Number);return (bb[0]-aa[0])||(bb[1]||0)-(aa[1]||0)});document.getElementById("resultCount").textContent=`Показано ${list.length} из ${DATA.tasks.length}`;const box=document.getElementById("tasks");if(!list.length){box.innerHTML='<div class="card empty">Ничего не найдено</div>';return}box.innerHTML=list.map(t=>`<article class="card task ${stat(t)==="done"?"done":""}" data-id="${esc(t.id)}"><div class="task-head"><span class="task-id">${esc(t.id)}</span><span class="task-title">${md(who(t).title)} <span class="tag">· ${esc(who(t).owner)}</span></span><span class="chev">⌄</span><select class="status" aria-label="Статус ${esc(t.id)}"><option value="todo" ${stat(t)==="todo"?"selected":""}>Не начато</option><option value="doing" ${stat(t)==="doing"?"selected":""}>В работе</option><option value="done" ${stat(t)==="done"?"selected":""}>Готово</option></select></div>${t.added_at?`<div class="freshness">${DATA.latest_task===`tg:${t.id}`&&stat(t)==="todo"?'<span class="new-badge">НОВОЕ</span>':""}<span>Добавлено: ${esc(t.added_at)}</span></div>`:""}<div class="task-detail">Этап: ${esc(t.stage==="0"?"Подготовлено":`Этап ${t.stage}`)}. Статус реализации исходного плана: ${t.initial==="done"?"уже выполнено":"ожидает команды «делаем» и дальнейшей реализации"}.</div></article>`).join("");box.querySelectorAll(".task").forEach(c=>{c.querySelector(".task-head").onclick=e=>{if(!e.target.closest("select"))c.classList.toggle("open")};c.querySelector("select").onchange=e=>{state[c.dataset.id]=e.target.value;save()}})}
function renderProgress(){const counts={todo:0,doing:0,done:0};DATA.tasks.forEach(t=>counts[stat(t)]++);document.getElementById("done").textContent=counts.done;document.getElementById("doing").textContent=counts.doing;document.getElementById("todo").textContent=counts.todo;document.getElementById("total").textContent=DATA.tasks.length;document.getElementById("progressText").textContent=`${counts.done} из ${DATA.tasks.length} задач`;document.getElementById("progressBar").style.width=`${Math.round(counts.done/DATA.tasks.length*100)}%`}
function render(){renderStages();renderTasks();renderProgress()}const sf=document.getElementById("stageFilter");DATA.stages.forEach(s=>sf.insertAdjacentHTML("beforeend",`<option value="${esc(s.id)}">${esc(s.id==="0"?"Подготовлено":`Этап ${s.id}: ${s.name}`)}</option>`));document.getElementById("search").oninput=render;sf.onchange=render;document.getElementById("expand").onclick=()=>document.querySelectorAll(".task").forEach(c=>c.classList.toggle("open"));document.getElementById("reset").onclick=()=>{if(confirm("Сбросить статусы плана в этом браузере?")){state={};save();window.planSharedReset?.("tg")}};document.getElementById("deferred").innerHTML=DATA.deferred.map(x=>`<span class="pill">${esc(x)}</span>`).join("");render();
</script></body></html>'''


if __name__ == "__main__":
    main()
