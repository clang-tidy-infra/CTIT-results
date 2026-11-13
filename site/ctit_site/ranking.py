"""Where the checks of a run would rank by check time among the checks of a
nightly timings run."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Run
from .timings import TimingsDay

# The projects check times are summed over, so that the times of different runs
# are comparable however many projects each run had. They are in every daily
# timings run and take long enough that most checks get a nonzero time on them.
# llvm-project is left out: it takes over twenty times longer than all of them
# together and would decide every ranking alone.
RANKING_PROJECTS = ("cppcheck", "doxygen", "poco")


def module(check: str) -> str:
    """The clang-tidy module of a check: bugprone for bugprone-use-after-move."""
    parts = check.split("-")
    return "-".join(parts[:2]) if parts[0] == "clang" else parts[0]


@dataclass
class Entry:
    check: str
    seconds: float


@dataclass
class Ranking:
    """Where a check of a run falls among the checks of a nightly run, by their
    times summed over the same projects."""

    day: TimingsDay
    check: str
    # The RANKING_PROJECTS the check ran on in the run that the nightly run has
    # check times for; all the times are summed over them.
    projects: list[str]
    # The time of the check in the run.
    seconds: float
    # {check: seconds} of the nightly run, only of the checks that ran on every
    # one of `projects`: a check left out of a project, say for needing a newer
    # C++ standard than the project uses, would look faster than it is.
    nightly: dict[str, float]

    def entries(self, of_module: str | None = None) -> list[Entry]:
        """The checks of the nightly run, slowest first, with the run's time of
        the check in place of its nightly time; only those of `of_module` if
        given."""
        times = {**self.nightly, self.check: self.seconds}
        entries = [
            Entry(check, seconds)
            for check, seconds in times.items()
            if of_module is None or module(check) == of_module
        ]
        entries.sort(key=lambda entry: (-entry.seconds, entry.check))
        return entries


def latest_detailed(days: list[TimingsDay]) -> TimingsDay | None:
    """The latest nightly run with per-project check times."""
    return next((day for day in reversed(days) if day.project_checks), None)


def rank(run: Run, day: TimingsDay, check: str) -> Ranking | None:
    """Sum the times of `check` in the run, and of the checks of the nightly run
    that ran on all the same projects, over the RANKING_PROJECTS the check ran
    on in the run; None if there are no such projects."""
    nightly_projects = {p for times in day.project_checks.values() for p in times}
    # {project: seconds} of the check in the run.
    run_times: dict[str, float] = {}
    for name in RANKING_PROJECTS:
        project = run.projects.get(name)
        profile = (project.check_profile if project else None) or {}
        if name in nightly_projects and check in profile:
            run_times[name] = profile[check]
    if not run_times:
        return None
    projects = list(run_times)
    seconds = sum(run_times.values())
    nightly = {
        name: sum(times[project] for project in projects)
        for name, times in day.project_checks.items()
        if all(project in times for project in projects)
    }
    return Ranking(day, check, projects, seconds, nightly)
