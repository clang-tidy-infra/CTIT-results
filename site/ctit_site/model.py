"""Run records loaded from runs/**/*.json."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CTIT_URL = "https://github.com/clang-tidy-infra/CTIT"
LLVM_URL = "https://github.com/llvm/llvm-project"

DiagnosticKey = tuple[str, int, int, str]


def parse_time(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def slug(value: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in value)


@dataclass
class Diagnostic:
    file: str
    line: int
    column: int
    message: str
    verdict: str | None

    @property
    def key(self) -> DiagnosticKey:
        return (self.file, self.line, self.column, self.message)


@dataclass
class ProjectRun:
    name: str
    status: str
    duration: float | None
    diagnostics: list[Diagnostic]

    def count(self, verdict: str | None) -> int:
        return sum(1 for d in self.diagnostics if d.verdict == verdict)


@dataclass
class Run:
    id: str
    path: str
    data: dict
    projects: dict[str, ProjectRun]
    baseline: dict[str, ProjectRun] | None
    sources: dict[str, str]

    @property
    def started(self) -> datetime:
        return parse_time(self.data["started_at"])

    @property
    def finished(self) -> datetime:
        return parse_time(self.data["finished_at"])

    @property
    def check(self) -> str:
        return str(self.data["check_name"])

    @property
    def pr(self) -> int | None:
        pr = self.data.get("pr_number")
        return int(pr) if pr is not None else None

    @property
    def status(self) -> str:
        return str(self.data["status"])

    @property
    def group(self) -> str:
        prefix = f"pr-{self.pr}" if self.pr else "main"
        return slug(f"{prefix}-{self.check}")

    @property
    def github_run_url(self) -> str:
        run_id = self.data["github_run_id"]
        attempt = self.data["github_run_attempt"]
        return f"{CTIT_URL}/actions/runs/{run_id}/attempts/{attempt}"

    @property
    def label(self) -> str:
        attempt = self.data["github_run_attempt"]
        suffix = f"/{attempt}" if attempt > 1 else ""
        return f"{self.data['github_run_id']}{suffix}"

    def total(self, verdict: str | None = "*") -> int:
        if verdict == "*":
            return sum(len(p.diagnostics) for p in self.projects.values())
        return sum(p.count(verdict) for p in self.projects.values())


def read_project_runs(items: Iterable[dict]) -> dict[str, ProjectRun]:
    runs = {}
    for item in items:
        diagnostics = [
            Diagnostic(
                file=d["file"],
                line=d["line"],
                column=d["column"],
                message=d["message"],
                verdict=d.get("verdict"),
            )
            for d in item["diagnostics"]
        ]
        diagnostics.sort(key=lambda d: d.key)
        runs[item["project"]] = ProjectRun(
            name=item["project"],
            status=item["status"],
            duration=item.get("duration_seconds"),
            diagnostics=diagnostics,
        )
    return runs


def load_runs(
    results_dir: Path, sources_at: Callable[[datetime], dict[str, str]]
) -> list[Run]:
    """Load every run, oldest first.

    `sources_at` maps a run's start time to the project source links in use
    at that time.
    """
    runs = []
    for path in sorted((results_dir / "runs").glob("**/*.json")):
        data = json.loads(path.read_text())
        baseline = data.get("baseline") or None
        baseline_runs = None
        if baseline and baseline.get("project_runs") is not None:
            baseline_runs = read_project_runs(baseline["project_runs"])
        run = Run(
            id=path.stem,
            path=path.relative_to(results_dir).as_posix(),
            data=data,
            projects=read_project_runs(data["project_runs"]),
            baseline=baseline_runs,
            sources={},
        )
        run.sources = sources_at(run.started)
        runs.append(run)
    runs.sort(key=lambda r: (r.started, r.id))
    return runs


def diff(
    old: list[Diagnostic], new: list[Diagnostic]
) -> tuple[list[Diagnostic], list[Diagnostic]]:
    """Return (added, removed) diagnostics, treating each list as a multiset."""
    old_keys = Counter(d.key for d in old)
    new_keys = Counter(d.key for d in new)
    added = []
    for d in new:
        if old_keys[d.key] > 0:
            old_keys[d.key] -= 1
        else:
            added.append(d)
    removed = []
    for d in old:
        if new_keys[d.key] > 0:
            new_keys[d.key] -= 1
        else:
            removed.append(d)
    return added, removed
