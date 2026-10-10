"""data/runs.json: a machine-readable summary of every run, newest first."""

from __future__ import annotations

import json

from ..model import Run
from ..writer import Site, run_href


def build_summary(site: Site, runs: list[Run]) -> None:
    summary = []
    for run in reversed(runs):
        summary.append(
            {
                "id": run.id,
                "path": run.path,
                "page": run_href(run),
                "github_run_id": run.data["github_run_id"],
                "github_run_attempt": run.data["github_run_attempt"],
                "pr_number": run.pr,
                "check_name": run.check,
                "llvm_revision": run.data["llvm_revision"],
                "runner_arch": run.data["runner_arch"],
                "started_at": run.data["started_at"],
                "duration_seconds": run.data["duration_seconds"],
                "status": run.status,
                "has_baseline": bool(run.data.get("baseline")),
                "projects": {
                    name: {
                        "status": p.status,
                        "duration_seconds": p.duration,
                        "warnings": len(p.diagnostics),
                        "tp": p.count("TP"),
                        "fp": p.count("FP"),
                    }
                    for name, p in sorted(run.projects.items())
                },
            }
        )
    path = site.out / "data" / "runs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=1) + "\n")
