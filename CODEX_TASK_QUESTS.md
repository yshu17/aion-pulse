# Задача для Кодекса: задания и русские строки клиента (карта, шаг «NPC с заданиями»)

Проект: `C:\Users\Євгеній\Desktop\ClaudeWorkspace\aion_chat_watcher`. Перед работой прочитай `PAIR.md`
(правила, журнал); это задача № 9 оттуда. Клиент: `C:\aMain\Games\AION Imperia\Aion Empire\classic` (далее
`<client>`). План карты: `docs/map-poi-plan.html`, шаг «NPC с заданиями (голубые треугольники)».

## Зачем

На игровой карте у NPC, которые выдают задания, стоят голубые треугольники (значок
`v4_radar_quest_icon_zonemap`, уже вырезан в `data/maps/icons/quest_point.png`). Чтобы показать их в программе,
нужно знать, какие NPC выдают задания. Заодно нужны русские строки клиента: названия осадных крепостей
(`STR_DF4_SV_3011`, `STR_LF4_SV_2021` и т. п. из `client_abyss.xml`) и районов.

## Правила (как в прошлый раз)

- Игровую папку **только читать**. Распакованное — в `client_extract/raw/` с сохранением путей внутри PAK.
- Бинарные XML — исходник и рядом UTF-8 `*.txt.xml`. Временный PAK-инструмент — в `tmp/`, после работы удалить.
- `data/`, `watcher/`, `tools/` не трогать — подключение делает Claude.
- После работы: строка в журнал `PAIR.md`, статус задачи 9 → «готово», строка в `client_extract/README.md`.

## Что распаковать

1. `<client>\Data\quest\quest.pak` — целиком: `quest.xml` (≈11 МБ), `combine_task.xml`, `quest_monster.csv`,
   `quest_script_monster.csv` → `client_extract/raw/Data/quest/...`
2. `<client>\l10n\rus\data\data.pak` — только папку `Strings/` (25 файлов: `client_strings_quest.xml`,
   `client_strings_npc.xml`, `client_strings_dic_place.xml`, `client_strings_level.xml`, `client_strings_ui.xml`,
   `client_strings_etc.xml` и остальные). `Dialogs/` и `CutScene/` не нужны.
   → `client_extract/raw/l10n/rus/data/Strings/...`
3. `<client>\Data\npcs\npcs.pak` — только `npc_ui.xml`, `npc_guide.xml` (могут описывать значок NPC на карте).

## Что подготовить (TSV в UTF-8, с заголовком)

1. `client_extract/raw/quest_givers.tsv` — одно задание на строку:
   `quest_id`, `name_ru` (через строки), `start_npc_id`, `end_npc_id` (если есть), `min_level`, `max_level`,
   `race` (light / dark / all), `category` (обычное / важное / событие / миссия — как в XML), `repeatable`.
   Если у задания несколько стартовых NPC — несколько строк. Поля называй по XML, если они другие, и опиши в
   отчёте.
2. `client_extract/raw/strings_ru.tsv` — `key`, `text` для всех строк из `client_strings_dic_place.xml`,
   `client_strings_level.xml`, `client_strings_npc.xml`, `client_strings_ui.xml` (ключи вида `STR_...`).
   Проверь, что там есть `STR_DF4_SV_3011`, `STR_DF4_SV_3021`, `STR_LF4_SV_2011`, `STR_LF4_SV_2021` — напиши
   их тексты в отчёте.

## Отчёт

`client_extract/raw/REPORT_QUESTS.md`: что распаковано (файлы, размеры), структура `quest.xml` (какие поля
отвечают за стартового NPC, расу, уровень, тип), сколько заданий и стартовых NPC всего и для зон
`df4`, `lf4`, `dc1`, `df1`, `df1a`, `df2`, `df2a`, `df3`, `underpass`; описание `npc_ui.xml` / `npc_guide.xml`,
если там есть значки NPC для карты; чего найти не удалось.
