from core.update.updater import latest_release, newer, parse_version


def test_versions_compare_numerically():
    assert parse_version("v1.2.10") == (1, 2, 10)
    assert newer("v1.10.0", "1.9.9") and not newer("1.0.0", "v1.0.0")


def test_release_json_gives_tag_and_page():
    body = '{"tag_name": "v1.1.0", "html_url": "https://github.com/x/y/releases/tag/v1.1.0"}'
    assert latest_release(body) == ("v1.1.0", "https://github.com/x/y/releases/tag/v1.1.0")
    assert latest_release("{}") is None


def test_release_address_comes_from_the_repository_name():
    from core.update.updater import release_api

    assert release_api("owner/name") == "https://api.github.com/repos/owner/name/releases/latest"
