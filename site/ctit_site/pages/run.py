"""run/<id>.html: one run's metadata and per-project summary."""

from __future__ import annotations

import math
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
from ..ranking import RANKING_PROJECTS, Entry, Ranking, module, rank
from ..timings import TimingsDay
from ..writer import Site, compare_href, group_title, project_href, run_href

ROOT = "../"
# How many checks the nearest-checks tables show above and below the check.
RANKING_CONTEXT = 3


def run_metadata(
    site: Site, run: Run, previous: Run | None, following: Run | None
) -> list[tuple[str, str]]:
    data = run.data
    links = [
        link(run.github_run_url, "GitHub run"),
        link(site.results_url(run), "run record (JSON)"),
    ]
    if data.get("artifact_url"):
        # The ctit-logs workflow artifact: the clang-tidy logs of the patched
        # and baseline runs, plus report.md and issue.md, as one zip.
        links.insert(1, link(data["artifact_url"], "clang-tidy logs (zip)"))
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


def neighbors_table(ranking: Ranking, entries: list[Entry], check: str) -> str:
    """`check` with its neighbors in `entries`, slowest first."""
    index = next(i for i, entry in enumerate(entries) if entry.check == check)
    first = max(index - RANKING_CONTEXT, 0)
    last = min(index + RANKING_CONTEXT, len(entries) - 1)
    gap = '<tr><td></td><td class="l dim">...</td><td></td></tr>\n'
    rows = [gap] if first > 0 else []
    for i in range(first, last + 1):
        entry = entries[i]
        mark = ' class="mark"' if entry.check == check else ""
        rows.append(
            f"<tr{mark}><td>{i + 1}</td>"
            f'<td class="l">{check_name_html(ranking, entry.check)}</td>'
            f"<td>{fmt_seconds(entry.seconds)}</td></tr>\n"
        )
    if last < len(entries) - 1:
        rows.append(gap)
    header = '<tr><th>Rank</th><th class="l">Check</th><th>Time (s)</th></tr>\n'
    return f"<table>\n{header}{''.join(rows)}</table>\n"


class LogScale:
    """Check times on a log scale, from the power of ten at or below the
    fastest nonzero time to the one at or above the slowest time."""

    def __init__(self, seconds: list[float]) -> None:
        positive = [s for s in seconds if s > 0] or [1.0]
        self.low = math.floor(math.log10(min(positive)))
        self.high = max(math.ceil(math.log10(max(positive))), self.low + 1)

    def x(self, seconds: float) -> str:
        """The position of a time in percent of the width; zero at the left edge."""
        if seconds <= 0:
            return "0%"
        fraction = (math.log10(seconds) - self.low) / (self.high - self.low)
        return f"{min(max(fraction, 0.0), 1.0) * 100:.2f}%"

    def axis(self) -> str:
        """An axis with a label at every power of ten."""
        parts = []
        for power in range(self.low, self.high + 1):
            value = 10.0**power
            label = f"{value * 1000:g}ms" if value < 1 else f"{value:g}s"
            x = self.x(value)
            anchor = (
                "start"
                if power == self.low
                else "end"
                if power == self.high
                else "middle"
            )
            parts.append(
                f'<line x1="{x}" x2="{x}" y1="0" y2="5" />'
                f'<text x="{x}" y="17" text-anchor="{anchor}">{label}</text>'
            )
        return f'<svg class="strip axis" aria-hidden="true">{"".join(parts)}</svg>'


def strip(scale: LogScale, entries: list[Entry], check: str, label: str) -> str:
    """Every check of `entries` as a tick at its time, `check` highlighted."""
    ticks = []
    mark = ""
    for entry in entries:
        x = scale.x(entry.seconds)
        if entry.check == check:
            mark = (
                f'<line class="this" x1="{x}" x2="{x}" y1="0" y2="100%">'
                f"<title>{esc(check)}: {fmt_seconds(entry.seconds)} s</title></line>"
            )
        else:
            ticks.append(f'<line x1="{x}" x2="{x}" y1="25%" y2="75%" />')
    return (
        f'<svg class="strip" role="img" aria-label="{esc(label)}">'
        f"{''.join(ticks)}{mark}</svg>"
    )


def and_list(items: list[str]) -> str:
    """A, B and C."""
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def check_time_block(ranking: Ranking, nightly_link: str) -> str:
    """How long the check took, and where it falls among all checks and among
    the checks of its module."""
    check = ranking.check
    groups = [
        ("All checks", ranking.entries()),
        (f"{module(check)} checks", ranking.entries(module(check))),
    ]
    scale = LogScale([entry.seconds for entry in groups[0][1]])
    body = (
        f"<p><b>{esc(check)}</b> took <b>{fmt_seconds(ranking.seconds)} s</b> on "
        f"{and_list(ranking.projects)}. Compared with the checks of the "
        f"{nightly_link}:</p>\n"
    )
    rows = []
    for title, entries in groups:
        index = next(i for i, e in enumerate(entries) if e.check == check)
        label = f"{title} ({len(entries)})"
        summary = (
            f"{label}: {index} slower and {len(entries) - index - 1} faster "
            f"than {check}"
        )
        rows.append(
            f'<tr><td class="l">{esc(label)}</td>'
            f"<td>{strip(scale, entries, check, summary)}</td></tr>\n"
        )
    body += (
        '<table class="strips">\n'
        f"{''.join(rows)}"
        f"<tr><td></td><td>{scale.axis()}</td></tr>\n"
        "</table>\n"
    )
    body += '<div class="side-by-side">\n'
    for _, entries in groups:
        body += f"<div>\n{neighbors_table(ranking, entries, check)}</div>\n"
    return body + "</div>\n"


def check_time_section(run: Run, nightly: TimingsDay | None) -> str:
    """How long the checks of the run took, and where they fall among the
    checks of the latest daily timings run."""
    checks = sorted(
        {check for p in run.projects.values() for check in p.check_profile or {}}
    )
    if nightly is None or not checks:
        return ""
    body = '<h4 id="check-time">Check time:</h4>\n'
    nightly_link = link(nightly.github_run_url, f"daily timings run of {nightly.date}")
    arch = run.data["runner_arch"]
    if arch != nightly.runner_arch:
        return body + (
            f'<p class="dim">This run ran on {esc(arch)} and the {nightly_link} on '
            f"{esc(nightly.runner_arch)}, so their check times cannot be compared.</p>\n"
        )
    projects = and_list(list(RANKING_PROJECTS))
    for check in checks:
        ranking = rank(run, nightly, check)
        if ranking is None:
            body += (
                f'<p class="dim"><b>{esc(check)}</b> has no times on any of '
                f"{projects} to compare with the {nightly_link}.</p>\n"
            )
        else:
            body += check_time_block(ranking, nightly_link)
    return body


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
