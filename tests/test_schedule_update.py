"""SN-9: has the schedule on the knowledge base changed? Compare the grid picture's name and headers, no parsing of it."""

from watcher.schedule_update import decide, fingerprint, image_url, site_fingerprint

PAGE = '<p><img src="https://news.aionempire.net/storage/app/media/schedule-20ru.jpg" alt=""></p>'
KNOWN = {"image": "schedule-20ru.jpg", "image_etag": '"6a942095-f31b0"', "image_modified": "Sun, 30 Aug 2026 12:22:45 GMT"}


def test_image_url_is_the_schedule_picture():
    assert image_url(PAGE) == "https://news.aionempire.net/storage/app/media/schedule-20ru.jpg"
    assert image_url("<p>нет картинки</p>") is None


def test_fingerprint_of_the_data_and_of_the_site_match_when_nothing_changed():
    known = fingerprint(KNOWN["image"], KNOWN["image_etag"], KNOWN["image_modified"])
    current = fingerprint("schedule-20ru.jpg", '"6a942095-f31b0"', "Sun, 30 Aug 2026 12:22:45 GMT")
    assert known == current
    assert fingerprint("schedule-21ru.jpg", "x", "y") != known


def test_decide_says_what_to_tell():
    known, new = "a", "b"
    assert decide(known, known, seen="", manual=False) is None  # same at start: say nothing
    assert decide(known, known, seen="", manual=True) == "same"
    assert decide(known, new, seen="", manual=False) == "changed"
    assert decide(known, new, seen=new, manual=False) is None  # the user already acknowledged this version
    assert decide(known, new, seen=new, manual=True) == "changed"  # a manual check always answers


def test_site_fingerprint_reads_the_page_then_heads_the_picture():
    calls = []

    def fetch(url, method):
        calls.append((url, method))
        if method == "GET":
            return PAGE, {}
        return "", {"ETag": '"6a942095-f31b0"', "Last-Modified": "Sun, 30 Aug 2026 12:22:45 GMT"}

    assert site_fingerprint(fetch) == fingerprint(KNOWN["image"], KNOWN["image_etag"], KNOWN["image_modified"])
    assert calls[0][1] == "GET" and calls[1] == ("https://news.aionempire.net/storage/app/media/schedule-20ru.jpg", "HEAD")


def test_site_fingerprint_without_a_picture_raises():
    import pytest
    with pytest.raises(ValueError):
        site_fingerprint(lambda url, method: ("<p></p>", {}))
