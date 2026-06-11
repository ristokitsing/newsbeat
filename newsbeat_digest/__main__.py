"""Command-line entry point for the newsbeat-digest processor."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from newsbeat_digest.collect import InsertedItem, collect_items
from newsbeat_digest.config import Settings
from newsbeat_digest.db import Database
from newsbeat_digest.logging_utils import configure_logging
from newsbeat_digest.models import RankedItem


COMMANDS = ("collect", "score", "brief", "publish", "run", "backfill")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="newsbeat-digest",
        description="Collect and publish a personal AI news digest.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        subparsers.add_parser(command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    configure_logging()
    database = Database(settings.database_path)
    database.initialize()

    handlers = {
        "collect": _collect,
        "score": _score,
        "brief": _brief,
        "publish": _publish,
        "run": _run,
        "backfill": _backfill,
    }
    try:
        return handlers[args.command](settings, database)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


def _collect(
    settings: Settings,
    database: Database,
    *,
    lookback_hours: int = 12,
) -> int:
    result = collect_items(
        database,
        settings.project_root / "sources.yaml",
        lookback_hours=lookback_hours,
    )
    _print_items(result.inserted)
    print(
        f"Fetched {result.fetched_count} items and collected "
        f"{len(result.inserted)} new items. "
        f"Database contains {database.count_items()} items."
    )
    if result.failed_sources:
        print(f"Failed sources: {', '.join(result.failed_sources)}")
    return 0


def _score(settings: Settings, database: Database) -> int:
    from newsbeat_digest.pipeline.phase3 import score_and_select

    result = score_and_select(settings, database)
    _print_ranked(result.ranked)
    print(
        f"Clustered {result.clustered_representatives} representatives, "
        f"rejected {result.duplicate_items} duplicates, scored "
        f"{result.scored_items}, selected {result.selected_items}, and "
        f"left {result.failed_items} unscored after failures."
    )
    return 0


def _brief(settings: Settings, database: Database) -> int:
    from newsbeat_digest.pipeline.brief import generate_briefs

    created, failed = generate_briefs(settings, database)
    print(f"Created {created} briefs. {failed} items failed.")
    return 0


def _publish(settings: Settings, database: Database) -> int:
    from newsbeat_digest.publish import publish_digest

    result = publish_digest(settings, database)
    print(
        f"Published {result.feed_items} feed items and marked "
        f"{result.delivered_items} newly delivered."
    )
    print(f"JSON: {result.json_path}")
    print(f"RSS: {result.rss_path}")
    print(f"Archive: {result.archive_path}")
    return 0


def _run(settings: Settings, database: Database) -> int:
    print("Running collect, score/select, brief, and publish.")
    _collect(settings, database)
    _score(settings, database)
    _brief(settings, database)
    _publish(settings, database)
    return 0


def _backfill(settings: Settings, database: Database) -> int:
    _collect(settings, database, lookback_hours=24 * 7)
    _score(settings, database)
    _brief(settings, database)
    _publish(settings, database)
    return 0


def _print_items(inserted: tuple[InsertedItem, ...]) -> None:
    if not inserted:
        return
    print(f"{'ID':>5}  {'SOURCE':<24}  TITLE")
    for inserted_item in inserted:
        item_id = inserted_item.id
        raw_item = inserted_item.item
        source = raw_item.source[:24]
        title = raw_item.title.replace("\n", " ")
        print(f"{item_id:>5}  {source:<24}  {title}")


def _print_ranked(ranked: tuple[RankedItem, ...]) -> None:
    if not ranked:
        return
    print(f"{'RANK':>6}  {'REL':>4}  {'CATEGORY':<10}  {'STATUS':<9}  TITLE")
    for entry in ranked:
        item = entry.item
        title = item.title.replace("\n", " ")
        print(
            f"{entry.rank:>6.2f}  {(item.llm_score or 0):>4.1f}  "
            f"{(item.llm_category or 'other'):<10}  "
            f"{item.status.value:<9}  {title}"
        )


if __name__ == "__main__":
    sys.exit(main())
