# Задача для Кодекса: данные карты из клиента — подписи районов, входы в данжи, рейдовые боссы

Проект: `C:\Users\Євгеній\Desktop\ClaudeWorkspace\aion_chat_watcher`. Сначала прочитай `PAIR.md` (задачи 10–12).
План карты: `docs/map-poi-plan.html`, шаги «Подписи районов из файлов игры», «Входы в данжи», «Рейдовые боссы».
Зоны программы (код → map id): `dc1` 120010000, `df1` 220010000, `df1a` 220030000, `df2` 220020000,
`df2a` 220050000, `df3` 220040000, `df4` 220070000, `lf4` 210050000, `underpass` 600010000.

## Правила

Как в прошлых задачах: игровую папку только читать; новое из клиента — в `client_extract/raw/`, временное — в
`tmp/` и удалить; `data/`, `watcher/`, `tools/build_poi.py` не трогать — подключает Claude. Можно добавить свой
инструмент выгрузки в `tools/` (например `tools/export_map_extras.py`), чтобы выгрузку можно было повторить.
В конце — строка в журнал `PAIR.md`, статусы задач 10–12, строка в `client_extract/README.md`.

## 10. Подписи районов из файлов игры

Сейчас подписи районов на карте взяты с aiondb (`data/maps/labels.tsv`) и стоят иначе, чем в игре.
В `client_extract/raw/Data/world/world/client_world_<зона>.xml` у каждой `<subzone>` есть `<name>`, `<string>`
(ключ вида `STR_SZ_DF4_A3`), `<ui_map>` (`main` / `zoom` / …), `<map_points><map_point>` с x, y, z — по ним игра
сама пишет названия на своей карте.

Нужно: `client_extract/raw/subzone_labels.tsv` с колонками `zone`, `map_id`, `subzone`, `string_key`, `name_ru`,
`ui_map`, `x`, `y`, `z` — по строке на каждый `map_point` (у подзоны их может быть несколько). Русское название —
из русских строк клиента (`client_extract/raw/l10n/rus/data/Strings/*.xml`, обычно `client_strings_level.xml` или
`client_strings_dic_place.xml`; если ключа нет в `strings_ru.tsv` — поищи во всех файлах `Strings/`). В отчёте:
сколько подписей по зонам, какие значения `ui_map` бывают и что они значат (по подзонам видно, какие подписи
крупные, а какие только при приближении), у скольких не нашлось названия.

## 11. Входы в данжи

На игровой карте есть фильтр «Вход в данж» (значок `abyss_indun` уже вырезан). Координат входов пока не
нашли. Поищи в клиенте: объекты уровней (`client_extract/client_level_entities.tsv`, `client_level_objects.tsv`,
при необходимости заново выгрузить больше классов сущностей из `levels/<зона>/level.pak` → `mission_mission0.xml`),
`Data/world/*.xml` (WorldId, client_world — `<subzone>` с названием «Вход в …», key_point), строки
`STR_SZ_*` со словом «Вход». Нужно: `client_extract/raw/dungeon_entrances.tsv` — `zone`, `map_id`, `name_ru`,
`target` (куда ведёт, если известно), `x`, `y`, `z`, `source` (откуда взята точка). Если подходит только
`map_point` подзоны «Вход в …» — так и отметь в `source`.

## 12. Рейдовые боссы

В `client_abyss.xml` есть `BossRaid`: `df4_3111` («Теграк») и `lf4_2111` («Гера»), но в `client_world` у них только
граница зоны (`abyss_boundary_area`). Проверь, нет ли точки появления босса (NPC с подходящим id в `npc_info`,
сущность в данных уровня, `key_point`). Нужно: строки в отчёте с координатами или вывод, что точки в клиенте нет.

## Отчёт

`client_extract/raw/REPORT_MAP_EXTRAS.md`: что нашлось по 10–12, файлы, количества по зонам, ограничения.
