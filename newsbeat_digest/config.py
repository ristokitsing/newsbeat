"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "Europe/Tallinn"
DEFAULT_MAX_ITEMS = 8
DEFAULT_SCORE_MODEL = "claude-haiku-4-5"
DEFAULT_BRIEF_MODEL = "claude-haiku-4-5"


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    database_path: Path
    anthropic_api_key: str | None
    pages_url: str | None
    timezone: str
    max_items: int
    score_model: str | None
    brief_model: str | None

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "Settings":
        root = (project_root or Path.cwd()).resolve()
        dotenv = _read_env_file(root / ".env")
        timezone = _get_setting(
            "AI_DIGEST_TIMEZONE",
            dotenv,
            DEFAULT_TIMEZONE,
        )
        _validate_timezone(timezone)

        max_items_text = _get_setting(
            "AI_DIGEST_MAX_ITEMS",
            dotenv,
            str(DEFAULT_MAX_ITEMS),
        )
        try:
            max_items = int(max_items_text)
        except ValueError as exc:
            raise ValueError("AI_DIGEST_MAX_ITEMS must be an integer") from exc
        if max_items < 1:
            raise ValueError("AI_DIGEST_MAX_ITEMS must be at least 1")

        database_path = Path(
            _get_setting("AI_DIGEST_DATABASE_PATH", dotenv, "digest.db")
        ).expanduser()
        if not database_path.is_absolute():
            database_path = root / database_path

        return cls(
            project_root=root,
            database_path=database_path,
            anthropic_api_key=_get_setting("ANTHROPIC_API_KEY", dotenv) or None,
            pages_url=_get_setting("AI_DIGEST_PAGES_URL", dotenv) or None,
            timezone=timezone,
            max_items=max_items,
            score_model=(
                _get_setting(
                    "AI_DIGEST_SCORE_MODEL",
                    dotenv,
                    DEFAULT_SCORE_MODEL,
                )
                or None
            ),
            brief_model=(
                _get_setting(
                    "AI_DIGEST_BRIEF_MODEL",
                    dotenv,
                    DEFAULT_BRIEF_MODEL,
                )
                or None
            ),
        )


def _validate_timezone(timezone: str) -> None:
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown AI_DIGEST_TIMEZONE: {timezone}") from exc


def _get_setting(
    name: str,
    dotenv: Mapping[str, str],
    default: str = "",
) -> str:
    return os.environ.get(name, dotenv.get(name, default))


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            raise ValueError(f"Invalid .env entry on line {line_number}")

        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            raise ValueError(f"Invalid .env entry on line {line_number}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value
    return values
