import tkinter as tk

import pytest

from watcher.alarm import NagAlarm
from watcher.parser import ChatMessage


class FakeNotifier:
    def __init__(self, loops: bool) -> None:
        self.loops = loops
        self.calls: list[str] = []

    def start_loop(self) -> bool:
        self.calls.append("loop")
        return self.loops

    def play(self) -> None:
        self.calls.append("play")

    def stop(self) -> None:
        self.calls.append("stop")


def msg(nick, text):
    return ChatMessage(time="2026.10.08 18:43:17", nick=nick, text=text, raw="")


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def make(root, loops=True):
    flashes = []
    notifier = FakeNotifier(loops)
    alarm = NagAlarm(root, notifier, flash=lambda on: flashes.append(on))
    return alarm, notifier, flashes


def window_text(alarm):
    return alarm.text.get("1.0", "end")


def test_trigger_opens_window_loops_sound_and_flashes(root):
    alarm, notifier, flashes = make(root)
    alarm.trigger([(msg("Seller", "WTS [Клинок Рудры]"), ["Клинок Рудры"])])
    assert alarm.window is not None and alarm.window.winfo_exists()
    assert alarm.sounding is True
    assert notifier.calls == ["loop"]
    assert flashes == [True]
    assert "Seller: WTS [Клинок Рудры]" in window_text(alarm)


def test_more_matches_append_without_restarting_sound(root):
    alarm, notifier, _ = make(root)
    alarm.trigger([(msg("A", "wts ммк"), ["ммк"])])
    alarm.trigger([(msg("B", "куплю ммк"), ["ммк"])])
    text = window_text(alarm)
    assert "A: wts ммк" in text and "B: куплю ммк" in text
    assert notifier.calls == ["loop"]


def test_hover_silences_but_keeps_window(root):
    alarm, notifier, flashes = make(root)
    alarm.trigger([(msg("A", "wts"), ["wts"])])
    alarm.text.event_generate("<Enter>")
    assert alarm.sounding is False
    assert notifier.calls == ["loop", "stop"]
    assert flashes == [True, False]
    assert alarm.window is not None


def test_click_on_message_silences(root):
    alarm, notifier, _ = make(root)
    alarm.trigger([(msg("A", "wts"), ["wts"])])
    alarm.silence_on_click(None)
    assert alarm.sounding is False


def test_ok_closes_and_silences(root):
    alarm, notifier, flashes = make(root)
    alarm.trigger([(msg("A", "wts"), ["wts"])])
    alarm.close()
    assert alarm.window is None
    assert alarm.sounding is False
    assert notifier.calls == ["loop", "stop"]
    assert flashes[-1] is False


def test_new_match_after_silence_rings_again(root):
    alarm, notifier, _ = make(root)
    alarm.trigger([(msg("A", "wts"), ["wts"])])
    alarm.silence()
    alarm.trigger([(msg("B", "wts"), ["wts"])])
    assert alarm.sounding is True
    assert notifier.calls == ["loop", "stop", "loop"]


def test_without_wav_repeats_beep(root):
    alarm, notifier, _ = make(root, loops=False)
    alarm.trigger([(msg("A", "wts"), ["wts"])])
    assert notifier.calls == ["loop", "play"]
    alarm._repeat_beep()
    assert notifier.calls == ["loop", "play", "play"]
    alarm.close()
    alarm._repeat_beep()  # a late timer after close must not ring
    assert notifier.calls[-1] == "stop"


def test_without_popup_only_rings(root):
    alarm, notifier, flashes = make(root)
    alarm.trigger([(msg("A", "wts"), ["wts"])], popup=False)
    assert alarm.window is None
    assert alarm.sounding is True and flashes == [True]
    alarm.silence()
    assert notifier.calls == ["loop", "stop"]


def test_popup_reactions_notify_app(root):
    acks = []
    alarm = NagAlarm(root, FakeNotifier(True), flash=lambda on: None, on_ack=lambda: acks.append(1))
    alarm.trigger([(msg("A", "wts"), ["wts"])])
    alarm.text.event_generate("<Enter>")
    assert acks == [1]
    alarm.text.event_generate("<Enter>")  # already silent: hovering again is not a new reaction
    assert acks == [1]
    alarm.trigger([(msg("B", "wts"), ["wts"])])
    alarm._on_ok()
    assert acks == [1, 1]
    assert alarm.window is None
