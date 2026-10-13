# Сопоставление задач и навыков

Сгенерировано `python tools/build_master_plan.py` из `docs/plan-ai-tools.json` — не править вручную. Учтены открытые задачи пяти планов и этапы черновиков; доступность проверена по файлам при сборке.

## Реестр инструментов

| Скилл / инструмент | Направление | Доступность | Codex | Открытых задач |
|---|---|---|---|---|
| `project-master-planner` | Планирование | установлен в проекте | Codex читает SKILL.md по AGENTS.md | 13 |
| `superpowers:brainstorming` | Планирование | плагин | у Codex есть свой экземпляр | 0 |
| `superpowers:writing-plans` | Планирование | плагин | у Codex есть свой экземпляр | 8 |
| `application-software-architect` | Архитектура | установлен в проекте | Codex читает SKILL.md по AGENTS.md | 26 |
| `application-ui-ux-designer` | UI/UX | установлен в проекте | Codex читает SKILL.md по AGENTS.md | 20 |
| `ui-ux-pro-max` | UI/UX | установлен глобально | Codex читает SKILL.md по AGENTS.md | 0 |
| `design-theme-guide` | UI/UX | установлен глобально | Codex читает SKILL.md по AGENTS.md | 2 |
| `application-motion-designer` | Motion | установлен в проекте | Codex читает SKILL.md по AGENTS.md | 2 |
| `superpowers:test-driven-development` | Разработка и тесты | плагин | у Codex есть свой экземпляр | 37 |
| `superpowers:systematic-debugging` | Отладка | плагин | у Codex есть свой экземпляр | 13 |
| `superpowers:verification-before-completion` | Проверка и ревью | плагин | у Codex есть свой экземпляр | 5 |
| `superpowers:requesting-code-review` | Проверка и ревью | плагин | у Codex есть свой экземпляр | 0 |
| `superpowers:using-git-worktrees` | Совместная работа | плагин | у Codex есть свой экземпляр | 0 |
| `ui-visual-validator` | Проверка и ревью | установлен глобально | Codex читает SKILL.md по AGENTS.md | 4 |
| `code-review` | Проверка и ревью | встроен в Claude Code | у Codex свой аналог | 1 |
| `security-review` | Безопасность | встроен в Claude Code | только у Claude | 15 |
| `run` | Проверка и ревью | встроен в Claude Code | только у Claude | 3 |
| `anthropic-skills:deep-research` | Исследование | из claude.ai | только у Claude | 10 |
| `tool:check_project` | Инструменты проекта | скрипт проекта | у Codex есть свой экземпляр | 3 |
| `tool:ui_snapshots` | Инструменты проекта | скрипт проекта | у Codex есть свой экземпляр | 3 |

## Распределение открытых задач

Claude Code: **19** · Codex: **12** · Совместно: **18** · Пользователь: **2**

## Задачи

