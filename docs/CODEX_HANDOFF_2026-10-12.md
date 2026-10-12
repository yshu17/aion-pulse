# Выдача Codex 12.10.2026 (ui:43 и map:34)

Утверждено пользователем 12.10.2026. Lead Developer — Claude Code. Это единый вход: здесь база, ветки, порядок, команды и формат отчёта.
Подробные требования — в заданиях `docs/TASK_UI-SNAPSHOT.md` и `docs/TASK_MAP-34.md`; здесь они не дублируются.

## 1. База

- Основная ветка: `feat/chat-watcher`. Тег базы выдачи: `handoff/2026-10-12` (коммит со всеми заданиями и этим файлом).
- Проверить перед стартом: `git log -1 --format=%H feat/chat-watcher` совпадает с `git rev-parse handoff/2026-10-12` (или ветка ушла вперёд только документами).
- Состояние базы: 316 тестов проходят, `python tools/check_plans.py` — `Plan integrity: OK`, 101 задача.
- В базе уже есть: пилот `ui:42` принят (`d125e49`), задание `ui:43` зарегистрировано, `map:32` переназначен на Claude.

## 2. Порядок

1. **Первой — `ui:43`** (`docs/TASK_UI-SNAPSHOT.md`), ветка `codex/ui-snapshots`.
2. **`map:34`** (`docs/TASK_MAP-34.md`), ветка `codex/map-34-marissa`. Не пересекается с `ui:43` по файлам.
3. Выполнять **последовательно**, если нет отдельного worktree и отдельного сеанса. Параллельно — только при обоих условиях (п. 4).

## 3. Рабочие копии и ветки

| Задача | Рабочая копия | Ветка | Создать ветку |
|---|---|---|---|
| `ui:43` | `C:\Users\Євгеній\Desktop\ClaudeWorkspace\aion_codex` | `codex/ui-snapshots` | `git switch -c codex/ui-snapshots feat/chat-watcher` |
| `map:34` последовательно | та же `aion_codex` | `codex/map-34-marissa` | `git switch -c codex/map-34-marissa feat/chat-watcher` после сдачи `ui:43` |
| `map:34` параллельно | `C:\Users\Євгеній\Desktop\ClaudeWorkspace\aion_codex_map34` | `codex/map-34-marissa` | команды п. 4 |

Перед стартом в каждой копии `git status --short` должен быть пустым. Если в `aion_codex` ещё стоит ветка `codex/ui-42-tabs`, она уже влита в основную: переключайся сразу на новую ветку от `feat/chat-watcher`.

## 4. Параллельный запуск `map:34` (по желанию)

Нужен отдельный worktree и отдельный сеанс Codex. Создание worktree занимает около двух минут (данные карт). Команды выполняет любой из нас, один раз:

    git -C "C:/Users/Євгеній/Desktop/ClaudeWorkspace/aion_chat_watcher" worktree add "C:/Users/Євгеній/Desktop/ClaudeWorkspace/aion_codex_map34" -b codex/map-34-marissa feat/chat-watcher

Папки `client_extract/` и `downloads/` подключаются junction (PowerShell), как в `aion_codex`:

    New-Item -ItemType Junction -Path "C:\Users\Євгеній\Desktop\ClaudeWorkspace\aion_codex_map34\client_extract" -Target "C:\Users\Євгеній\Desktop\ClaudeWorkspace\aion_chat_watcher\client_extract"
    New-Item -ItemType Junction -Path "C:\Users\Євгеній\Desktop\ClaudeWorkspace\aion_codex_map34\downloads" -Target "C:\Users\Євгеній\Desktop\ClaudeWorkspace\aion_chat_watcher\downloads"

Без отдельного сеанса одну папку не использовать для двух задач одновременно.

## 5. Skills

- `ui:43`: `application-ui-ux-designer` (основной), `ui-visual-validator`, `superpowers:test-driven-development`.
- `map:34`: `superpowers:systematic-debugging`, `superpowers:test-driven-development`.
- Если skill недоступен в твоей среде, написать в отчёте «NOT VERIFIED» и выполнить проверку вручную по критериям задания.

## 6. Команды проверки

- Полный набор: `python -m pytest -q` (сейчас 316; после каждой задачи число не уменьшается).
- `ui:43`: `python tools/ui_snapshots.py check`, отрицательный тест из `TASK_UI-SNAPSHOT.md` п. 8.
- `map:34`: `python -m pytest -q tests/test_build_poi.py tests/test_poi.py`.
- Планы: `python tools/check_plans.py` — только если трогаешь файлы планов (не должен).

## 7. Что делает Claude параллельно

Готовит `map:32` в ветке `claude/map-32-cross` (`watcher/mapview.py`, `tests/test_mapview.py`). Эти файлы не входят в разрешённые файлы твоих задач.
`watcher/theme.py` свободен (пилот закрыт), но в твоих заданиях он не нужен. Визуальную приёмку `map:32` Claude выполнит после `ui:43`.

## 8. Формат отчёта

1. Запись в начало журнала `PAIR.md` одним коммитом в своей ветке (не оставлять незакоммиченный `PAIR.md`):

    - **ДД.ММ Кодекс · ui:43 (или map:34)** — ветка <имя>, коммит <SHA>; файлы: <список>; `python -m pytest -q`: N passed; <ключевые результаты>; не проверено: <список>; открыто: <вопросы или «нет»>.

2. Сообщить Claude: ветка и SHA. Не сливать в `feat/chat-watcher`, не делать rebase и reset.
3. Если что-то в задании противоречит коду, записать расхождение в отчёт и остановиться, не менять задание и не угадывать.
4. Честно указывать непроверенное. Системный DPI 125 % и 150 % в `ui:43` — «не проверен».

## 9. Тексты для вставки

**ui:43**

> Выполни задание `docs/TASK_UI-SNAPSHOT.md` в рабочей копии `aion_codex`. База — `feat/chat-watcher` (тег `handoff/2026-10-12`). Создай ветку `codex/ui-snapshots`. Меняй только файлы из раздела 6 задания. Отчёт — по `docs/CODEX_HANDOFF_2026-10-12.md` раздел 8. Не сливай и не публикуй.

**map:34**

> Выполни задание `docs/TASK_MAP-34.md`. База — `feat/chat-watcher` (тег `handoff/2026-10-12`). Ветка `codex/map-34-marissa`. Меняй только файлы из раздела 3 задания. Отчёт — по `docs/CODEX_HANDOFF_2026-10-12.md` раздел 8. Не сливай и не публикуй.
