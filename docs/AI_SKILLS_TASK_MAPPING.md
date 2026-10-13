# Сопоставление задач и навыков

Сгенерировано `python tools/build_master_plan.py` из `docs/plan-ai-tools.json` — не править вручную. Учтены открытые задачи пяти планов и этапы черновиков; доступность проверена по файлам при сборке.

## Реестр инструментов

| Скилл / инструмент | Направление | Доступность | Codex | Открытых задач |
|---|---|---|---|---|
| `project-master-planner` | Планирование | установлен в проекте | Codex читает SKILL.md по AGENTS.md | 13 |
| `superpowers:brainstorming` | Планирование | плагин | у Codex есть свой экземпляр | 0 |
| `superpowers:writing-plans` | Планирование | плагин | у Codex есть свой экземпляр | 10 |
| `application-software-architect` | Архитектура | установлен в проекте | Codex читает SKILL.md по AGENTS.md | 23 |
| `application-ui-ux-designer` | UI/UX | установлен в проекте | Codex читает SKILL.md по AGENTS.md | 44 |
| `ui-ux-pro-max` | UI/UX | установлен глобально | Codex читает SKILL.md по AGENTS.md | 10 |
| `design-theme-guide` | UI/UX | установлен глобально | Codex читает SKILL.md по AGENTS.md | 12 |
| `application-motion-designer` | Motion | установлен в проекте | Codex читает SKILL.md по AGENTS.md | 4 |
| `superpowers:test-driven-development` | Разработка и тесты | плагин | у Codex есть свой экземпляр | 34 |
| `superpowers:systematic-debugging` | Отладка | плагин | у Codex есть свой экземпляр | 12 |
| `superpowers:verification-before-completion` | Проверка и ревью | плагин | у Codex есть свой экземпляр | 4 |
| `superpowers:requesting-code-review` | Проверка и ревью | плагин | у Codex есть свой экземпляр | 0 |
| `superpowers:using-git-worktrees` | Совместная работа | плагин | у Codex есть свой экземпляр | 0 |
| `ui-visual-validator` | Проверка и ревью | установлен глобально | Codex читает SKILL.md по AGENTS.md | 27 |
| `code-review` | Проверка и ревью | встроен в Claude Code | у Codex свой аналог | 1 |
| `security-review` | Безопасность | встроен в Claude Code | только у Claude | 12 |
| `run` | Проверка и ревью | встроен в Claude Code | только у Claude | 3 |
| `anthropic-skills:deep-research` | Исследование | из claude.ai | только у Claude | 13 |
| `tool:check_project` | Инструменты проекта | скрипт проекта | у Codex есть свой экземпляр | 3 |
| `tool:ui_snapshots` | Инструменты проекта | скрипт проекта | у Codex есть свой экземпляр | 26 |

## Распределение открытых задач

