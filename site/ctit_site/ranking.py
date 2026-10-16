"""Where the checks of a run would rank by check time among the checks of a
nightly timings run."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Run
from .timings import TimingsDay


def module(check: str) -> str:
    """The clang-tidy module of a check: bugprone for bugprone-use-after-move."""
    parts = check.split("-")
    return "-".join(parts[:2]) if parts[0] == "clang" else parts[0]


@dataclass
class Entry:
    check: str
    seconds: float
    # Whether the time is from the run rather than from the nightly run.
    new: bool


@dataclass
class Ranking:
    day: TimingsDay
    # The projects both runs have check times for; the times are summed over them.
    projects: list[str]
    # {check: seconds} of the run and of the nightly run.
    run: dict[str, float]
    nightly: dict[str, float]

    def entries(self, of_module: str | None = None) -> list[Entry]:
        """The checks of the nightly run, slowest first, with the run's checks
        in place of their nightly times; only those of `of_module` if given."""
        entries = [
            Entry(check, seconds, check in self.run)
            for check, seconds in {**self.nightly, **self.run}.items()
            if of_module is None or module(check) == of_module
        ]
        entries.sort(key=lambda entry: (-entry.seconds, entry.check))
        return entries


def latest_detailed(days: list[TimingsDay]) -> TimingsDay | None:
    """The latest nightly run with per-project check times."""
    return next((day for day in reversed(days) if day.project_checks), None)


def rank(run: Run, day: TimingsDay) -> Ranking | None:
    """Sum the check times of the run and of the nightly run over the projects
    both have them for; None if there are no such projects."""
    profiles = {
        name: project.check_profile
        for name, project in run.projects.items()
        if project.check_profile
    }
    nightly_projects = {p for times in day.project_checks.values() for p in times}
    projects = sorted(nightly_projects.intersection(profiles))
    if not projects:
        return None
    run_times: dict[str, float] = {}
    for project in projects:
        for check, seconds in profiles[project].items():
            run_times[check] = run_times.get(check, 0.0) + seconds
    nightly_times = {
        check: sum(times.get(project, 0.0) for project in projects)
        for check, times in day.project_checks.items()
        if any(project in times for project in projects)
    }
    return Ranking(day, projects, run_times, nightly_times)
