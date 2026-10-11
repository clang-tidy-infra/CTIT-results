"""Daily check timings records loaded from timings/**/*.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .model import CTIT_URL


@dataclass
class TimingsDay:
    date: str
    path: str
    run_id: int
    attempt: int
    llvm_revision: str
    runner: str
    # {project: seconds}; a project is missing if its log had no timings.
    check_seconds: dict[str, float]
    analysis_seconds: dict[str, float]
    # {check: {project: seconds}}; empty for records written before the
    # per-project check times were kept.
    project_checks: dict[str, dict[str, float]]

    @property
    def github_run_url(self) -> str:
        return f"{CTIT_URL}/actions/runs/{self.run_id}/attempts/{self.attempt}"


def _seconds(projects: dict, key: str) -> dict[str, float]:
    return {
        name: float(values[key])
        for name, values in projects.items()
        if values.get(key) is not None
    }


def _project_checks(data: dict) -> dict[str, dict[str, float]]:
    """Turn the record's columns back into {check: {project: seconds}}."""
    names: list[str] = data.get("check_names", [])
    result: dict[str, dict[str, float]] = {}
    for project, column in data.get("project_checks", {}).items():
        for name, seconds in zip(names, column, strict=True):
            if seconds is not None:
                result.setdefault(name, {})[project] = float(seconds)
    return result


def load_timings(results_dir: Path) -> list[TimingsDay]:
    """Load one timings record per day, oldest first.

    A day with several runs (a rerun or a manual run) keeps the latest one.
    """
    days: dict[str, TimingsDay] = {}
    for path in sorted((results_dir / "timings").glob("**/*.json")):
        data = json.loads(path.read_text())
        day = TimingsDay(
            date=data["date"],
            path=path.relative_to(results_dir).as_posix(),
            run_id=int(data["github_run_id"]),
            attempt=int(data["github_run_attempt"]),
            llvm_revision=data["llvm_revision"],
            runner=data["runner_name"],
            check_seconds=_seconds(data["projects"], "check_seconds"),
            analysis_seconds=_seconds(data["projects"], "duration_seconds"),
            project_checks=_project_checks(data),
        )
        current = days.get(day.date)
        if current is None or (day.run_id, day.attempt) > (
            current.run_id,
            current.attempt,
        ):
            days[day.date] = day
    return [days[date] for date in sorted(days)]
