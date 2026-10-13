# Значки расписания и меню — задание Кодексу (13.10.2026)

Решение пользователя 13.10: заменить текстовые кнопки и символы значками из того же набора Phosphor.

## Что сделать

1. Исходники уже скачаны Claude: `downloads/phosphor_icons_2.1.1/add_2026-10-13/` — `bell`, `bell-fill`, `map-pin`,
   `arrow-clockwise`, `funnel`, `trash`, `list`, `pencil-simple` (MIT, только `<path>`). Скопируй их в `regular/`
   (bell-fill тоже туда — имя файла отличает его) и добавь в `ICONS` в `tools/build_ui_icons.py`.
2. Собери PNG: `python tools/build_ui_icons.py` — 16 и 20 px, цвета набора (text, muted, accent, success, warning,
   caution). CairoSVG под Python 3.14 не грузится — используй тот же путь, что для magnifying-glass и других:
   белые силуэты 80 px в `downloads/phosphor_icons_2.1.1/masks/` (нарисовать из SVG) или venv на Python 3.12.
3. Проверь: каждый новый значок есть во всех размерах и цветах, `python -m pytest -q` проходит; положи в ветку
   превью-лист новых значков (одна картинка, тёмный фон) в `docs/evidence/icons-2/after.png`.
4. Обнови `downloads/phosphor_icons_2.1.1/README.md` (число значков и файлов) и строку в `DOWNLOADS.md`.

Подключение в программе (кнопки «Добавить событие», «Проверить обновление», «Виды», колокольчик вместо
«напомнить / напомню», «на карте», «Удалить» в форме, меню) делает Claude после приёмки.

## Ветка и передача

Ветка `codex/icons-2` от свежей `feat/chat-watcher`. Скиллы — только нужные (`CLAUDE.md`): здесь достаточно
`ui-visual-validator` для превью. В журнал `PAIR.md` — ветка, коммит, `pytest`, какие скиллы прочитаны.
