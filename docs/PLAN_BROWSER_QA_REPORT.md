# Независимый аудит 12 страниц планов — ui:44

Исполнитель: Codex. Проверяющий: Claude Code. Дата: 12.10.2026 (Europe/Warsaw).

## Вердикт

**PARTIAL — полная браузерная приёмка не завершена.** Проверены код, данные, 12 сгенерированных страниц, два тега миграции и воспроизводимость сборки. Встроенный браузер Codex отклонил открытие локального `file://` по политике URL (разрешены только `http:` и `https:`; инструмент прямо запретил обход через локальный сервер и другую поверхность). Поэтому ни один интерактивный сценарий, снимок 375/768/1400 px или консоль браузера не объявлены проверенными. Claude Code должен выполнить браузерную часть до решения об удалении нативных списков.

Проверенный коммит: `e5f8a868fc16b94812b143112208ade1c7d854cb` (`plan-native-hidden`, `feat/chat-watcher` на момент начала). Сравнительный тег: `plan-native-visible` = `0028d6a925372d688d807683409a44234540bf34`. Ветка отчёта: `codex/plan-browser-check`. Рабочая копия была чистой перед проверкой. Файлы приложения, планы и статусы не изменялись.

## Страницы

| № | Страница | Файл |
|---|---|---|
| 1 | MASTER PLAN | `docs/index.html` |
| 2 | Telegram | `docs/telegram-bridge-plan.html` |
| 3 | Расписание | `docs/schedule-notify-plan.html` |
| 4 | UI/UX | `docs/ui-ux-improvement-plan.html` |
| 5 | Карта | `docs/map-poi-plan.html` |
| 6 | Обзор черновиков | `docs/feature-drafts.html` |
| 7 | Кюна и перепродажа | `docs/feature-quna-resale.html` |
| 8 | Калькулятор брони | `docs/feature-armor-calculator.html` |
| 9 | Калькулятор стигм | `docs/feature-stigma-calculator.html` |
| 10 | DPS Meter | `docs/feature-dps-meter-feasibility.html` |
| 11 | Игровой лаунчер | `docs/feature-game-launcher.html` |
| 12 | Античит | `docs/feature-launcher-anticheat.html` |

Все 12 файлов присутствуют. Во всех ровно один `shared-plan` и один встроенный `shared-plan-data`; JSON этого блока побайтно соответствует одной модели `docs/plan-model.json` после разбора. Компонент и словарь статусов одни для всех страниц. В модели 126 уникальных задач: карта 39, расписание 10, UI/UX 44, Telegram 9, черновики 24. Статусы источника: выполнено 61, запланировано 37, в работе 4, исследование 24. Данные списка не являются результатом браузерного подсчёта отрисованных карточек.

## Матрица

Обозначения: **PASS** — проверено полностью; **PARTIAL** — подтверждены исходники, данные и/или тесты, но нет проверки браузерного поведения; **NOT VERIFIED** — необходимых наблюдений нет. `Task Card`, статусы, чекбоксы, приоритеты, Skills, фильтры, Motion и экспорт/импорт имеют PARTIAL именно из-за отсутствия браузерного запуска. `Адаптивность` и `Ошибки` означают соответственно реальные размеры окна и консоль.

| Страница | Task Card | Статусы | Чекбоксы | Приоритеты | Skills | Фильтры | Motion | Адаптивность | Экспорт/импорт | Ошибки | Итог |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MASTER | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| Telegram | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| Расписание | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| UI/UX | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| Карта | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| Черновики | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| Кюна | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| Броня | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| Стигмы | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| DPS Meter | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| Лаунчер | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |
| Античит | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | NOT VERIFIED | PARTIAL | NOT VERIFIED | PARTIAL |

### Детализация сценариев

| Сценарий | Результат | Доказательство и предел |
|---|---|---|
| Отметка → done; снятие → review; doing → blocked; review → done | PARTIAL | Правила и 8 статусов присутствуют в `plan_states.py`, `plan_shared.py`; тесты успешны. Реальный клик и сохранение после reload не проверены. |
| Фильтры по статусу, приоритету, исполнителю, Skill, подтверждению; поиск | PARTIAL | Контролы и предикаты в едином JS присутствуют. Совпадение видимых карточек со счётчиком в браузере не проверено. |
| Раскрытие, закрытие, вложенность, всё открыть/закрыть, сохранение | PARTIAL | Обработчики есть; выявлен дефект QA-02. Быстрые клики и фокус не проверены. |
| MASTER: уникальные ID, числа и связи | PARTIAL | `check_plans.py` прошёл; JSON един на 12 страницах. Реальная синхронизация двух вкладок/страниц браузера не проверена. |
| Миграция до/после, `?native=1`, перенос/сброс/откат | PARTIAL | Теги развёрнуты отдельно; модели одинаковы; отличие `HIDE_NATIVE_LISTS=false→true`; тесты миграции успешны. Сохранение старых отметок на одном origin не проверено. |
| Экспорт → очистка → импорт → откат | PARTIAL | Код и существующие тесты проверены; реальный файл и восстановление localStorage не проверены. Между origin не проверено. |
| Reduced motion, повторные клики, отсутствие зависшей анимации | PARTIAL | CSS `@media (prefers-reduced-motion:reduce)`, токены и обработчик отмены есть; измерение поведения в браузере не выполнено. |
| 375, 768, 1400 px; снимки; консоль | NOT VERIFIED | Локальные URL отклонены политикой браузера. Скриншотов нет, пути к ним отсутствуют. |

