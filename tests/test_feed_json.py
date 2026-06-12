from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from newsbeat_digest.config import Settings
from newsbeat_digest.db import Database
from newsbeat_digest.models import BriefContent, RawItem
from newsbeat_digest.publish import publish_digest


CONTENT: BriefContent = {
    "what_happened": "A provider released an AI model. Technical details were published.",
    "why_it_matters": "The model could change practical workflows. Independent evaluation is still needed.",
    "linkedin_angle": {
        "hook": "The practical test starts after launch day.",
        "points": ["Test quality", "Measure cost", "Check reliability"],
    },
    "instagram_carousel": {
        "slides": ["New model", "Key change", "Practical impact", "Open question"],
        "cta": "What would you test first?",
    },
    "caution": "Performance claims have not been independently verified.",
}

# A summary-only brief, as produced by the pipeline after Phase 2.
SUMMARY: BriefContent = {
    "what_happened": "A research group shared an update. It posted limited detail.",
    "why_it_matters": "It hints at a useful direction. The evidence is still thin.",
    "caution": "No full article text was available for this story.",
}


def _insert_briefed_item(
    database: Database,
    *,
    url: str,
    cluster: str,
    content: BriefContent,
    digest_date: date,
    digest_slot: str = "am",
) -> int:
    item_id = database.insert_item(
        RawItem(
            title=f"Story {cluster}",
            url=url,
            published_at=None,
            source="Example",
        )
    )
    assert item_id is not None
    with database.connect() as connection:
        connection.execute(
            """
            UPDATE items
            SET status = 'selected',
                cluster_id = ?,
                llm_score = 8.0,
                llm_category = 'models'
            WHERE id = ?
            """,
            (cluster, item_id),
        )
    assert database.insert_brief(
        item_id,
        content,
        digest_date=digest_date,
        digest_slot=digest_slot,
    )
    return item_id


def test_feed_omits_social_keys_for_summary_only_briefs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_DIGEST_DATABASE_PATH", str(tmp_path / "digest.db"))
    settings = Settings.from_env(tmp_path)
    database = Database(settings.database_path)
    database.initialize()
    today = date(2026, 6, 10)
    _insert_briefed_item(
        database,
        url="https://example.com/legacy",
        cluster="legacy",
        content=CONTENT,
        digest_date=today,
    )
    _insert_briefed_item(
        database,
        url="https://example.com/summary",
        cluster="summary",
        content=SUMMARY,
        digest_date=today,
    )

    result = publish_digest(
        settings,
        database,
        now=datetime(2026, 6, 10, 9, tzinfo=ZoneInfo("Europe/Tallinn")),
    )
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    by_title = {item["title"]: item for item in payload["items"]}

    legacy = by_title["Story legacy"]
    assert "linkedin_angle" in legacy
    assert "instagram_carousel" in legacy

    summary = by_title["Story summary"]
    assert "linkedin_angle" not in summary
    assert "instagram_carousel" not in summary
    # Summary fields are always present, social ones are not.
    assert summary["what_happened"]
    assert summary["why_it_matters"]
    assert summary["caution"]


def test_feed_retention_keeps_recent_days_newest_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_DIGEST_DATABASE_PATH", str(tmp_path / "digest.db"))
    settings = Settings.from_env(tmp_path)
    database = Database(settings.database_path)
    database.initialize()
    _insert_briefed_item(
        database,
        url="https://example.com/today",
        cluster="today",
        content=SUMMARY,
        digest_date=date(2026, 6, 10),
    )
    _insert_briefed_item(
        database,
        url="https://example.com/six-days",
        cluster="six-days",
        content=SUMMARY,
        digest_date=date(2026, 6, 4),
    )
    _insert_briefed_item(
        database,
        url="https://example.com/eight-days",
        cluster="eight-days",
        content=SUMMARY,
        digest_date=date(2026, 6, 2),
    )

    result = publish_digest(
        settings,
        database,
        now=datetime(2026, 6, 10, 9, tzinfo=ZoneInfo("Europe/Tallinn")),
    )
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    dates = [item["digest_date"] for item in payload["items"]]

    # Today and six days ago survive (newest first); eight days ago is dropped.
    assert dates == ["2026-06-10", "2026-06-04"]


def test_digest_json_has_required_fields_and_publish_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, database = _briefed_database(tmp_path, monkeypatch)
    now = datetime(2026, 6, 10, 15, tzinfo=ZoneInfo("Europe/Tallinn"))

    first = publish_digest(settings, database, now=now)
    second = publish_digest(settings, database, now=now)

    payload = json.loads(first.json_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["timezone"] == "Europe/Tallinn"
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert {
        "id",
        "title",
        "url",
        "source",
        "digest_date",
        "digest_slot",
        "what_happened",
        "why_it_matters",
        "linkedin_angle",
        "instagram_carousel",
        "caution",
    } <= set(item)
    assert len(item["linkedin_angle"]["points"]) == 3
    assert len(item["instagram_carousel"]["slides"]) == 4
    assert first.delivered_items == 1
    assert second.delivered_items == 0
    assert second.archive_path.exists()

    with database.connect() as connection:
        delivered = connection.execute(
            "SELECT COUNT(*) FROM delivered_clusters"
        ).fetchone()[0]
    assert delivered == 1


def test_published_feed_retains_seven_digest_dates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_DIGEST_DATABASE_PATH", str(tmp_path / "digest.db"))
    settings = Settings.from_env(tmp_path)
    database = Database(settings.database_path)
    database.initialize()
    for day in range(1, 9):
        digest_date = datetime(2026, 6, day).date()
        item_id = database.insert_item(
            RawItem(
                title=f"Story from June {day}",
                url=f"https://example.com/story-{day}",
                published_at=f"2026-06-{day:02d}T08:00:00+00:00",
                source="Example",
            )
        )
        assert item_id is not None
        with database.connect() as connection:
            connection.execute(
                """
                UPDATE items
                SET status = 'selected',
                    cluster_id = ?,
                    llm_score = 8.0,
                    llm_category = 'models'
                WHERE id = ?
                """,
                (f"story-{day}", item_id),
            )
        assert database.insert_brief(
            item_id,
            CONTENT,
            digest_date=digest_date,
            digest_slot="am",
        )

    result = publish_digest(
        settings,
        database,
        now=datetime(
            2026,
            6,
            8,
            15,
            tzinfo=ZoneInfo("Europe/Tallinn"),
        ),
    )
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))

    assert {item["digest_date"] for item in payload["items"]} == {
        f"2026-06-{day:02d}" for day in range(2, 9)
    }
    assert database.count_items() == 8


def _briefed_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Settings, Database]:
    monkeypatch.setenv("AI_DIGEST_DATABASE_PATH", str(tmp_path / "digest.db"))
    settings = Settings.from_env(tmp_path)
    database = Database(settings.database_path)
    database.initialize()
    item_id = database.insert_item(
        RawItem(
            title="Provider releases a useful AI model",
            url="https://example.com/model",
            published_at="2026-06-10T08:00:00+00:00",
            source="Example",
        )
    )
    assert item_id is not None
    with database.connect() as connection:
        connection.execute(
            """
            UPDATE items
            SET status = 'selected',
                cluster_id = 'example-model',
                llm_score = 8.7,
                llm_category = 'models'
            WHERE id = ?
            """,
            (item_id,),
        )
    brief_id = database.insert_brief(
        item_id,
        CONTENT,
        digest_date=datetime(2026, 6, 10).date(),
        digest_slot="pm",
    )
    assert brief_id is not None
    return settings, database
