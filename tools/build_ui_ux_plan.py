"""Build the interactive UI/UX plan from UI_UX_IMPROVEMENT_PLAN.md."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "UI_UX_IMPROVEMENT_PLAN.md"
OUTPUT = ROOT / "docs" / "ui-ux-improvement-plan.html"


def markdown_table_rows(lines: list[str], heading: str) -> list[list[str]]:
    start = next(i for i, line in enumerate(lines) if line.startswith(heading))
    rows: list[list[str]] = []
    for line in lines[start + 1 :]:
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def task_rows(lines: list[str]) -> list[dict[str, str]]:
    rows = markdown_table_rows(lines, "## 3. Таблица улучшений")
    tasks = []
    for row in rows[1:]:
        if len(row) != 9 or not row[0].isdigit():
            continue
        keys = ("id", "problem", "solution", "area", "files", "priority", "impact", "effort", "dependencies")
        tasks.append(dict(zip(keys, row, strict=True)))
    return tasks


def stage_rows(lines: list[str]) -> list[dict[str, object]]:
    rows = markdown_table_rows(lines, "## 4. План внедрения по этапам")
    stages = []
    for row in rows[1:]:
        if len(row) != 4:
            continue
        match = re.search(r"\*\*(\d+)\.\s*([^*]+)\*\*", row[0])
        if not match:
            continue
        ids: set[int] = set()
        for chunk in row[2].split(","):
            chunk = chunk.strip()
            range_match = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", chunk)
            if range_match:
                ids.update(range(int(range_match.group(1)), int(range_match.group(2)) + 1))
            elif chunk.isdigit():
                ids.add(int(chunk))
        stages.append({
            "id": int(match.group(1)),
            "name": match.group(2).strip(),
            "content": row[1],
            "tasks": sorted(ids),
            "ready": row[3],
        })
    return stages


def task_owners(lines: list[str]) -> dict[str, str]:
    """«- **Кодекс:** 8, 16, …» lines of section 8 -> {task id: owner}."""
    owners: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^-\s+\*\*(Claude|Кодекс):\*\*\s+([\d,\s]+)", line)
        if match:
            for number in re.findall(r"\d+", match.group(2)):
                owners[number] = match.group(1)
    return owners


def main() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    tasks = task_rows(lines)
    owners = task_owners(lines)
    for task in tasks:
        task["owner"] = owners.get(task["id"], "—")
    stages = stage_rows(lines)
    if len(tasks) != 31 or len(stages) != 9:
        raise SystemExit(f"Expected 31 tasks and 9 stages, got {len(tasks)} and {len(stages)}")

    data = json.dumps({"tasks": tasks, "stages": stages}, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.replace("__PLAN_DATA__", data)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)} ({len(tasks)} tasks, {len(stages)} stages)")


TEMPLATE = r'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Интерактивный план UI/UX</title>
<style>
:root{--bg:#141519;--surface:#1c1e24;--surface2:#262931;--border:#363a45;--text:#e9e7e4;--muted:#a1a5ae;--accent:#ff8c1a;--ok:#5fd38d;--warn:#f5b544;--blue:#7ab8ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:26px 18px 52px}h1{font-size:28px;line-height:1.2;margin:0 0 8px}h2{font-size:19px;margin:30px 0 12px}h3{font-size:16px;margin:0}.sub,.muted{color:var(--muted)}a{color:#ffb05c}code{font:13px Consolas,monospace;color:#ffd09a}
.head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px}.hero{margin:18px 0 12px}.stats{display:grid;grid-template-columns:repeat(4,minmax(100px,1fr));gap:10px;margin-top:14px}.stat{background:var(--surface2);border-radius:9px;padding:10px 12px}.stat b{display:block;font-size:20px}.stat span{font-size:12px;color:var(--muted)}
.bar{height:9px;background:var(--surface2);border-radius:9px;overflow:hidden;margin:10px 0 4px}.bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .25s}.toolbar{display:grid;grid-template-columns:minmax(220px,1fr) 180px 180px auto;gap:9px;align-items:center;margin:14px 0}.toolbar input,.toolbar select,.button{background:var(--surface2);border:1px solid var(--border);border-radius:8px;color:var(--text);padding:9px 11px;font:inherit}.button{cursor:pointer}.button:hover{border-color:var(--accent);color:#ffb05c}.grid{display:grid;grid-template-columns:280px minmax(0,1fr);gap:12px;align-items:start}.stages{position:sticky;top:12px}.stage{border-bottom:1px solid var(--border);padding:11px 2px}.stage:last-child{border:0}.stage button{width:100%;border:0;background:none;color:inherit;text-align:left;padding:0;font:inherit;cursor:pointer}.stage button:hover .stitle{color:#ffb05c}.stage-top{display:flex;justify-content:space-between;gap:8px}.stitle{font-weight:600}.tag{font-size:12px;color:var(--muted)}.stage .bar{height:5px;margin:7px 0 0}.stage.selected{background:#29241e;margin:0 -8px;padding:11px 10px;border-radius:8px}.tasks{display:grid;gap:9px}.task{overflow:hidden}.task.done{border-color:#375b48}.task-top{display:grid;grid-template-columns:38px minmax(0,1fr) 135px 22px;gap:10px;align-items:center;cursor:pointer}.num{color:var(--muted);font:13px Consolas,monospace}.problem{font-weight:600}.priority{font-size:11px;font-weight:700;border-radius:5px;padding:2px 7px;justify-self:start;background:#34251a;color:#ffb05c}.priority.P0{background:#402225;color:#ff8585}.priority.P1{background:#3d301b;color:#ffd16b}.priority.P2{background:#252d37;color:#9fcaff}.priority.P3{background:#292931;color:#c0b6d8}.status{width:135px;background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:7px;padding:6px;font:13px "Segoe UI",system-ui,sans-serif}.chev{color:var(--muted)}.detail{display:none;margin:13px 0 0 48px;padding-top:12px;border-top:1px solid var(--border);grid-template-columns:1fr 1fr;gap:12px}.task.open .detail{display:grid}.detail h4{margin:0 0 4px;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.04em}.detail p{margin:0;overflow-wrap:anywhere}.detail .wide{grid-column:1/-1}.decision{border-left:3px solid var(--accent);padding:8px 12px;background:var(--surface);margin:8px 0}.stage-filter{color:var(--muted);font-size:13px;margin:0 0 10px}.empty{padding:26px;text-align:center;color:var(--muted)}details.reference summary{cursor:pointer;font-weight:600}details.reference .inside{padding-top:12px;color:#d3d2d0}.checks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.check{background:var(--surface2);border-radius:7px;padding:8px 10px}.foot{margin-top:14px;font-size:12px;color:var(--muted)}
@media(max-width:850px){.grid{grid-template-columns:1fr}.stages{position:static}.toolbar{grid-template-columns:1fr 1fr}.toolbar input{grid-column:1/-1}.stats{grid-template-columns:repeat(2,1fr)}}@media(max-width:560px){.wrap{padding:18px 10px}.head{display:block}.task-top{grid-template-columns:30px minmax(0,1fr) 22px}.task-top .status{grid-column:2;grid-row:2}.detail{margin-left:0;grid-template-columns:1fr}.detail .wide{grid-column:auto}.toolbar{grid-template-columns:1fr}.toolbar input{grid-column:auto}.checks{grid-template-columns:1fr}}
</style>
</head>
<body><main class="wrap">
<header class="head"><div><h1>UI/UX: интерактивный план</h1><div class="sub">Aion Chat Watcher · план из <a href="../UI_UX_IMPROVEMENT_PLAN.md">UI_UX_IMPROVEMENT_PLAN.md</a> · обновлён по решениям карты v3</div></div><button class="button" id="reset">Сбросить статусы</button></header>
<section class="card hero"><div><b id="overallText">0 из 31 задач</b><span class="tag"> · статусы хранятся в этом браузере</span></div><div class="bar"><i id="overallBar"></i></div><div class="stats"><div class="stat"><b id="doneCount">0</b><span>готово</span></div><div class="stat"><b id="doingCount">0</b><span>в работе</span></div><div class="stat"><b id="todoCount">31</b><span>не начато</span></div><div class="stat"><b>9</b><span>этапов</span></div></div></section>
<div class="decision"><b>Связь с картой v3:</b> состав POI и расположение поиска сохраняются; порталы не добавляются до решения; игровые значки POI остаются готовыми. UI-полировка карты проводится после подтверждения текущей компоновки и геопривязок. <a href="map-poi-plan.html">Открыть интерактивный план карты</a>.</div>
<h2>Этапы</h2><div class="grid"><aside class="card stages" id="stages"></aside><section><div class="toolbar"><input id="search" type="search" placeholder="Поиск по задачам, решениям, файлам…"><select id="priority"><option value="">Все приоритеты</option><option>P0</option><option>P1</option><option>P2</option><option>P3</option></select><select id="stageFilter"><option value="">Все этапы</option></select><button class="button" id="expand">Раскрыть видимые</button></div><div class="stage-filter" id="resultCount"></div><div class="tasks" id="tasks"></div></section></div>
<h2>Правила проекта для работы над интерфейсом</h2><section class="card checks"><div class="check">Карта: не возвращать удалённые слои, сбор, задания и порталы.</div><div class="check">POI-значки: только готовые игровые ресурсы из клиента или aiondb.</div><div class="check">Геопривязка и количество точек проверяются отдельно от визуального редизайна.</div><div class="check">Пункты 18 и 30: подтвердить актуальность на текущем интерфейсе; анимация поиска необязательна.</div></section>
<h2>Основа дизайн-системы и критерии</h2><details class="card reference"><summary>Показать ограничения, критерии готовности и исходный план</summary><div class="inside"><p><b>Направление:</b> тёмная компактная панель с одним тёплым акцентом. Сохраняем игровые цвета качества предметов, высокую читаемость текста и готовые значки карты.</p><p><b>Ограничения Tk:</b> нет теней, размытия и прозрачности отдельных виджетов; глубина достигается цветом и 9-slice. Анимации короткие, дешёвые и отключаемые; перемасштабирование карты не анимировать.</p><p><b>Критерии завершения:</b> контраст текста не ниже 4.5:1; контуры контролов от 3:1; окно 1000×600 без обрезанных элементов; пустые/загрузочные/ошибочные состояния; видимый фокус клавиатуры; проверка масштабов 100/125/150%; тесты проходят и exe собирается.</p><p>Полные обоснования, палитра, типографика, дизайн-токены и риски находятся в <a href="../UI_UX_IMPROVEMENT_PLAN.md">исходном Markdown-плане</a>.</p></div></details>
<div class="foot">Статусы интерактивной страницы сохраняются только в localStorage браузера. Для изменения самого плана редактируй Markdown и пересобирай страницу: <code>python tools/build_ui_ux_plan.py</code>.</div>
</main>
<script>
const DATA=__PLAN_DATA__;
const KEY="aion-ui-ux-plan-status-v1";let state=load();
function load(){try{return JSON.parse(localStorage.getItem(KEY)||"{}")}catch{return {}}}
function save(){localStorage.setItem(KEY,JSON.stringify(state));render()}
function esc(v){return String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]))}
function status(id){return state[id]||"todo"}
function stageTasks(stage){return DATA.tasks.filter(t=>stage.tasks.includes(+t.id))}
function stageProgress(stage){if(!stage.tasks.length)return state.stage0==="done"?1:0;let tasks=stageTasks(stage);return tasks.length?tasks.filter(t=>status(t.id)==="done").length/tasks.length:0}
function renderStages(){const box=document.getElementById("stages");box.innerHTML=DATA.stages.map(s=>{const pct=Math.round(stageProgress(s)*100),selected=document.getElementById("stageFilter").value===String(s.id);return `<div class="stage ${selected?"selected":""}"><button data-stage="${s.id}"><div class="stage-top"><span class="stitle">${s.id}. ${esc(s.name)}</span><span class="tag">${pct}%</span></div><div class="tag">${esc(s.content)}</div><div class="bar"><i style="width:${pct}%"></i></div></button></div>`}).join("");box.querySelectorAll("[data-stage]").forEach(b=>b.onclick=()=>{document.getElementById("stageFilter").value=b.dataset.stage;render()})}
function renderTasks(){const q=document.getElementById("search").value.trim().toLocaleLowerCase("ru"),p=document.getElementById("priority").value,s=document.getElementById("stageFilter").value;let list=DATA.tasks.filter(t=>(!q||Object.values(t).join(" ").toLocaleLowerCase("ru").includes(q))&&(!p||t.priority===p)&&(!s||DATA.stages.find(x=>String(x.id)===s)?.tasks.includes(+t.id)));document.getElementById("resultCount").textContent=`Показано: ${list.length} из ${DATA.tasks.length}`;const box=document.getElementById("tasks");if(!list.length){box.innerHTML='<div class="card empty">Ничего не найдено</div>';return}box.innerHTML=list.map(t=>`<article class="card task ${status(t.id)==="done"?"done":""}" data-task="${t.id}"><div class="task-top"><span class="num">#${t.id}</span><span class="problem">${esc(t.problem)} <span class="tag owner">· ${esc(t.owner)}</span></span><span class="priority ${t.priority}">${t.priority}</span><span class="chev">⌄</span><select class="status" aria-label="Статус задачи ${t.id}"><option value="todo" ${status(t.id)==="todo"?"selected":""}>Не начато</option><option value="doing" ${status(t.id)==="doing"?"selected":""}>В работе</option><option value="done" ${status(t.id)==="done"?"selected":""}>Готово</option></select></div><div class="detail"><div><h4>Решение</h4><p>${esc(t.solution)}</p></div><div><h4>Область · сложность</h4><p>${esc(t.area)} · ${esc(t.effort)}</p></div><div><h4>Файлы</h4><p>${esc(t.files)}</p></div><div><h4>Зависимости</h4><p>${esc(t.dependencies)}</p></div><div class="wide"><h4>Ожидаемый эффект</h4><p>${esc(t.impact)}</p></div></div></article>`).join("");box.querySelectorAll(".task").forEach(card=>{card.querySelector(".task-top").addEventListener("click",e=>{if(e.target.closest("select"))return;card.classList.toggle("open")});card.querySelector("select").addEventListener("change",e=>{state[card.dataset.task]=e.target.value;save()})})}
function renderProgress(){const counts={todo:0,doing:0,done:0};DATA.tasks.forEach(t=>counts[status(t.id)]++);document.getElementById("doneCount").textContent=counts.done;document.getElementById("doingCount").textContent=counts.doing;document.getElementById("todoCount").textContent=counts.todo;document.getElementById("overallText").textContent=`${counts.done} из ${DATA.tasks.length} задач`;document.getElementById("overallBar").style.width=`${Math.round(counts.done/DATA.tasks.length*100)}%`}
function render(){renderStages();renderTasks();renderProgress()}
const stageSelect=document.getElementById("stageFilter");DATA.stages.forEach(s=>stageSelect.insertAdjacentHTML("beforeend",`<option value="${s.id}">${s.id}. ${esc(s.name)}</option>`));
document.getElementById("search").addEventListener("input",render);document.getElementById("priority").addEventListener("change",render);stageSelect.addEventListener("change",render);document.getElementById("expand").onclick=()=>document.querySelectorAll(".task").forEach(x=>x.classList.toggle("open"));document.getElementById("reset").onclick=()=>{if(confirm("Сбросить все статусы этого плана в этом браузере?")){state={};save()}};render();
</script></body></html>'''


if __name__ == "__main__":
    main()

