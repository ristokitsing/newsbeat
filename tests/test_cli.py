from pathlib import Path

import pytest

from newsbeat_digest.collect import CollectionResult
from newsbeat_digest.__main__ import main


def test_collect_initializes_database_and_exits_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "digest.db"
    monkeypatch.setenv("AI_DIGEST_DATABASE_PATH", str(database_path))
    monkeypatch.setattr(
        "newsbeat_digest.__main__.collect_items",
        lambda *args, **kwargs: CollectionResult((), 0, ()),
    )

    exit_code = main(["collect"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert database_path.exists()
    assert "collected 0 new items" in output


@pytest.mark.parametrize(
    "command",
    ["score", "brief", "publish", "run", "backfill"],
)
def test_remaining_phase_one_commands_exit_cleanly(
    command: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AI_DIGEST_DATABASE_PATH",
        str(tmp_path / f"{command}.db"),
    )
    monkeypatch.setattr(
        "newsbeat_digest.__main__.collect_items",
        lambda *args, **kwargs: CollectionResult((), 0, ()),
    )

    assert main([command]) == 0


def test_score_reports_missing_key_when_items_need_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from newsbeat_digest.db import Database
    from newsbeat_digest.models import RawItem

    database_path = tmp_path / "score.db"
    monkeypatch.setenv("AI_DIGEST_DATABASE_PATH", str(database_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "profile.md").write_text("# Profile", encoding="utf-8")
    database = Database(database_path)
    database.initialize()
    database.insert_item(
        RawItem(
            title="New AI model",
            url="https://example.com/model",
            published_at=None,
            source="Example",
        )
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["score"])

    assert exit_code == 2
    assert "ANTHROPIC_API_KEY is required" in capsys.readouterr().err
    assert database.list_items()[0].cluster_id is None
