from watcher.tgbatch import ChatBatcher


def feed(batcher, count, now, start=0):
    for i in range(start, start + count):
        batcher.add(f"line {i}", now)


def test_two_lines_go_out_at_once_as_one_message():
    b = ChatBatcher()
    b.add("a", 0)
    assert b.poll(0) == []  # waits for a partner line
    b.add("b", 0.5)
    assert b.poll(0.5) == ["a\nb"]


def test_lone_line_is_sent_after_flush_delay():
    b = ChatBatcher(flush_after=3)
    b.add("a", 0)
    assert b.poll(2.9) == []
    assert b.poll(3.0) == ["a"]


def test_switches_to_four_lines_at_18_messages_a_minute():
    b = ChatBatcher()
    feed(b, 36, 0)
    out = b.poll(0)
    assert len(out) == 18 and all(m.count("\n") == 1 for m in out)  # 18 messages of 2 lines
    assert b.compact and b.batch_size == 4
    feed(b, 8, 1, start=36)
    out = b.poll(1)
    # message 19 holds 4 lines; message 20 is the last free slot and takes the rest
    assert [m.count("\n") + 1 for m in out] == [4, 4]
    assert b.sent_last_window(1) == 20


def test_never_more_than_20_messages_in_a_minute():
    b = ChatBatcher()
    total = 0
    for second in range(0, 120):
        feed(b, 3, second, start=second * 3)
        sent = b.poll(second)
        total += len(sent)
        assert b.sent_last_window(second) <= 20
    assert total <= 40
    for second in range(120, 240):  # load stops: packing empties the queue
        b.poll(second)
    assert b.queued == 0


def test_no_line_lost_or_reordered_under_load():
    b = ChatBatcher()
    got = []
    n = 0
    for second in range(0, 300):
        for _ in range(5):
            b.add(f"{n}", second)
            n += 1
        for message in b.poll(second):
            got += message.split("\n")
    for second in range(300, 500):
        for message in b.poll(second):
            got += message.split("\n")
    assert got == [str(i) for i in range(n)]


def test_back_to_two_lines_when_traffic_drops():
    b = ChatBatcher()
    feed(b, 36, 0)
    b.poll(0)
    assert b.compact
    feed(b, 2, 61, start=36)
    assert b.poll(61) == ["line 36\nline 37"]  # minute passed: window empty, normal size again
    assert not b.compact


def test_message_never_exceeds_4096_chars():
    b = ChatBatcher(limit=1, warn_at=1, relax_below=1)
    for i in range(50):
        b.add("x" * 300, 0)
    out = b.poll(0)
    assert len(out) == 1 and len(out[0]) <= 4096
    assert b.queued == 50 - out[0].count("\n") - 1


def test_queue_limit_drops_oldest():
    b = ChatBatcher(max_queue=3)
    for i in range(5):
        b.add(str(i), 0)
    assert b.queued == 3 and b.dropped == 2


def test_next_slot_in():
    b = ChatBatcher(limit=2, warn_at=2, relax_below=1)
    feed(b, 4, 0)
    b.poll(0)
    assert b.next_slot_in(10) == 50
    assert b.next_slot_in(60) == 0
