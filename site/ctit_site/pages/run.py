"""run/<id>.html: one run's metadata and per-project summary."""

from __future__ import annotations

from collections import Counter

from ..markup import (
    esc,
    fmt_duration,
    fmt_signed,
    fmt_time,
    kv_table,
    link,
    revision_html,
    status_html,
)
from ..model import Run, diff
from ..writer import Site, compare_href, group_title, project_href, run_href

ROOT = "../"


def run_metadata(
    site: Site, run: Run, previous: Run | None, following: Run | None
) -> list[tuple[str, str]]:
    data = run.data
    links = [
        link(run.github_run_url, "GitHub run"),
        link(site.results_url(run), "JSON"),
    ]
    if data.get("artifact_url"):
        links.insert(1, link(data["artifact_url"], "logs"))
    config = data.get("check_config") or {}
    options = (
        "<br />".join(f"{esc(k)}: {esc(v)}" for k, v in sorted(config.items()))
        if config
        else '<span class="dim">none</span>'
    )
    meta = [
        ("Check", group_title(run, ROOT)),
        ("LLVM revision", revision_html(data["llvm_revision"])),
    ]
    baseline = data.get("baseline")
    if baseline:
        meta.append(("Baseline revision", revision_html(baseline["llvm_revision"])))
    meta += [
        ("Options", options),
        ("Runner", esc(data["runner_arch"])),
        ("Started", f"{fmt_time(run.started)} UTC"),
        ("Finished", f"{fmt_time(run.finished)} UTC"),
        ("Duration", fmt_duration(data["duration_seconds"])),
        ("Status", status_html(run.status)),
        ("Links", " | ".join(links)),
    ]
    nav = []
    if previous:
        nav.append(
            f"previous {link(run_href(previous, ROOT), previous.label)} "
            f"({link(compare_href(previous, run, ROOT), 'compare')})"
        )
    if following:
        nav.append(
            f"next {link(run_href(following, ROOT), following.label)} "
            f"({link(compare_href(run, following, ROOT), 'compare')})"
        )
    if nav:
        meta.append(("Same PR and check", ", ".join(nav)))
    return meta


def projects_table(run: Run) -> str:
    has_baseline = run.baseline is not None
    header = (
        '<tr><th class="l">Project</th><th>Status</th><th>Time</th>'
        "<th>Warnings</th><th>TP</th><th>FP</th><th>Unclassified</th>"
    )
    if has_baseline:
        header += "<th>Baseline</th><th>New</th><th>Gone</th>"
    header += "</tr>\n"
    rows = []
    totals: Counter[str] = Counter()
    for name in sorted(run.projects):
        project = run.projects[name]
        counts = {
            "warnings": len(project.diagnostics),
            "tp": project.count("TP"),
            "fp": project.count("FP"),
            "none": project.count(None),
        }
        row = (
            f'<td class="l">{link(project_href(run, name, ROOT), name)}</td>'
            f"<td>{status_html(project.status)}</td>"
            f"<td>{fmt_duration(project.duration)}</td>"
            f"<td>{counts['warnings']}</td><td>{counts['tp']}</td>"
            f"<td>{counts['fp']}</td><td>{counts['none']}</td>"
        )
        if run.baseline is not None:
            base = run.baseline.get(name)
            if base is None:
                row += '<td class="dim">-</td>' * 3
            else:
                new, gone = diff(base.diagnostics, project.diagnostics)
                counts["baseline"] = len(base.diagnostics)
                counts["new"] = len(new)
                counts["gone"] = len(gone)
                row += (
                    f"<td>{counts['baseline']}</td>"
                    f"<td>{fmt_signed(len(new), 'up')}</td>"
                    f"<td>{fmt_signed(-len(gone), 'down')}</td>"
                )
        totals.update(counts)
        rows.append(f"<tr>{row}</tr>\n")
    total_row = (
        f'<tr><td class="l">Total</td><td></td>'
        f"<td>{fmt_duration(sum(p.duration or 0 for p in run.projects.values()))}</td>"
        f"<td>{totals['warnings']}</td><td>{totals['tp']}</td>"
        f"<td>{totals['fp']}</td><td>{totals['none']}</td>"
    )
    if has_baseline:
        total_row += (
            f"<td>{totals['baseline']}</td>"
            f"<td>{fmt_signed(totals['new'], 'up')}</td>"
            f"<td>{fmt_signed(-totals['gone'], 'down')}</td>"
        )
    total_row += "</tr>\n"
    return f"<table>\n{header}{''.join(rows)}{total_row}</table>\n"


def build_run(
    site: Site, run: Run, previous: Run | None, following: Run | None
) -> None:
    has_baseline = run.baseline is not None
    body = (
        f"<h3>Run {esc(run.label)}:</h3>\n"
        f"{kv_table(run_metadata(site, run, previous, following))}"
    )
    if run.data.get("baseline") and not has_baseline:
        body += (
            '<p class="warning">Baseline results were not recorded for this run.</p>\n'
        )
    anchor = ' id="baseline"' if has_baseline else ""
    body += f"<h4{anchor}>Projects:</h4>\n{projects_table(run)}"
    if has_baseline:
        body += (
            "<p>New: warnings that the baseline did not produce. "
            "Gone: baseline warnings that this run no longer produces.</p>\n"
        )
    if not run.projects:
        body += (
            '<p class="warning">No project results were recorded for this run.</p>\n'
        )
    site.write(f"run/{run.id}.html", f"CTIT Run {run.label}: {run.check}", body)
