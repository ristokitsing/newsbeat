"""Simple title-similarity deduplication and stable cluster assignment."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from newsbeat_digest.db import Database
from newsbeat_digest.models import Item, ItemStatus


TITLE_SIMILARITY_THRESHOLD = 0.78
_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(slots=True)
class _Cluster:
    cluster_id: str
    representative: Item


def cluster_new_items(database: Database) -> tuple[int, int]:
    pending = database.list_items(ItemStatus.NEW)
    if not pending:
        return 0, 0

    existing = [
        item
        for item in database.list_items()
        if item.status is not ItemStatus.NEW
        and item.cluster_id
        and item.cluster_representative
    ]
    clusters = [
        _Cluster(str(item.cluster_id), item)
        for item in sorted(existing, key=_representative_key, reverse=True)
    ]
    assignments: dict[int, tuple[str, bool]] = {}

    for item in sorted(pending, key=_representative_key, reverse=True):
        cluster = _best_cluster(item, clusters)
        if cluster is None:
            cluster = _Cluster(_cluster_id(item), item)
            clusters.append(cluster)
            assignments[item.id] = (cluster.cluster_id, True)
            continue

        assignments[item.id] = (cluster.cluster_id, False)
        if _representative_key(item) > _representative_key(
            cluster.representative
        ):
            previous = cluster.representative
            assignments[previous.id] = (cluster.cluster_id, False)
            assignments[item.id] = (cluster.cluster_id, True)
            cluster.representative = item

    database.set_clusters(
        [
            (item_id, cluster_id, representative)
            for item_id, (cluster_id, representative) in assignments.items()
        ]
    )
    rejected = database.reject_new_cluster_duplicates()
    representatives = sum(
        1
        for item in database.list_items(ItemStatus.NEW)
        if item.cluster_representative
    )
    return representatives, rejected


def title_similarity(first: str, second: str) -> float:
    normalized_first = _normalize_title(first)
    normalized_second = _normalize_title(second)
    if not normalized_first or not normalized_second:
        return 0.0
    sequence = SequenceMatcher(
        None,
        normalized_first,
        normalized_second,
    ).ratio()
    first_words = set(normalized_first.split())
    second_words = set(normalized_second.split())
    union = first_words | second_words
    jaccard = len(first_words & second_words) / len(union) if union else 0.0
    return max(sequence, jaccard)


def _best_cluster(item: Item, clusters: list[_Cluster]) -> _Cluster | None:
    best: _Cluster | None = None
    best_similarity = TITLE_SIMILARITY_THRESHOLD
    for cluster in clusters:
        similarity = title_similarity(item.title, cluster.representative.title)
        if similarity >= best_similarity:
            best = cluster
            best_similarity = similarity
    return best


def _normalize_title(title: str) -> str:
    return " ".join(_WORD_RE.findall(title.casefold()))


def _cluster_id(item: Item) -> str:
    digest = hashlib.sha256(item.canonical_url.encode("utf-8")).hexdigest()
    return f"c_{digest[:16]}"


def _representative_key(item: Item) -> tuple[float, str, int]:
    return (item.score_hint, item.first_seen_at, item.id)
