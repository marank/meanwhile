"""
config.env: reading the configuration from the environment.
"""

from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import env

LONG_KEY = "k" * 40


@pytest.mark.parametrize("value", ["", "change-me", "changeme", "secret", "too-short"])
def test_secret_key_refuses_placeholders_outside_debug(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("SECRET_KEY", value)
    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        env.secret_key(debug=False)


def test_secret_key_falls_back_to_a_dev_key_in_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "change-me")
    assert env.secret_key(debug=True).startswith("django-insecure-")


def test_secret_key_takes_a_long_random_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", LONG_KEY)
    assert env.secret_key(debug=False) == LONG_KEY
    assert env.secret_key(debug=True) == LONG_KEY


@pytest.mark.parametrize(("value", "expected"), [("true", True), ("ON", True), ("0", False), ("", False)])
def test_env_bool(monkeypatch: pytest.MonkeyPatch, value: str, expected: bool) -> None:
    monkeypatch.setenv("FLAG", value)
    assert env.env_bool("FLAG") is expected


def test_env_bool_refuses_other_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLAG", "maybe")
    with pytest.raises(ImproperlyConfigured):
        env.env_bool("FLAG")


def test_env_bool_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLAG", raising=False)
    assert env.env_bool("FLAG", True) is True


def test_env_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NUMBER", "42")
    assert env.env_int("NUMBER", 1) == 42
    monkeypatch.setenv("NUMBER", "")
    assert env.env_int("NUMBER", 1) == 1
    monkeypatch.setenv("NUMBER", "many")
    with pytest.raises(ImproperlyConfigured):
        env.env_int("NUMBER", 1)


def test_env_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ITEMS", " a, b ,,c ")
    assert env.env_list("ITEMS") == ["a", "b", "c"]
    monkeypatch.delenv("ITEMS")
    assert env.env_list("ITEMS", ["x"]) == ["x"]


def test_env_str(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NAME", raising=False)
    assert env.env_str("NAME", "fallback") == "fallback"
    with pytest.raises(ImproperlyConfigured):
        env.env_str("NAME")


def test_parse_app_urls_derives_hosts_and_origins() -> None:
    urls = env.parse_app_urls(["https://cal.example.com", "http://localhost:8080", "https://x.example.com:443"])
    assert [u.hostname for u in urls] == ["cal.example.com", "localhost", "x.example.com"]
    assert [u.origin for u in urls] == ["https://cal.example.com", "http://localhost:8080", "https://x.example.com"]


@pytest.mark.parametrize("urls", [[], ["cal.example.com"], ["ftp://cal.example.com"]])
def test_parse_app_urls_refuses_bad_entries(urls: list[str]) -> None:
    with pytest.raises(ImproperlyConfigured):
        env.parse_app_urls(urls)


def test_load_dotenv_keeps_existing_variables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text('# comment\nexport NEW_ONE="quoted"\nKEPT=from-file\nnot a line\n')
    monkeypatch.setenv("KEPT", "from-env")
    monkeypatch.delenv("NEW_ONE", raising=False)

    env.load_dotenv(tmp_path / "missing", dotenv)

    import os

    assert os.environ["NEW_ONE"] == "quoted"
    assert os.environ["KEPT"] == "from-env"
