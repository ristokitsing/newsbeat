from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def test_compose_caps_batch_and_static_server_resources() -> None:
    compose = yaml.load(
        (ROOT / "compose.yaml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    services = compose["services"]

    worker = services["newsbeat-digest"]
    assert worker["mem_limit"] == "384m"
    assert worker["cpus"] == "0.5"
    assert worker["restart"] == "no"
    assert worker["environment"]["AI_DIGEST_DATABASE_PATH"] == "/data/digest.db"
    assert "./data:/data" in worker["volumes"]
    assert "./feed:/app/feed" in worker["volumes"]
    assert "./digests:/app/digests" in worker["volumes"]

    feed = services["static-feed"]
    assert feed["mem_limit"] == "48m"
    assert feed["ports"] == ["127.0.0.1:8088:8080"]
    assert feed["read_only"] == "true"


def test_systemd_timer_runs_four_times_in_tallinn() -> None:
    timer = (ROOT / "deploy/systemd/newsbeat-digest.timer").read_text(
        encoding="utf-8"
    )
    service = (ROOT / "deploy/systemd/newsbeat-digest.service").read_text(
        encoding="utf-8"
    )

    assert timer.count("OnCalendar=") == 4
    assert timer.count("Europe/Tallinn") == 4
    for hour in ("07:07", "11:07", "16:07", "21:07"):
        assert f"{hour}:00 Europe/Tallinn" in timer
    assert "Persistent=true" in timer
    assert "docker compose run --rm newsbeat-digest" in service
    assert "flock -n /run/lock/newsbeat-digest.lock" in service


def test_image_uses_python_314_and_unprivileged_runtime() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.14-slim")
    assert "PIP_NO_CACHE_DIR=1" in dockerfile
    assert "MALLOC_ARENA_MAX=2" in dockerfile
    assert "USER digest" in dockerfile
    assert 'ENTRYPOINT ["newsbeat-digest"]' in dockerfile


def test_generated_runtime_files_are_ignored() -> None:
    ignored = set(
        (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    )

    assert {"data/", "feed/", "digests/", "digest.db"} <= ignored
    assert {"*.egg-info/", "build/", "dist/"} <= ignored
