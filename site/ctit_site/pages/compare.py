"""compare/<old>..<new>.html: warnings added and removed between two runs."""

from __future__ import annotations

from ..markup import (
    Count,
    CountColumn,
    count_cell,
    diagnostics_table,
    esc,
    fmt_time,
    link,
)
from ..model import Run, diff
from ..writer import Site, compare_href, group_title, project_href, run_href

ROOT = "../"


def build_compare(site: Site, old: Run, new: Run) -> None:
    projects = sorted(set(old.projects) | set(new.projects))
    old_cells: list[Count] = []
    new_cells: list[Count] = []
    sections = []
    for name in projects:
        before = old.projects.get(name)
        after = new.projects.get(name)
        old_count = len(before.diagnostics) if before else None
        old_cells.append(
            count_cell(old_count, href=project_href(old, name, ROOT))
            if before
            else count_cell(None)
        )
        new_cells.append(
            count_cell(len(after.diagnostics), old_count, project_href(new, name, ROOT))
            if after
            else count_cell(None)
        )
        if before and after:
            added, removed = diff(before.diagnostics, after.diagnostics)
            if added or removed:
                sections.append(
                    f"<h4>{esc(name)}:</h4>\n"
                    f"<p>Added ({len(added)}):</p>\n"
                    f"{diagnostics_table(added, new.sources.get(name))}"
                    f"<p>Removed ({len(removed)}):</p>\n"
                    f"{diagnostics_table(removed, old.sources.get(name))}"
                )
    old_cells.append(count_cell(old.total()))
    new_cells.append(count_cell(new.total(), old.total()))
    old_column = CountColumn("<th>Old</th>", old_cells)
    new_column = CountColumn("<th>New</th>", new_cells)
    rows = [
        f'<tr><td class="l">{esc(name)}</td>{old_column.td(i)}{new_column.td(i)}</tr>\n'
        for i, name in enumerate([*projects, "Total"])
    ]
    body = (
        f"Comparing run {link(run_href(old, ROOT), old.label)} "
        f"({fmt_time(old.started)}, {esc(old.data['runner_arch'])}) to run "
        f"{link(run_href(new, ROOT), new.label)} "
        f"({fmt_time(new.started)}, {esc(new.data['runner_arch'])}) "
        f"for {group_title(new, ROOT)}.\n"
        "<h4>Warnings:</h4>\n<table>\n"
        f'<tr><th class="l">Project</th>{old_column.th()}{new_column.th()}</tr>\n'
        f"{''.join(rows)}</table>\n"
    )
    if old.data["llvm_revision"] == new.data["llvm_revision"]:
        body += "<p>Both runs used the same LLVM revision and patch.</p>\n"
    body += (
        "".join(sections) if sections else "<p>No warnings were added or removed.</p>\n"
    )
    site.write(
        compare_href(old, new),
        f"CTIT Compare {old.label} to {new.label}",
        body,
    )
