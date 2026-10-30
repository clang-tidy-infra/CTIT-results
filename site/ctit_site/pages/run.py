"""run/<id>.html: one run's metadata and per-project summary."""

from __future__ import annotations

from collections import Counter
from urllib.parse import quote

from ..markup import (
    esc,
    fmt_duration,
    fmt_seconds,
    fmt_signed,
    fmt_time,
    kv_table,
    link,
    revision_html,
    status_html,
)
from ..model import Run, diff
from ..ranking import Entry, Ranking, module, rank
from ..timings import TimingsDay
from ..writer import Site, compare_href, group_title, project_href, run_href

ROOT = "../"
# How many checks a ranking shows above and below each check of the run.
RANKING_CONTEXT = 3


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


def check_name_html(ranking: Ranking, check: str) -> str:
    if check in ranking.nightly:
        return link(f"{ROOT}timings.html?checks={quote(check)}", check)
    return esc(check)


def ranking_table(ranking: Ranking, entries: list[Entry]) -> str:
    """The checks of the run with their neighbors in `entries`."""
    shown: set[int] = set()
    for i, entry in enumerate(entries):
        if entry.new:
            shown.update(range(i - RANKING_CONTEXT, i + RANKING_CONTEXT + 1))
    gap = '<tr><td></td><td class="l dim">...</td><td></td></tr>\n'
    rows = []
    last = -1
    for i, entry in enumerate(entries):
        if i not in shown:
            continue
        if i > last + 1:
            rows.append(gap)
        last = i
        mark = ' class="mark"' if entry.new else ""
        rows.append(
            f"<tr{mark}><td>{i + 1}</td>"
            f'<td class="l">{check_name_html(ranking, entry.check)}</td>'
            f"<td>{fmt_seconds(entry.seconds)}</td></tr>\n"
        )
    if last < len(entries) - 1:
        rows.append(gap)
    header = '<tr><th>#</th><th class="l">Check</th><th>Time (s)</th></tr>\n'
    return f"<table>\n{header}{''.join(rows)}</table>\n"


def position(entries: list[Entry], check: str) -> str:
    index = next(i for i, entry in enumerate(entries) if entry.check == check)
    return f"{index + 1} of {len(entries)}"


def check_time_section(run: Run, nightly: TimingsDay | None) -> str:
    """Where the checks of the run would rank by check time among the checks
    of the latest daily timings run."""
    if nightly is None or not any(p.check_profile for p in run.projects.values()):
        return ""
    body = '<h4 id="check-time">Check time:</h4>\n'
    nightly_link = link(nightly.github_run_url, f"daily timings run of {nightly.date}")
    arch = run.data["runner_arch"]
    if arch != nightly.runner_arch:
        return body + (
            f'<p class="dim">This run ran on {esc(arch)} and the {nightly_link} on '
            f"{esc(nightly.runner_arch)}, so their check times cannot be compared.</p>\n"
        )
    ranking = rank(run, nightly)
    if ranking is None:
        return body + (
            f'<p class="dim">The {nightly_link} has no check times for the '
            "projects of this run.</p>\n"
        )
    everything = ranking.entries()
    modules = sorted({module(check) for check in ranking.run})
    by_module = {name: ranking.entries(name) for name in modules}
    rows = []
    for check in sorted(ranking.run):
        before = ranking.nightly.get(check)
        rows.append(
            f'<tr><td class="l">{check_name_html(ranking, check)}</td>'
            f"<td>{fmt_seconds(ranking.run[check])}</td>"
            "<td>"
            + ('<span class="dim">-</span>' if before is None else fmt_seconds(before))
            + "</td>"
            f"<td>{position(by_module[module(check)], check)}</td>"
            f"<td>{position(everything, check)}</td></tr>\n"
        )
    body += (
        "<p>How long the checks of this run took, from clang-tidy's check "
        f"profile, and where they would rank among all checks of the {nightly_link}, "
        "slowest first. Times are summed over the "
        f"{len(ranking.projects)} projects that both runs have times for. "
        "Daily run is the check's own time in that run, or a dash if that run "
        "did not have the check. The daily run enables every check at once, so "
        "the comparison is approximate. The tables below show each check of "
        "this run in bold, next to its neighbors in the ranking.</p>\n"
        '<table>\n<tr><th class="l">Check</th><th>Time (s)</th><th>Daily run (s)</th>'
        "<th>In module</th><th>Overall</th></tr>\n"
        f"{''.join(rows)}</table>\n"
    )
    lists = [(f"{name} checks", entries) for name, entries in by_module.items()]
    lists.append(("All checks", everything))
    body += '<div class="side-by-side">\n'
    for title, entries in lists:
        body += (
            f"<div>\n<p>{esc(title)}:</p>\n{ranking_table(ranking, entries)}</div>\n"
        )
    return body + "</div>\n"


def build_run(
    site: Site,
    run: Run,
    previous: Run | None,
    following: Run | None,
    nightly: TimingsDay | None,
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
            "<p>Baseline is the number of warnings without the patch. New "
            "warnings appear only with the patch, and gone warnings only "
            "without it.</p>\n"
        )
    if not run.projects:
        body += (
            '<p class="warning">No project results were recorded for this run.</p>\n'
        )
    body += check_time_section(run, nightly)
    site.write(f"run/{run.id}.html", f"CTIT Run {run.label}: {run.check}", body)