## Автоматические проверки

- `python -m pytest -q` в рабочей копии: **358 passed in 32.39s**.
- `python tools/check_plans.py`: **OK, 126 tasks, 5 core pages, 6 DRAFT plans, 67 AI recommendations**. Проверяет уникальность ID, модель, даты, ссылки, зависимости, подтверждения.
- Временная копия тега `plan-native-hidden` в `tmp/plan-after-build/`: генераторы `build_ui_ux_plan.py`, `build_telegram_plan.py`, `build_feature_drafts.py`, `build_master_plan.py` завершились с кодом 0. Сравнение 12 HTML и `plan-model.json` с проверяемым коммитом: **13 из 13 совпали побайтно**.
- Временная копия тега `plan-native-visible` в `tmp/plan-before/`: 12 страниц; встроенная модель совпадает с состоянием после миграции. Во всех страницах константа `HIDE_NATIVE` меняется `false→true`; только PAGE `all/ui/tg` попадают в условие скрытия.
- Синтаксическая компиляция всех inline JavaScript через Node `vm.Script`: **0 ошибок**; чтение всех `docs/*.json`: **0 ошибок**.
- `check_plans.py` в архивной копии без `.git` сообщает 5 «commit not found» для записей подтверждения: это ограничение архива без истории Git, не результат проверки основной рабочей копии.
- Ошибки консоли браузера: **NOT VERIFIED**.

## Дефекты и расхождения

### QA-01 · Medium · порядок новой задачи

- Страница: все 12, особенно MASTER и UI/UX; код `tools/plan_shared.py:134`.
- Шаги: открыть общую карточку при текущем `MODEL.latest=ui:44`; оставить фильтр «Все планы».
- Ожидается: план с новой открытой задачей расположен сверху по действующему правилу планов.
- Фактически по коду: поиск `newest` сравнивает `status(i)==='todo'`, а `status()` нормализует `todo` в `planned`. Поэтому `newest` всегда отсутствует; порядок остаётся `map, draft, sn, ui, tg`, и план с `ui:44` не поднимается. Бейдж NEW у самой задачи остаётся.
- Доказательство: `docs/plan-model.json` хранит `latest=ui:44`, статус `planned`; статический путь исполнения однозначен. Скриншота нет из-за политики браузера.
- Рекомендация: сравнивать с `planned`, добавить регрессионную проверку порядка.

### QA-02 · Medium · раскрытие не сохраняется при перерисовке

- Страница: все 12; `tools/plan_shared.py:154`.
- Шаги: раскрыть карточку; изменить фильтр, поиск или статус (вызывает `draw()`); либо обновить страницу.
- Ожидается: согласно заданию состояние раскрытия сохраняется.
- Фактически по коду: `draw()` заменяет весь `shared-list.innerHTML` новыми закрытыми `details`; состояние `open` нигде не считывается и не восстанавливается. Reload также создаёт закрытые карточки.
- Доказательство: разбор кода; браузерный клик и снимок недоступны.
- Рекомендация: сохранять ID раскрытых карточек перед перерисовкой и восстанавливать после неё; для reload определить согласованный способ хранения.

### QA-03 · Low · параметр старого режима слишком широкий

- Страницы: MASTER, UI/UX, Telegram; `tools/plan_shared.py:96`.
- Шаги: открыть URL с `?native=0` либо `?native`.
- Ожидается: старый список возвращается только при документированном `?native=1`.
- Фактически по коду: `URLSearchParams(...).has('native')` принимает любое значение, поэтому скрытие отключится и для `0`.
- Доказательство: статический разбор; скриншота нет.
- Рекомендация: проверять значение параметра `=== '1'`.

Других подтверждённых проблем на уровне данных или синтаксиса не найдено. Это не означает, что нет визуальных и браузерных дефектов.

## Передача Claude Code

1. Проверить QA-01–03 и распределить исправления; Codex не менял код.
2. Запустить браузерную матрицу 12 × 3 ширины в доступном Playwright MCP или другом уже имеющемся инструменте. Сохранить 36 снимков, указать браузер, фактическую ширину viewport и консоль.
3. На изолированном origin пройти чекбоксы, статусы, фильтры, вложенность, reduced motion, быстрые клики, перенос отметок между тегами, экспорт/импорт/откат. Не трогать реальные localStorage пользователя.
4. Только после браузерной приёмки и решения владельца рассматривать физическое удаление старых списков (этап 4).

Статус ui:44 в исходном плане **не менялся**: пользователь запретил изменение реальных статусов в рамках read-only аудита. Отчёт документирует частичный результат и препятствие.
