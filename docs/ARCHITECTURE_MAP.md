# Карта архитектуры Aion Chat Watcher (13.10.2026)

Построено по реальным импортам `watcher/*.py` (40 модулей). Tk — модуль импортирует `tkinter`.

## 1. Ядра без Tk (переносимы в лаунчер)

```mermaid
flowchart LR
  subgraph core[Ядро без Tk]
    parser --> catalog
    matcher --> parser
    poi --> matcher
    series --> matcher & parser
    alerts --> parser
    reminders
    schedule_view --> reminders
    schedule_custom --> reminders
    notify_center
    alert_bridge --> notify_center
    notify_settings
    schedule_update
    config
    gamecheck
    tailer
    notifier
    specs
    errlog
    tgbatch
  end
```

## 2. Экраны (Tk) и их зависимости

```mermaid
flowchart TB
  app[app.py — владелец состояния] --> feed & allchat & itemlist & mapview & schedule_tab & notify_tab & alarm & toasts
  feed --> emptystate & textview & ui_icons & motion
  allchat --> textview & emptystate & tailer
  itemlist --> hint & ui_icons
  mapview --> mapcard & poi & hint & ui_icons
  schedule_tab --> schedule_view & schedule_custom & hint & ui_icons & motion
  notify_tab --> notify_settings
  alarm --> motion & window_icon
  toasts --> toast_native & notify_center
  ui_icons --> theme
  tooltip --> motion
```

## 3. Поток данных: от лога до уведомления

```mermaid
sequenceDiagram
  participant Log as Chat.log
  participant T as tailer
  participant P as parser
  participant M as matcher
  participant A as app._process
  participant AL as alerts (tracker)
  participant AB as alert_bridge
  participant NC as notify_center
  participant TS as toasts (Tk)
  participant F as feed (Tk)
  Log->>T: новые строки
  T->>A: lines
  A->>P: parse_line
  P->>M: check(msg)
  M-->>A: hits
  A->>AL: add (nag / standard)
  A->>F: add row
  A->>AB: chat_match(alerts, entries, nag)
  AB->>NC: notify(chat)
  NC->>TS: pop_next
  TS-->>AB: accept -> toast_accepted
  AB-->>A: alert ids -> _accept
```

## 4. Расписание: данные и правки

```mermaid
flowchart LR
  data[(data/schedule.json — сетка сервера, не правится программой)]
  custom[(schedule_custom.json — свои правки)]
  data --> merge[Custom.merge]
  custom --> merge
  merge --> view[schedule_view: next_events, day_label, group_of, clock_pair]
  view --> tab[schedule_tab: Ближайшие, По дням, форма, текст]
  tab -->|add / edit / remove| custom
  reminders --> view
  update[schedule_update: отпечаток картинки] --> app
```

## 5. Где состояние и таймеры (Tk)

| Владелец | Состояние | Таймер (after) |
|---|---|---|
| app.py | cfg, tracker, series, матчер, очередь проверки обновления | `_ui_tick`, `_check_reminders` (30 с), `_tick` (poll), проверка расписания (5 с после старта) |
| schedule_tab | events, belled, hidden, custom | `refresh` (30 с), `tick_now` (5 с) |
| toasts | карточки, очередь center | `_poll` (33 мс) |
| alarm | звук по кругу | `_repeat_beep`, `_blink` |
| motion (animate, tween) | — | кадры по запросу, отменяемые |

## 6. Что переносится, что нет

- Переносимо: блоки раздела 1 (около 25 модулей без Tk).
- Не переносится напрямую: раздел 2. Пересобирается в React по макетам.
- Общие точки: `config.json` и `schedule_custom.json` — формат JSON, его читает и лаунчер.

## 7. Размеры (измерено)

- `app.py` 1277 строк — самый большой узел: импортирует 31 модуль.
- `mapview.py` 1020, `theme.py` 858, `schedule_tab.py` 562, `feed.py` 302.
- Ядра без Tk: большинство модулей до 200 строк.
