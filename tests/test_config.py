from pathlib import Path

import pytest

from newsbeat_digest.config import (
    DEFAULT_MAX_ITEMS,
    DEFAULT_SCORE_MODEL,
    DEFAULT_TIMEZONE,
    Settings,
)


def test_settings_use_phase_one_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "ANTHROPIC_API_KEY",
        "AI_DIGEST_PAGES_URL",
        "AI_DIGEST_TIMEZONE",
        "AI_DIGEST_MAX_ITEMS",
        "AI_DIGEST_SCORE_MODEL",
        "AI_DIGEST_BRIEF_MODEL",
        "AI_DIGEST_DATABASE_PATH",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env(tmp_path)

    assert settings.database_path == tmp_path / "digest.db"
    assert settings.timezone == DEFAULT_TIMEZONE
    assert settings.max_items == DEFAULT_MAX_ITEMS
    assert settings.anthropic_api_key is None
    assert settings.score_model == DEFAULT_SCORE_MODEL


def test_settings_reject_invalid_max_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_DIGEST_MAX_ITEMS", "zero")

    with pytest.raises(ValueError, match="must be an integer"):
        Settings.from_env(tmp_path)


def test_settings_load_dotenv_without_overriding_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".env").write_text(
        "AI_DIGEST_MAX_ITEMS=6\nAI_DIGEST_PAGES_URL=https://example.com/feed/\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_DIGEST_MAX_ITEMS", "7")
    monkeypatch.delenv("AI_DIGEST_PAGES_URL", raising=False)

    settings = Settings.from_env(tmp_path)

    assert settings.max_items == 7
    assert settings.pages_url == "https://example.com/feed/"
