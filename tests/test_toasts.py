import ctypes
import tkinter as tk

import pytest

from watcher.notify_center import NotificationAction, NotificationCenter
from watcher.toast_native import WorkArea
from watcher.toasts import ToastManager


@pytest.fixture
def toast_env():
    now = [0.0]
    clock = lambda: now[0]
    root = tk.Tk()
    root.withdraw()
    center = NotificationCenter(clock=clock)
    opened = []
    manager = ToastManager(root, center, clock=clock, on_open=opened.append,
                           reduce_motion=lambda: True,
                           work_area=lambda: WorkArea(0, 0, 1600, 1000))
    try:
        yield root, center, manager, now, opened
    finally:
        manager.close()
        root.destroy()


def publish(center, count=1):
    return [center.notify("chat", "chat", f"Заголовок {i}", "Сообщение из чата", sound=False)
            for i in range(count)]


def test_stack_waits_for_slot_and_expiration_does_not_acknowledge(toast_env):
    root, center, manager, now, _ = toast_env
    events = publish(center, 4)
    manager.pump()
    root.update()
    assert len(manager.cards) == 3 and center.queued == 1
    for card in manager.cards:
        card.hovered = lambda: False
    now[0] = 8.3
    manager.pump()
    assert len(manager.cards) == 1
    assert manager.cards[0].event == events[-1]
    assert center.unread == 4


def test_hover_pauses_and_click_opens_then_acknowledges(toast_env):
    _, center, manager, now, opened = toast_env
    event = publish(center)[0]
    manager.pump()
    card = manager.cards[0]
    card.hovered = lambda: True
    now[0] = 30
    manager.pump()
    assert card.remaining == 8
    manager.act(card, "open")
    assert opened == [event] and not manager.cards and center.unread == 0


def test_snooze_requeues_once_and_keeps_silent_event_silent(toast_env):
    _, center, manager, now, _ = toast_env
    sounds = []
    center._sound = sounds.append
    publish(center)
    manager.pump()
    manager.act(manager.cards[0], "snooze")
    now[0] = 299
    manager.pump()
    assert not manager.cards
    now[0] = 300
    manager.pump()
    assert len(manager.cards) == 1 and sounds == []
    manager.act(manager.cards[0], "snooze")
    now[0] = 600
    manager.pump()
    assert len(manager.cards) == 1


def test_dnd_hides_cards_and_drops_queued_visuals(toast_env):
    _, center, manager, _, _ = toast_env
    publish(center, 4)
    manager.pump()
    center.do_not_disturb = True
    manager.pump()
    assert not manager.cards and center.queued == 0 and center.count() == 4
    center.do_not_disturb = False
    manager.pump()
    assert not manager.cards


def test_native_style_prevents_activation_and_handles_negative_monitor(toast_env):
    root, center, manager, _, _ = toast_env
    manager._area = WorkArea(-1600, -200, 0, 800, 1.5)
    publish(center)
    desktop = manager.desktop
    desktop.user.GetForegroundWindow.restype = ctypes.c_void_p
    foreground = desktop.user.GetForegroundWindow()
    manager.pump()
    root.update()
    card = manager.cards[0]
    assert desktop.user.GetForegroundWindow() == foreground
    style = desktop.user.GetWindowLongW(card.native.hwnd, -20)
    assert style & 0x08000000 and style & 0x80
    assert card.x < 0 and card.width == 570
    assert card.x + card.width <= manager._area.right


def test_action_buttons_and_timer_cleanup(toast_env):
    root, center, manager, _, _ = toast_env
    center.notify("schedule", "siege", "Осада", "Через 15 минут",
                  [NotificationAction("accept", "Принять"), NotificationAction("snooze", "Позже")], sound=False)
    manager.start()
    manager.pump()
    card = manager.cards[0]
    assert len(card.action_boxes) == 2
    for box, _ in card.action_boxes:
        assert box[2] <= card.width and box[3] < card.height
    timer = manager._after
    manager.close()
    assert not manager.cards
    assert timer not in root.tk.call("after", "info")


@pytest.mark.parametrize("scale", [1, 1.25, 1.5, 2])
def test_dpi_layout_keeps_text_buttons_and_frame_inside_window(toast_env, scale):
    _, center, manager, _, _ = toast_env
    manager._area = WorkArea(0, 0, 1920, 1080, scale)
    center.notify("chat", "warning", "Очень длинное название уведомления " * 8,
                  "Очень длинное сообщение для проверки переноса строк. " * 50,
                  [NotificationAction("accept", "Принять"), NotificationAction("snooze", "Через 5 мин")], sound=False)
    manager.pump()
    card = manager.cards[0]
    assert card.width == round(380 * scale)
    assert card.height < 400 * scale
    for box, _ in card.action_boxes:
        assert box[2] < card.width and box[3] < card.height


def test_accept_reaches_the_app_and_acknowledges(toast_env):
    """SN-4: «Принять» on a chat toast must accept the chat alerts — the app has to hear it."""
    root, center, manager, now, _ = toast_env
    heard = []
    manager.on_action = lambda event, action: heard.append((event.id, action))
    event = center.notify("chat", "chat", "Найдено", "Nick: wts", [NotificationAction("accept", "Принять")], sound=False)
    manager.pump()
    root.update()
    manager.act(manager.cards[0], "accept")
    assert heard == [(event.id, "accept")]
    assert not center.is_active(event)


def test_top_corner_stacks_cards_from_the_top(toast_env):
    """SN-5: «Справа сверху» — the first card sits at the top edge, the next one below it."""
    root, center, manager, now, _ = toast_env
    manager.corner = "top"
    publish(center, 2)
    manager.pump()
    root.update()
    first, second = manager.cards
    assert first.window.winfo_y() < 100
    assert second.window.winfo_y() > first.window.winfo_y()
