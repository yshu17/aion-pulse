from watcher.gamecheck import game_running, process_names


def test_game_running_by_process_name():
    assert game_running(["explorer.exe", "AION.bin"]) is True
    assert game_running(["explorer.exe", "aion_chat_watcher.exe"]) is False


def test_process_list_of_this_machine():
    names = process_names()
    assert names is not None and any(n.startswith("python") for n in names)
    assert game_running() in (True, False)
