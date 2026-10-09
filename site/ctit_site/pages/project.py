"""run/<id>/<project>.html: every warning one project produced in one run."""

from __future__ import annotations

from collections import Counter

from ..markup import (
    diagnostics_table,
    esc,
    fmt_duration,
    kv_table,
    link,
    status_html,
)
from ..model import ProjectRun, Run, diff, slug
from ..writer import Site, group_title, run_href

ROOT = "../../"


def build_project(site: Site, run: Run, project: ProjectRun) -> None:
    source = run.sources.get(project.name)
    meta = [
        ("Run", link(run_href(run, ROOT), run.label)),
        ("Check", group_title(run, ROOT)),
        ("Status", status_html(project.status)),
        ("Time", fmt_duration(project.duration)),
        (
            "Warnings",
            (
                f"{len(project.diagnostics)} "
                f"(TP {project.count('TP')}, FP {project.count('FP')}, "
                f"unclassified {project.count(None)})"
            ),
        ),
    ]
    if source:
        meta.append(
            ("Source", link(source, source.removeprefix("https://github.com/")))
        )
    body = f"<h3>{esc(project.name)}:</h3>\n{kv_table(meta)}"

    base = run.baseline.get(project.name) if run.baseline is not None else None
    if base is not None:
        added, removed = diff(base.diagnostics, project.diagnostics)
        added_keys = Counter(d.key for d in added)
        kept = []
        for d in project.diagnostics:
            if added_keys[d.key] > 0:
                added_keys[d.key] -= 1
            else:
                kept.append(d)
        body += (
            f"<h4>New warnings, not in baseline ({len(added)}):</h4>\n"
            f"{diagnostics_table(added, source)}"
            f"<h4>Gone, only in baseline ({len(removed)}):</h4>\n"
            f"{diagnostics_table(removed, source)}"
            f"<h4>Unchanged, also in baseline ({len(kept)}):</h4>\n"
            f"{diagnostics_table(kept, source)}"
        )
    else:
        body += (
            f"<h4>Warnings ({len(project.diagnostics)}):</h4>\n"
            f"{diagnostics_table(project.diagnostics, source)}"
        )
    site.write(
        f"run/{run.id}/{slug(project.name)}.html",
        f"CTIT Run {run.label}: {project.name}",
        body,
    )
