from watcher.gamecheck import game_running, process_names


def test_game_running_by_process_name():
    assert game_running(["explorer.exe", "AION.bin"]) is True
    assert game_running(["explorer.exe", "aion_chat_watcher.exe"]) is False
    names = process_names()  # the real list of this machine
    assert names is not None and any(n.startswith("python") for n in names)
