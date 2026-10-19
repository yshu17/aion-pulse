<h1 align="center">⚡ Pulse</h1>

<p align="center">
  <b>Помощник для Aion Empire: следит за чатом и зовёт, когда найдено то, что нужно тебе</b>
</p>

<p align="center">
  <a href="https://github.com/yshu17/aion-pulse/releases/latest">
    <img src="https://img.shields.io/badge/%D1%81%D0%BA%D0%B0%D1%87%D0%B0%D1%82%D1%8C-Pulse.exe-ff8c1a?style=for-the-badge&logo=github&logoColor=white" alt="Скачать Pulse.exe">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/github/v/release/yshu17/aion-pulse?label=%D0%B2%D0%B5%D1%80%D1%81%D0%B8%D1%8F&color=ff8c1a" alt="Версия">
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078d4?logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white" alt="Python">
</p>

<p align="center">
  <a href="README_FULL.md">📖 Полная версия</a> ·
  <a href="https://github.com/yshu17/aion-pulse/releases">📦 Релизы</a> ·
  <a href="README_FULL.md#%EF%B8%8F-configjson">⚙️ config.json</a>
</p>

<p align="center">
  <img src="screenshots/01-matches.png" alt="Pulse — вкладка «Поиск»" width="95%">
</p>

## ✨ Возможности

- 🔔 **Поиск** — сигнал, когда в «Поиске группы» появилось ключевое слово или ссылка на отмеченный предмет
- 🎒 **Что искать** — 11 тыс. предметов с 45-го уровня: иконки, цвет по качеству, фильтры и подсказки с характеристиками
- 💬 **Весь чат** — все каналы в одном окне, ссылки на предметы, места и задания читаются названиями
- 🗺️ **Карта** — оригинальные карты игры: привратники, склады, торговцы, NPC с заданиями
- 📅 **Расписание** — события сервера в твоём времени и напоминания
- 🛡️ **Безопасно** — Pulse только читает `Chat.log`; клиент, память игры и ввод не трогаются

## 🚀 Быстрый старт

1. Скачай [Pulse.exe](https://github.com/yshu17/aion-pulse/releases/latest) и запусти.
2. В `system.cfg` игры включи лог чата: `g_chatlog = "1"`.
3. В **Настройки** укажи **Папку игры** (`Aion Empire`).
4. Введи **Ключевые слова** или отметь предметы в **Что искать**.
5. Нажми **Start** — статус сменится на «● Слежу».

## 📸 Скриншоты

| 🎒 Что искать | 🗺️ Карта |
|:---:|:---:|
| <img src="screenshots/02-items.png" alt="Что искать"> | <img src="screenshots/03-map.png" alt="Карта"> |
| **📅 Расписание** | **⚙️ Настройки** |
| <img src="screenshots/04-schedule.png" alt="Расписание"> | <img src="screenshots/05-settings.png" alt="Настройки"> |

## 🛠️ Из исходников

```
pip install -r requirements.txt
python main.py
```

---

<p align="center">
  Режимы оповещения, фильтры, карта, <code>config.json</code>, данные и разработка —
  в <a href="README_FULL.md"><b>📖 полной версии</b></a>.
</p>