| Ключ | Задача | Исполнитель | Основной скилл | Дополнительные | Передача |
|---|---|---|---|---|---|
| `map:20` | Проверка в игре и сборка | Совместно | `superpowers:verification-before-completion` | `run`, `superpowers:systematic-debugging`, `tool:check_project` | нужен пользователь |
| `map:24` | v4 · Бездна в программе | Совместно | `application-software-architect` | `superpowers:test-driven-development`, `superpowers:systematic-debugging`, `tool:check_project` | в работе |
| `map:27` | v4 · Проверка в игре и сборка | Совместно | `superpowers:verification-before-completion` | `run`, `tool:check_project` | нужен пользователь |
| `map:29` | Плавное приближение и отдаление карты | Codex | `application-motion-designer` | `application-ui-ux-designer`, `superpowers:test-driven-development` | готово к передаче Codex |
| `map:30` | Режим курсора и перемещения карты | Codex | `application-ui-ux-designer` | `application-motion-designer`, `superpowers:test-driven-development` | готово к передаче Codex |
| `map:31` | Кнопка очистки синих меток «Место» | Claude Code | `application-ui-ux-designer` | `superpowers:test-driven-development` | передача не нужна |
| `map:32` | Уменьшить синие крестики на 35 % | Claude Code | `application-ui-ux-designer` | `ui-visual-validator`, `tool:ui_snapshots` | в работе |
| `map:33` | Развести подписи карты и значки | Claude Code | `application-ui-ux-designer` | `ui-visual-validator`, `superpowers:test-driven-development` | передача не нужна |
| `map:34` | Убрать несуществующий вход в пещеру Мариссы | Codex | `superpowers:systematic-debugging` | `superpowers:test-driven-development` | готово к передаче Codex |
| `map:35` | Добавить фильтры карты | Claude Code | `project-master-planner`, `application-ui-ux-designer` | `application-software-architect`, `superpowers:test-driven-development` | ждёт архитектурного решения Claude |
| `map:36` | Увеличить названия зон на 15 % | Codex | `application-ui-ux-designer` | `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `map:37` | Убрать дублирование прохода в тоннель Силентера | Codex | `superpowers:systematic-debugging` | `superpowers:test-driven-development` | готово к передаче Codex |
| `map:38` | Показывать в сообщении метку с названием локации | Claude Code | `superpowers:test-driven-development` | `superpowers:systematic-debugging` | передача не нужна |
| `map:39` | Настраиваемая ширина карты и соседней панели | Совместно | `application-ui-ux-designer` | `application-software-architect`, `superpowers:test-driven-development` | готово к передаче Codex |
| `sn:SN-10` | Проверка поверх игры и сборка | Совместно | `ui-visual-validator` | `tool:ui_snapshots`, `run`, `superpowers:verification-before-completion` | нужен пользователь |
| `tg:1.1` | Модуль `telegram.py`: `sendMessage` (HTML, экранирование `<>&`), `429`, ошибки сети, `getUpdates` для поиска чатов. | Codex | `superpowers:test-driven-development` | `security-review`, `code-review` | план ждёт «делаем» |
| `tg:1.2` | Поток-отправщик: группа через `ChatBatcher` (тик 0.5 с), личка — своя очередь, по одному. | Codex | `application-software-architect` | `superpowers:test-driven-development`, `superpowers:systematic-debugging` | план ждёт «делаем» |
| `tg:1.3` | Отдельный «слушатель» лога для группы (свой tailer, только `3.Поиск группы` через `parse_line`), работает пока включена галочка. | Claude Code | `application-software-architect` | `superpowers:test-driven-development` | передача не нужна |
| `tg:1.4` | Совпадения поиска → в личку (из того же места, где сейчас звук; история не шлётся). | Claude Code | `superpowers:test-driven-development` |  | передача не нужна |
| `tg:1.5` | Настройки в `config.json`: `tg_token`, `tg_group_chat_id`, `tg_alert_chat_id`, `tg_group_enabled`, `tg_alert_enabled`. | Claude Code | `security-review` | `application-software-architect` | передача не нужна |
| `tg:1.6` | Тесты с подменённым HTTP: 429, обрыв сети, в группу не уходит ничего кроме `3.Поиск группы`, личка. | Codex | `superpowers:test-driven-development` | `superpowers:systematic-debugging` | план ждёт «делаем» |
| `tg:2.1` | Вкладка «Telegram»: токен (скрыт как пароль), «Найти чаты», выбор группы и лички, «Тестовое сообщение». | Claude Code | `application-ui-ux-designer` | `security-review`, `superpowers:test-driven-development` | передача не нужна |
| `tg:2.2` | Галочки «Чат в группу» и «Уведомления в личку», статус: «отправлено N», «в очереди N», «нет связи», «неверный токен», «бот не в группе». | Claude Code | `application-ui-ux-designer` | `superpowers:test-driven-development` | передача не нужна |
| `draft:DRAFT-01.1` | Уточнить расчётные сценарии | Claude Code | `project-master-planner` |  | передача не нужна |
| `draft:DRAFT-01.2` | Проверить игровые правила и источники | Совместно | `anthropic-skills:deep-research` |  | передача не нужна |
| `draft:DRAFT-01.3` | Согласовать модель и макет | Claude Code | `application-software-architect`, `application-ui-ux-designer` |  | передача не нужна |
| `draft:DRAFT-01.4` | Реализация и сверка примеров | Совместно | `superpowers:writing-plans` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-02.1` | Инвентаризация доступных полей предметов | Codex | `project-master-planner` | `superpowers:systematic-debugging` | готово к передаче Codex |
| `draft:DRAFT-02.2` | Сверить игровые механики | Совместно | `anthropic-skills:deep-research` |  | передача не нужна |
| `draft:DRAFT-02.3` | Спроектировать сравнение комплектов | Claude Code | `application-software-architect`, `application-ui-ux-designer` |  | передача не нужна |
| `draft:DRAFT-02.4` | Реализация и проверка на известных наборах | Совместно | `superpowers:writing-plans` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-03.1` | Сверить каталог и названия стигм | Codex | `project-master-planner` | `superpowers:systematic-debugging` | готово к передаче Codex |
| `draft:DRAFT-03.2` | Подтвердить правила набора | Совместно | `anthropic-skills:deep-research` |  | передача не нужна |
| `draft:DRAFT-03.3` | Выбрать редактор набора | Claude Code | `application-software-architect`, `application-ui-ux-designer` |  | передача не нужна |
| `draft:DRAFT-03.4` | Реализация и игровая сверка | Совместно | `superpowers:writing-plans` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-04.1` | Определить решение, которое нужен принять | Claude Code | `project-master-planner` |  | передача не нужна |
| `draft:DRAFT-04.2` | Проверить доступные события и правила | Совместно | `anthropic-skills:deep-research` |  | передача не нужна |
| `draft:DRAFT-04.3` | Оценить прототип без интеграции | Codex | `application-software-architect` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-04.4` | Только при go: отдельный план реализации | Совместно | `superpowers:writing-plans` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-05.1` | Дизайн-система и макеты основных экранов | Claude Code | `application-ui-ux-designer`, `design-theme-guide` |  | ждёт предыдущих этапов |
| `draft:DRAFT-05.2` | Общий API: вход и статус серверов | Claude Code | `application-software-architect` | `security-review`, `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-05.3` | Лаунчер-MVP на Tauri 2 | Совместно | `application-software-architect` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-05.4` | Патчер и CDN | Совместно | `application-software-architect`, `superpowers:test-driven-development` | `superpowers:systematic-debugging` | ждёт предыдущих этапов |
| `draft:DRAFT-05.5` | Самообновление, установщик и подпись кода | Совместно | `security-review` | `superpowers:verification-before-completion` | ждёт предыдущих этапов |
| `draft:DRAFT-05.6` | Сайт на Next.js | Claude Code | `application-ui-ux-designer` | `application-software-architect` | ждёт предыдущих этапов |
| `draft:DRAFT-05.7` | Функции Chat Watcher во вкладках лаунчера | Совместно | `application-software-architect` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-05.8` | Магазин и донат (в будущем) | Пользователь | `project-master-planner` | `security-review` | ждёт предыдущих этапов |
| `draft:DRAFT-06.1` | Модель угроз своего сервера | Claude Code | `anthropic-skills:deep-research` | `security-review` | ждёт предыдущих этапов |
| `draft:DRAFT-06.2` | Серверные проверки и журнал | Совместно | `application-software-architect`, `security-review` |  | ждёт предыдущих этапов |
| `draft:DRAFT-06.3` | Целостность клиента по хешам | Codex | `superpowers:test-driven-development` | `security-review` | ждёт предыдущих этапов |
| `draft:DRAFT-06.4` | Решение по клиентскому античиту | Пользователь | `project-master-planner` |  | ждёт предыдущих этапов |
| `draft:DRAFT-01.1` | Уточнить расчётные сценарии | Claude Code | `project-master-planner` |  | передача не нужна |
| `draft:DRAFT-01.2` | Проверить игровые правила и источники | Совместно | `anthropic-skills:deep-research` |  | передача не нужна |
| `draft:DRAFT-01.3` | Согласовать модель и макет | Claude Code | `application-software-architect`, `application-ui-ux-designer` |  | передача не нужна |
| `draft:DRAFT-01.4` | Реализация и сверка примеров | Совместно | `superpowers:writing-plans` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-02.1` | Инвентаризация доступных полей предметов | Codex | `project-master-planner` | `superpowers:systematic-debugging` | готово к передаче Codex |
| `draft:DRAFT-02.2` | Сверить игровые механики | Совместно | `anthropic-skills:deep-research` |  | передача не нужна |
| `draft:DRAFT-02.3` | Спроектировать сравнение комплектов | Claude Code | `application-software-architect`, `application-ui-ux-designer` |  | передача не нужна |
| `draft:DRAFT-02.4` | Реализация и проверка на известных наборах | Совместно | `superpowers:writing-plans` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-03.1` | Сверить каталог и названия стигм | Codex | `project-master-planner` | `superpowers:systematic-debugging` | готово к передаче Codex |
| `draft:DRAFT-03.2` | Подтвердить правила набора | Совместно | `anthropic-skills:deep-research` |  | передача не нужна |
| `draft:DRAFT-03.3` | Выбрать редактор набора | Claude Code | `application-software-architect`, `application-ui-ux-designer` |  | передача не нужна |
| `draft:DRAFT-03.4` | Реализация и игровая сверка | Совместно | `superpowers:writing-plans` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-04.1` | Определить решение, которое нужен принять | Claude Code | `project-master-planner` |  | передача не нужна |
| `draft:DRAFT-04.2` | Проверить доступные события и правила | Совместно | `anthropic-skills:deep-research` |  | передача не нужна |
| `draft:DRAFT-04.3` | Оценить прототип без интеграции | Codex | `application-software-architect` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-04.4` | Только при go: отдельный план реализации | Совместно | `superpowers:writing-plans` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-05.1` | Дизайн-система и макеты основных экранов | Claude Code | `application-ui-ux-designer`, `design-theme-guide` |  | ждёт предыдущих этапов |
| `draft:DRAFT-05.2` | Общий API: вход и статус серверов | Claude Code | `application-software-architect` | `security-review`, `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-05.3` | Лаунчер-MVP на Tauri 2 | Совместно | `application-software-architect` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-05.4` | Патчер и CDN | Совместно | `application-software-architect`, `superpowers:test-driven-development` | `superpowers:systematic-debugging` | ждёт предыдущих этапов |
| `draft:DRAFT-05.5` | Самообновление, установщик и подпись кода | Совместно | `security-review` | `superpowers:verification-before-completion` | ждёт предыдущих этапов |
| `draft:DRAFT-05.6` | Сайт на Next.js | Claude Code | `application-ui-ux-designer` | `application-software-architect` | ждёт предыдущих этапов |
| `draft:DRAFT-05.7` | Функции Chat Watcher во вкладках лаунчера | Совместно | `application-software-architect` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-05.8` | Магазин и донат (в будущем) | Пользователь | `project-master-planner` | `security-review` | ждёт предыдущих этапов |
| `draft:DRAFT-06.1` | Модель угроз своего сервера | Claude Code | `anthropic-skills:deep-research` | `security-review` | ждёт предыдущих этапов |
| `draft:DRAFT-06.2` | Серверные проверки и журнал | Совместно | `application-software-architect`, `security-review` |  | ждёт предыдущих этапов |
| `draft:DRAFT-06.3` | Целостность клиента по хешам | Codex | `superpowers:test-driven-development` | `security-review` | ждёт предыдущих этапов |
| `draft:DRAFT-06.4` | Решение по клиентскому античиту | Пользователь | `project-master-planner` |  | ждёт предыдущих этапов |