Claude Code: **25** · Codex: **33** · Совместно: **18** · Пользователь: **0**

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
| `sn:SN-4` | Старые оповещения — через центр | Claude Code | `application-software-architect` | `superpowers:test-driven-development`, `superpowers:systematic-debugging` | передача не нужна |
| `sn:SN-5` | Вкладка «Уведомления» (настройки) | Совместно | `application-ui-ux-designer` | `ui-ux-pro-max`, `application-software-architect`, `superpowers:test-driven-development` | ждёт архитектурного решения Claude |
| `sn:SN-6` | Расписание: данные из статьи | Claude Code | `superpowers:verification-before-completion` | `anthropic-skills:deep-research` | передача не нужна |
| `sn:SN-7` | Вкладка «Расписание» | Совместно | `application-ui-ux-designer` | `application-motion-designer`, `superpowers:test-driven-development` | ждёт архитектурного решения Claude |
| `sn:SN-9` | Проверка обновления расписания | Codex | `application-software-architect` | `security-review`, `superpowers:test-driven-development` | ждёт архитектурного решения Claude |
| `sn:SN-10` | Проверка поверх игры и сборка | Совместно | `ui-visual-validator` | `tool:ui_snapshots`, `run`, `superpowers:verification-before-completion` | нужен пользователь |
| `ui:1` | На 1000×600 строка настроек обрезана, громкость пропадает | Codex | `application-ui-ux-designer` | `ui-ux-pro-max`, `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:2` | Контраст ниже 4.5:1: «Пропущено», Stop, выключенные фишки; границы полей 1.5:1 | Codex | `application-ui-ux-designer`, `design-theme-guide` | `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:3` | Настройки занимают ≈ 45 % высоты | Codex | `application-ui-ux-designer` | `ui-ux-pro-max`, `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:4` | Статус слежения мелкий и далеко от Start | Codex | `application-ui-ux-designer` | `ui-ux-pro-max`, `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:5` | Нет токенов: 25 цветов и 14 шрифтов прописаны на месте | Codex | `application-ui-ux-designer`, `design-theme-guide` | `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:6` | Шрифты: один кегль на всё, нет иерархии | Codex | `application-ui-ux-designer`, `design-theme-guide` | `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:7` | Оранжевый везде — акцент не работает | Codex | `application-ui-ux-designer`, `design-theme-guide` | `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:8` | Разнородные Юникод-символы вместо иконок | Codex | `application-ui-ux-designer` | `design-theme-guide`, `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:9` | Совпадения — сплошные оранжевые плашки | Codex | `application-ui-ux-designer`, `design-theme-guide` | `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:10` | Счётчики похожи на кнопки | Codex | `application-ui-ux-designer` | `ui-ux-pro-max`, `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:11` | Подпись выбранной вкладки смещена на ~4 px | Codex | `application-ui-ux-designer` | `ui-ux-pro-max`, `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:12` | Пустая лента до Start, нет «загрузки» | Codex | `application-ui-ux-designer` | `ui-ux-pro-max`, `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:13` | Выключенная фишка качества выглядит недоступной | Codex | `application-ui-ux-designer`, `design-theme-guide` | `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:14` | Окно «Найдено в чате!» в 3 раза больше содержимого | Codex | `application-ui-ux-designer` | `ui-ux-pro-max`, `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:15` | Фокус клавиатуры не виден (не проверено) | Codex | `application-ui-ux-designer` | `ui-ux-pro-max`, `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:16` | Полосы прокрутки устаревшие | Codex | `application-ui-ux-designer` | `design-theme-guide`, `ui-visual-validator`, `tool:ui_snapshots` | готово к передаче Codex |
| `ui:28` | Не проверено на 125/150 % масштабе Windows | Claude Code | `application-ui-ux-designer` | `design-theme-guide`, `ui-visual-validator`, `tool:ui_snapshots` | передача не нужна |
| `ui:29` | Список «Что искать»: кнопка ✕ сброса фильтров весит как стрелки поиска | Claude Code | `application-ui-ux-designer` | `ui-ux-pro-max`, `ui-visual-validator`, `tool:ui_snapshots` | передача не нужна |
| `ui:30` | Поиск по карте: результат «прыгает» | Claude Code | `application-motion-designer` | `application-ui-ux-designer`, `superpowers:test-driven-development` | передача не нужна |
| `ui:31` | Общий тёмный фон плоский | Codex | `application-ui-ux-designer` | `design-theme-guide`, `ui-visual-validator`, `tool:ui_snapshots` | ждёт проверки Claude |
| `ui:32` | В некоторых строках заметны неравномерные отступы и текст подходит слишком близко к краю/обрезается | Codex | `application-ui-ux-designer` | `ui-visual-validator`, `tool:ui_snapshots` | ждёт проверки Claude |
| `ui:33` | Подпись перекрывает изображение или значок под ней | Codex | `application-ui-ux-designer` | `ui-visual-validator`, `tool:ui_snapshots` | ждёт проверки Claude |
| `ui:34` | У комбобокса лишняя или раздвоенная рамка вокруг области стрелки | Codex | `application-ui-ux-designer` | `design-theme-guide`, `ui-visual-validator`, `tool:ui_snapshots` | ждёт проверки Claude |
| `ui:35` | Геометрия кнопки, скругление и тень выглядят несогласованно | Codex | `application-ui-ux-designer` | `design-theme-guide`, `ui-visual-validator`, `tool:ui_snapshots` | ждёт проверки Claude |
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
| `draft:DRAFT-05.1` | Согласовать область лаунчера | Claude Code | `project-master-planner` |  | передача не нужна |
| `draft:DRAFT-05.2` | Проверить официальный запуск и правила | Совместно | `anthropic-skills:deep-research` | `security-review` | передача не нужна |
| `draft:DRAFT-05.3` | Спроектировать процесс и UX | Claude Code | `application-software-architect`, `application-ui-ux-designer` | `security-review` | передача не нужна |
| `draft:DRAFT-05.4` | План безопасной реализации | Совместно | `superpowers:writing-plans` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-06.1` | Подтвердить цель, владельца и угрозы | Claude Code | `application-software-architect` | `security-review` | передача не нужна |
| `draft:DRAFT-06.2` | Проверить полномочия и приватность | Claude Code | `anthropic-skills:deep-research` |  | передача не нужна |
| `draft:DRAFT-06.3` | Сравнить варианты защиты | Claude Code | `application-software-architect`, `security-review` |  | передача не нужна |
| `draft:DRAFT-06.4` | Решение владельца и Claude | Совместно | `project-master-planner` |  | ждёт предыдущих этапов |
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
| `draft:DRAFT-05.1` | Согласовать область лаунчера | Claude Code | `project-master-planner` |  | передача не нужна |
| `draft:DRAFT-05.2` | Проверить официальный запуск и правила | Совместно | `anthropic-skills:deep-research` | `security-review` | передача не нужна |
| `draft:DRAFT-05.3` | Спроектировать процесс и UX | Claude Code | `application-software-architect`, `application-ui-ux-designer` | `security-review` | передача не нужна |
| `draft:DRAFT-05.4` | План безопасной реализации | Совместно | `superpowers:writing-plans` | `superpowers:test-driven-development` | ждёт предыдущих этапов |
| `draft:DRAFT-06.1` | Подтвердить цель, владельца и угрозы | Claude Code | `application-software-architect` | `security-review` | передача не нужна |
| `draft:DRAFT-06.2` | Проверить полномочия и приватность | Claude Code | `anthropic-skills:deep-research` |  | передача не нужна |
| `draft:DRAFT-06.3` | Сравнить варианты защиты | Claude Code | `application-software-architect`, `security-review` |  | передача не нужна |
| `draft:DRAFT-06.4` | Решение владельца и Claude | Совместно | `project-master-planner` |  | ждёт предыдущих этапов |
