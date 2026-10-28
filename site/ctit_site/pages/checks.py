"""checks.html: one row per clang-tidy check."""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import quote

from ..markup import fmt_time, link
from ..model import LLVM_URL, Run
from ..writer import Site, run_href


def build_checks(site: Site, runs: list[Run]) -> None:
    by_check: dict[str, list[Run]] = defaultdict(list)
    for run in runs:
        by_check[run.check].append(run)
    rows = []
    for check in sorted(by_check):
        check_runs = by_check[check]
        latest = check_runs[-1]
        latest_pr = next((r.pr for r in reversed(check_runs) if r.pr), None)
        pr_link = (
            link(f"{LLVM_URL}/pull/{latest_pr}", f"#{latest_pr}")
            if latest_pr
            else '<span class="dim">-</span>'
        )
        rows.append(
            "<tr>"
            f'<td class="l">{link("index.html?q=" + quote(check), check)}</td>'
            f"<td>{len(check_runs)}</td>"
            f"<td>{link(run_href(latest), fmt_time(latest.started))}</td>"
            f"<td>{latest.total()}</td>"
            f'<td class="l">{pr_link}</td>'
            "</tr>\n"
        )
    body = (
        "<h3>Checks:</h3>\n"
        "<p>Every check CTIT has tested. Warnings is the total of the latest "
        "run. Click a check to see all of its runs on the index.</p>\n"
        "<table>\n"
        '<tr><th class="l">Check</th><th>Runs</th><th>Latest run</th>'
        '<th>Warnings</th><th class="l">Latest PR</th></tr>\n'
        f"{''.join(rows)}</table>\n"
    )
    site.write("checks.html", "CTIT Results: Checks", body)
