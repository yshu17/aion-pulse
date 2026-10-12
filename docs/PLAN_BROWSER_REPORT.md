# UI:45 — остаточная независимая проверка 12 интерактивных страниц

Исполнитель: Codex. Проверяющий: Claude Code. Дата: 12.10.2026 (Europe/Warsaw).

## Итог

**BLOCKED.** Ключевые браузерные проверки UI:45 не выполнены, поэтому доказательств для рассмотрения этапа 4 недостаточно. Код планов и данные пользователя не менялись; старые списки не удалялись.

Проверенная база: `6c768256d570d5243d92a4dd20b7ab37ff03c136` (`feat/chat-watcher`, исходная точка ветки `codex/plan-browser-residual`). Ветка была чистой перед началом. Отдельного файла `TASK_UI-45.md` нет: техническое поручение находится в `PAIR.md` (запись «передача ui:45 Кодексу») и в запросе пользователя. Предыдущая проверка: [PLAN_BROWSER_QA_REPORT.md](PLAN_BROWSER_QA_REPORT.md).

### Браузер и условия запуска

Браузер **не использовался**; страницы **не запускались**. Доступный встроенный браузер Codex ранее отклонил локальный `file://` по политике URL и запретил обход через локальный сервер либо другую браузерную поверхность. Текущий инвентарь показывает только Codex In-app Browser и MCP Apps, без Chrome/Edge; Playwright MCP отсутствует, пакеты `playwright`, `playwright-core`, `puppeteer` не установлены. `tools/ui_snapshots.py` снимает Tk-окно приложения, а не HTML-планы. Поэтому viewport, движок, масштаб, console и origin для браузерных тестов не существуют. Реальные пользовательские данные браузера не трогали. Пользователь подтвердил, что HTTPS-ссылки на эту точную сборку нет, и попросил передать браузерную часть Claude.

**Снимки: 0/36.** Не создано синтетических замен. В `docs/ui/plan-browser/` нет результатов этого запуска. Ширины 375, 768 и 1400 px, горизонтальная прокрутка, наложения, графики и читаемость остаются **NOT VERIFIED**.

## Перечень страниц и матрица

Статус **PARTIAL** означает только проверку сгенерированного HTML/JSON/JS и существующих автотестов; браузерное поведение таким статусом не подтверждается. **NOT VERIFIED** означает отсутствие наблюдения. **FAIL** — доказанный дефект кода.

