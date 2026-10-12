"""Show SN-2 demo cards; --capture saves only those cards and then exits."""
import argparse
import sys
import tkinter as tk
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageGrab
from main import enable_dpi_awareness
from watcher.notify_center import NotificationAction, NotificationCenter
from watcher.toasts import ToastManager
from watcher.toast_native import WindowsDesktop


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--scale", type=float, default=1)
    args = parser.parse_args()
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    center = NotificationCenter()
    area = replace(WindowsDesktop().work_area(), scale=args.scale)
    manager = ToastManager(root, center, on_open=lambda event: print(event.title),
                           work_area=lambda: area, duration=20)
    center.notify("schedule", "siege", "Осада через 15 минут", "Келькмарос · Храм красной земли",
                  [NotificationAction("open", "Открыть"), NotificationAction("snooze", "Через 5 мин")])
    center.notify("chat", "chat", "Найдено в поиске группы", "Ник: собираем группу в Удас, нужен хил.",
                  [NotificationAction("accept", "Принять")])
    center.notify("game", "warning", "Игра не запущена", "Запустите Aion и нажмите Start.")
    manager.start()

    def close():
        manager.close()
        root.destroy()

    def capture():
        shots = [ImageGrab.grab(bbox=(card.x, card.y, card.x + card.width, card.y + card.height), all_screens=True)
                 for card in reversed(manager.cards)]
        result = Image.new("RGB", (max(image.width for image in shots), sum(image.height for image in shots) + 12 * (len(shots) - 1)), "#141519")
        y = 0
        for shot in shots:
            result.paste(shot, (0, y))
            y += shot.height + 12
        args.capture.parent.mkdir(parents=True, exist_ok=True)
        result.save(args.capture)
        print(args.capture)
        close()

    if args.capture:
        root.after(700, capture)
    else:
        root.after(22000, close)
    root.mainloop()


if __name__ == "__main__":
    main()
