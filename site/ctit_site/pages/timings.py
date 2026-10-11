"""timings.html: daily clang-tidy check timings, summed over chosen checks and
projects. The times of each check are in timings/checks/<check>.js, which the
page loads for the checks it needs."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, timedelta

from ..markup import esc, render
from ..model import slug
from ..timings import TimingsDay
from ..writer import Site

# Projects summed when a page opens; all of them if none of these exist.
DEFAULT_PROJECTS = {"llvm-project"}
TITLE = "CTIT Results: Timings"

Series = dict[str, list[float | None]]


def _checkboxes(projects: list[str]) -> str:
    defaults = DEFAULT_PROJECTS.intersection(projects)
    boxes = []
    for project in projects:
        checked = " checked" if project in defaults or not defaults else ""
        boxes.append(
            f'<label><input type="checkbox" name="project" value="{esc(project)}"'
            f'{checked} autocomplete="off" /> {esc(project)}</label>\n'
        )
    return "".join(boxes)


def _encode(data: object) -> str:
    # "<" is escaped so that the data cannot end the <script> element early.
    return json.dumps(data, sort_keys=True).replace("<", "\\u003c")


def _series(days: list[TimingsDay], values: Callable[[TimingsDay], dict]) -> Series:
    """{project: [seconds or None for each day]}."""
    projects = sorted({p for day in days for p in values(day)})
    return {p: [values(day).get(p) for day in days] for p in projects}


def _comparison_days(days: list[TimingsDay]) -> list[int | None]:
    """The latest run, the run before it, and the latest run a week earlier,
    among the runs with per-project check times."""
    detailed = [i for i, day in enumerate(days) if day.project_checks]
    if not detailed:
        return [None, None, None]
    latest = detailed[-1]
    cutoff = date.fromisoformat(days[latest].date) - timedelta(days=7)
    week = next(
        (i for i in reversed(detailed) if date.fromisoformat(days[i].date) <= cutoff),
        None,
    )
    return [latest, detailed[-2] if len(detailed) > 1 else None, week]


def _check_table(days: list[TimingsDay], names: list[str], projects: list[str]) -> dict:
    """The times of every check on the days of _comparison_days, per project,
    so that the page can sum them over the checked projects."""
    compared = _comparison_days(days)

    def seconds(check: str, project: str, i: int | None) -> float | None:
        if i is None:
            return None
        return days[i].project_checks.get(check, {}).get(project)

    return {
        "names": names,
        "days": compared,
        "values": {
            project: [[seconds(name, project, i) for i in compared] for name in names]
            for project in projects
        },
    }


def _write_days(site: Site, days: list[TimingsDay]) -> None:
    """timings/days.js: the runs, shared by every timings page."""
    runs = [
        {
            "date": day.date,
            "run": day.github_run_url,
            "llvm": day.llvm_revision,
            "runner": day.runner,
            # Whether the run has per-project check times.
            "detailed": bool(day.project_checks),
        }
        for day in days
    ]
    path = site.out / "timings" / "days.js"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"window.TIMINGS_DAYS = {json.dumps(runs)};\n" "window.TIMINGS_CHECKS = {};\n"
    )


def _write_check(site: Site, days: list[TimingsDay], check: str) -> None:
    """timings/checks/<check>.js: in_run[i] is 1 if the check ran in run i
    (0 before it was added to clang-tidy or after it was removed), and
    projects[project][i] its time on the project, None where it did not run
    on the project."""
    data = {
        "in_run": [int(check in day.project_checks) for day in days],
        "projects": _series(days, lambda day: day.project_checks.get(check, {})),
    }
    path = site.out / "timings" / "checks" / f"{slug(check)}.js"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"window.TIMINGS_CHECKS[{json.dumps(check)}] = {json.dumps(data)};\n"
    )


def build_timings(site: Site, days: list[TimingsDay]) -> None:
    if not days:
        body = '<h3>Check timings:</h3>\n<p class="dim">No timings yet.</p>\n'
        site.write("timings.html", TITLE, body)
        return
    _write_days(site, days)
    check_series = _series(days, lambda day: day.check_seconds)
    projects = list(check_series)
    names = sorted({check for day in days for check in day.project_checks})
    data = {
        "metrics": {
            "check": {"label": "check time", "title": "Check time"},
            "analysis": {"label": "analysis time", "title": "Analysis time"},
        },
        "series": {
            "check": check_series,
            "analysis": _series(days, lambda day: day.analysis_seconds),
        },
        "checks": _check_table(days, names, projects),
    }
    body = render("timings.html", projects=_checkboxes(projects), data=_encode(data))
    site.write("timings.html", TITLE, body)
    for check in names:
        _write_check(site, days, check)
