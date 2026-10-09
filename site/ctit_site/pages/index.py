"""index.html: every run, grouped by pull request and check."""

from __future__ import annotations

from ..markup import (
    Count,
    CountColumn,
    count_cell,
    esc,
    fmt_duration,
    fmt_time,
    link,
    render,
)
from ..model import Run
from ..writer import Site, compare_href, group_title, project_href, run_href

FIXED_HEADERS = (
    '<th></th><th></th><th class="l">Date</th><th class="l">Arch</th><th>Time</th>'
)


def project_cell(run: Run, project: str, previous: Run | None) -> Count:
    result = run.projects.get(project)
    if result is None:
        return count_cell(None)
    old = None
    if previous is not None and project in previous.projects:
        old = len(previous.projects[project].diagnostics)
    return count_cell(
        len(result.diagnostics), old, project_href(run, project), result.status
    )


def run_cell(run: Run) -> str:
    """Link to the run page; details that would widen the table go in the tooltip."""
    title = f"Run {run.label}, started {fmt_time(run.started)} UTC"
    if run.status != "COMPLETED":
        title += f", {run.status.lower()}"
    text = link(run_href(run), run.started.strftime("%Y-%m-%d"), title)
    if run.status != "COMPLETED":
        text = f'<span class="bad">{text}</span>'
    return text


def with_previous(runs: list[Run]) -> list[tuple[Run, Run | None]]:
    """Pair each run of a group with the run before it, newest first."""
    pairs = [(run, runs[i - 1] if i else None) for i, run in enumerate(runs)]
    return pairs[::-1]


def group_key(run: Run) -> str:
    """Text the filter box matches against."""
    if run.pr:
        return f"{run.check} pr-{run.pr} #{run.pr}".lower()
    return f"{run.check} main".lower()


def build_index(site: Site, groups: dict[str, list[Run]]) -> None:
    ordered = sorted(groups.values(), key=lambda runs: runs[-1].started, reverse=True)
    projects = sorted({p for runs in ordered for run in runs for p in run.projects})

    # All groups share one table so that their columns line up.
    cells: list[list[Count]] = [[] for _ in range(len(projects) + 1)]
    for runs in ordered:
        for run, previous in with_previous(runs):
            for column, project in zip(cells, projects):
                column.append(project_cell(run, project, previous))
            old_total = previous.total() if previous else None
            cells[-1].append(count_cell(run.total(), old_total))
    headers = [f'<th class="p">{esc(p)}</th>' for p in projects] + ["<th>Total</th>"]
    columns = [CountColumn(h, c) for h, c in zip(headers, cells)]

    header = (
        f"<tr>{FIXED_HEADERS}"
        + "".join(column.th() for column in columns)
        + "<th>TP</th><th>FP</th></tr>\n"
    )
    width = header.count("<th")
    sections = []
    row_index = 0
    for runs in ordered:
        latest = runs[-1]
        rows = []
        for run, previous in with_previous(runs):
            compare = link(compare_href(previous, run), "C") if previous else ""
            baseline = link(run_href(run) + "#baseline", "B") if run.baseline else ""
            rows.append(
                "<tr>"
                f"<td>{compare}</td><td>{baseline}</td>"
                f'<td class="l">{run_cell(run)}</td>'
                f'<td class="l">{esc(run.data["runner_arch"])}</td>'
                f"<td>{fmt_duration(run.data['duration_seconds'])}</td>"
                f"{''.join(column.td(row_index) for column in columns)}"
                f"<td>{run.total('TP')}</td><td>{run.total('FP')}</td>"
                "</tr>\n"
            )
            row_index += 1
        sections.append(
            f'<tbody class="group" id="{esc(latest.group)}" '
            f'data-key="{esc(group_key(latest))}">\n'
            f'<tr><td class="l" colspan="{width}">'
            f"<h4>{group_title(latest)}:</h4></td></tr>\n"
            f"{header}{''.join(rows)}</tbody>\n"
        )
    table = f'<div class="wide">\n<table>\n{"".join(sections)}</table>\n</div>\n'
    site.write("index.html", "CTIT Results", render("index.html", groups=table))
