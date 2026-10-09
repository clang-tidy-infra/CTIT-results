#!/usr/bin/env python3
"""Build the static CTIT results website from the run records in runs/."""

from __future__ import annotations

import argparse
import os
import shutil
from collections import defaultdict
from pathlib import Path

from ctit_site.model import Run, load_runs
from ctit_site.pages.about import build_about
from ctit_site.pages.checks import build_checks
from ctit_site.pages.compare import build_compare
from ctit_site.pages.index import build_index
from ctit_site.pages.project import build_project
from ctit_site.pages.run import build_run
from ctit_site.pages.summary import build_summary
from ctit_site.sources import ProjectSources
from ctit_site.writer import Site

STATIC_DIR = Path(__file__).resolve().parent / "static"


def build(
    results_dir: Path,
    out: Path,
    ctit_dir: Path | None,
    repository: str,
    revision: str | None,
) -> int:
    runs = load_runs(results_dir, ProjectSources(ctit_dir).at)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(STATIC_DIR, out)
    site = Site(out, repository, revision)

    groups: dict[str, list[Run]] = defaultdict(list)
    for run in runs:
        groups[run.group].append(run)

    build_index(site, groups)
    build_checks(site, runs)
    build_about(site)
    build_summary(site, runs)
    for group_runs in groups.values():
        for index, run in enumerate(group_runs):
            previous = group_runs[index - 1] if index > 0 else None
            following = group_runs[index + 1] if index + 1 < len(group_runs) else None
            build_run(site, run, previous, following)
            for project in run.projects.values():
                build_project(site, run, project)
            if previous is not None:
                build_compare(site, previous, run)
    return len(runs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results", type=Path, default=Path("."), help="CTIT-results checkout"
    )
    parser.add_argument(
        "--out", type=Path, default=Path("_site"), help="output directory"
    )
    parser.add_argument(
        "--ctit",
        type=Path,
        help="CTIT git clone, used to link warnings to the project sources",
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", "clang-tidy-infra/CTIT-results"),
    )
    parser.add_argument("--revision", default=os.environ.get("GITHUB_SHA"))
    args = parser.parse_args()
    count = build(args.results, args.out, args.ctit, args.repository, args.revision)
    print(f"Built site for {count} runs in {args.out}")


if __name__ == "__main__":
    main()