| Страница | Файл | Загрузка/консоль | Общая карточка и данные | Действия/фильтры | Motion | 375/768/1400 | Экспорт/импорт | Итог |
|---|---|---|---|---|---|---|---|---|
| MASTER | `docs/index.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| Telegram | `docs/telegram-bridge-plan.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| Расписание | `docs/schedule-notify-plan.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| UI/UX | `docs/ui-ux-improvement-plan.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| Карта | `docs/map-poi-plan.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| Черновики | `docs/feature-drafts.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| Кюна | `docs/feature-quna-resale.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| Броня | `docs/feature-armor-calculator.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| Стигмы | `docs/feature-stigma-calculator.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| DPS Meter | `docs/feature-dps-meter-feasibility.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| Лаунчер | `docs/feature-game-launcher.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |
| Античит | `docs/feature-launcher-anticheat.html` | NOT VERIFIED | PARTIAL | NOT VERIFIED | NOT VERIFIED | NOT VERIFIED | FAIL | BLOCKED |

Колонка «общая карточка и данные» подтверждает присутствие одного `shared-plan` и идентичного JSON модели во всех 12 файлах. Она **не** подтверждает визуальную отрисовку, клики, уникальность карточек в DOM, доступность Skills/ответственных/чекбоксов или отсутствие ошибок JS при исполнении. Колонка «Экспорт/импорт» отмечена FAIL из-за общего обработчика повторного импорта, описанного ниже; фактическое скачивание и восстановление не проверены.

## Автоматические проверки

- `python -m pytest -q`: **359 passed in 32.73s**.
- `python tools/check_plans.py`: **OK, 127 tasks, 5 core pages, 6 DRAFT plans, 68 AI recommendations**.
- Проверка встроенной модели: **12/12** страниц содержат одну и ту же модель; **127/127** ID уникальны. Распределение: карта 39, расписание 10, UI/UX 45, Telegram 9, черновики 24. В модели 9 этапов UI/UX и 3 этапа Telegram.
- Все inline JavaScript блоки 12 страниц компилируются через Node `vm.Script`: **0 синтаксических ошибок**. Исполнение и консоль браузера **NOT VERIFIED**.
- Генераторы запущены только в `tmp/ui45-build/`: UI/UX 45 задач, Telegram 9, 6 черновиков, MASTER 127. Сравнение с проверяемым коммитом: **13/13** сгенерированных файлов (`12 HTML + plan-model.json`) совпали побайтно. Исходные страницы не менялись.
- По коду видны исправления QA-01–03: сортировка проверяет `planned`, открытые ID сохраняются при `draw()`, нативный режим требует значения `native=1`. Реальное поведение этих исправлений в браузере Codex **NOT VERIFIED**.

## Не выполненные сценарии UI:45

| Сценарий | Результат |
|---|---|
| Чекбокс done/review, статус, приоритет, Skills, ответственный, поиск, все фильтры, счётчики, история | NOT VERIFIED в браузере |
| Раскрытие/закрытие, быстрые нажатия, возврат фильтра, клавиатура, фокус | NOT VERIFIED |
| 160/140 мс, вспышка статуса, реальный `prefers-reduced-motion` | NOT VERIFIED; наличие CSS не засчитано |
| Экспорт → очистка → импорт → откат → reload на изолированном origin | NOT VERIFIED |
| Повторный импорт без дублей истории | FAIL по исходнику; реальный файл NOT VERIFIED |
| Конфликт общего и старого журналов без перезаписи, повторный перенос | NOT VERIFIED |
| Скрытие нативных списков, `?native=1`, другие значения, отсутствие двойного DOM | PARTIAL по коду, браузер NOT VERIFIED |
| Сохранность старых ключей и личных отметок пользователя | Пользователь подтвердил перенос на своём `file://` по записи Claude; Codex эти данные не открывал и не проверял |

## Дефект UI45-01 — повторный импорт дублирует историю

**Важность: Medium. Страницы: все 12.** `tools/plan_shared.py:239`.

Шаги воспроизведения на изолированных данных: создать одну запись изменения, экспортировать JSON, импортировать файл дважды, открыть историю задачи. Ожидается одна импортированная запись. Фактически по однозначному пути кода строка `ledger.history.push(...data.history.filter(...))` выполняется при каждом импорте без проверки ранее импортированных записей; история удваивается. Статусы при этом могут сохраняться, но требование идемпотентности не соблюдено. Ширина/браузер/скриншот: **NOT VERIFIED**, поскольку локальные страницы недоступны. Рекомендация Claude: устранить повторное добавление истории и добавить браузерную проверку двух последовательных импортов.

Ранее найденные QA-01–03 исправлены Claude в коде коммита `7146f49`; Codex подтвердил наличие исправлений статически, не визуально.

## Рекомендации и решение по этапу 4

1. Claude Code проверить и исправить UI45-01, затем повторить импорт одного файла дважды с контролем статусов, истории и отката.
2. Провести 36 реальных снимков и сценарии Motion, localStorage, консоли, клавиатуры и нативного режима на изолированном origin доступным браузерным инструментом. Зафиксировать точный коммит, браузер, viewport и пути к снимкам.
3. До рассмотрения этапа 4 сохранить экспорт пользователя и проверить нужные ему origin. `docs/STAGE4_PRECHECK.md` прямо требует UI:45 и отдельного решения владельца.

**Вердикт UI:45 — BLOCKED. Доказательств для этапа 4 недостаточно.** Это не разрешение удалять старые списки, старые ключи или механизм отката.
