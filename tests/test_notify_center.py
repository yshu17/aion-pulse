from watcher.notify_center import NotificationAction, NotificationCenter


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def test_disabled_source_is_ignored_without_sound_or_count():
    sounds = []
    center = NotificationCenter(sound=sounds.append)
    center.set_source("chat", enabled=False)

    assert center.notify("chat", "chat", "Match", "hello") is None
    assert center.count() == center.queued == center.unread == 0
    assert sounds == []


def test_notification_is_queued_counted_and_sound_is_per_source():
    sounds = []
    center = NotificationCenter(sound=sounds.append)
    center.set_source("schedule", sound=False)
    action = NotificationAction("map", "На карте")
    event = center.notify("schedule", "event", "Siege", "Abyss", [action])

    assert event is not None and event.actions == (action,)
    assert center.count("schedule") == center.count() == center.unread == 1
    assert center.pop_next() == event
    assert center.pop_next() is None
    assert sounds == []
    assert center.acknowledge(event.id)
    assert center.unread == 0


def test_do_not_disturb_suppresses_queue_but_keeps_count_and_sound():
    sounds = []
    center = NotificationCenter(sound=sounds.append)
    center.do_not_disturb = True

    event = center.notify("chat", "match", "Found", "hello")

    assert event is not None
    assert center.queued == 0
    assert center.count("chat") == center.unread == 1
    assert sounds == [event]


def test_queue_drops_oldest_when_full():
    center = NotificationCenter(max_queue=2)
    first = center.notify("chat", "match", "One")
    second = center.notify("chat", "match", "Two")
    third = center.notify("chat", "match", "Three")

    assert center.queued == 2
    assert center.pop_next() == second
    assert center.pop_next() == third
    assert first is not None


def test_snooze_emits_again_after_delay_and_ack_cancels_it():
    clock = FakeClock()
    center = NotificationCenter(clock=clock)
    event = center.notify("schedule", "event", "Soon")
    assert event is not None
    center.pop_next()

    assert center.snooze(event.id, 5)
    clock.advance(4.9)
    assert center.tick() == 0
    clock.advance(0.1)
    assert center.tick() == 1
    repeated = center.pop_next()
    assert repeated is not None and repeated.id != event.id

    assert center.acknowledge(repeated.id)
    clock.advance(100)
    assert center.tick() == 0


def test_unacknowledged_repeat_repeats_and_reaction_stops_the_series():
    clock = FakeClock()
    center = NotificationCenter(clock=clock)
    event = center.notify("chat", "match", "Found", repeat_after=10)
    assert event is not None
    center.pop_next()

    clock.advance(10)
    assert center.tick() == 1
    repeated = center.pop_next()
    assert repeated is not None and repeated.repeat_key == event.id
    assert center.acknowledge(repeated.id)
    clock.advance(60)
    assert center.tick() == 0
