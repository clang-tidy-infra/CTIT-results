"""HTML templates and the small HTML building blocks shared by all pages."""

from __future__ import annotations

import html
import posixpath
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path
from string import Template
from urllib.parse import quote

from .model import LLVM_URL, Diagnostic

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


@cache
def load_template(name: str) -> Template:
    return Template((TEMPLATES_DIR / name).read_text())


def render(name: str, **values: str) -> str:
    return load_template(name).substitute(values)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def link(href: str, text: str, title: str | None = None) -> str:
    title_attr = f' title="{esc(title)}"' if title else ""
    return f'<a href="{esc(href)}"{title_attr}>{esc(text)}</a>'


def fmt_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    total = round(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def fmt_signed(value: int, css: str) -> str:
    if value == 0:
        return '<span class="dim">0</span>'
    return f'<span class="{css}">{value:+d}</span>'


def status_html(status: str) -> str:
    if status == "COMPLETED":
        return "ok"
    return f'<span class="bad">{esc(status.lower())}</span>'


def verdict_html(verdict: str | None) -> str:
    if verdict == "FP":
        return '<span class="fp">FP</span>'
    if verdict == "TP":
        return '<span class="tp">TP</span>'
    return '<span class="dim">-</span>'


def revision_html(revision: str) -> str:
    sha, _, patch = revision.partition("+patch:")
    text = link(f"{LLVM_URL}/commit/{sha}", sha)
    if patch:
        text += f" + patch sha256:{esc(patch)}"
    return text


def kv_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f'<tr><td class="l">{k}:</td><td class="l">{v}</td></tr>\n' for k, v in rows
    )
    return f"<table>\n{body}</table>\n"


def diagnostics_table(diagnostics: list[Diagnostic], source: str | None) -> str:
    if not diagnostics:
        return '<p class="dim">None.</p>\n'
    rows = []
    for d in diagnostics:
        location = f"{d.file}:{d.line}:{d.column}"
        path = posixpath.normpath(d.file)
        if source and not path.startswith(("../", "/")):
            location = link(f"{source}/{quote(path)}#L{d.line}", location)
        else:
            location = esc(location)
        rows.append(
            f"<tr><td>{verdict_html(d.verdict)}</td>"
            f'<td class="l">{location}</td>'
            f'<td class="msg">{esc(d.message)}</td></tr>\n'
        )
    return (
        '<table>\n<tr><th>Verdict</th><th class="l">Location</th>'
        f'<th class="l">Message</th></tr>\n{"".join(rows)}</table>\n'
    )


@dataclass
class Count:
    """A warning count and its change from the previous run, as HTML."""

    number: str
    delta: str


def delta_html(new: int, old: int | None) -> str:
    """Return the change from the previous run, or nothing for the first run."""
    if old is None:
        return ""
    diff = new - old
    if diff > 0:
        return f'<span class="up">(+{diff})</span>'
    if diff < 0:
        return f'<span class="down">({diff})</span>'
    return '<span class="dim">(+0)</span>'


def count_cell(
    count: int | None,
    old: int | None = None,
    href: str | None = None,
    status: str = "COMPLETED",
) -> Count:
    if count is None:
        return Count('<span class="dim">-</span>', "")
    title = None if status == "COMPLETED" else status.lower()
    number = link(href, str(count), title) if href else str(count)
    if title:
        # A status word would widen every cell of the column, so highlight instead.
        number = f'<span class="bad" title="{esc(title)}">{number}</span>'
    return Count(number, delta_html(count, old))


class CountColumn:
    """A column of counts, rendered as two table columns.

    The numbers go in a right-aligned column directly under the header, and
    the deltas go in a left-aligned column of their own, so that both line up
    whatever their width. The delta column is left out when it would be empty.
    """

    def __init__(self, header: str, cells: list[Count]) -> None:
        self.header = header
        self.cells = cells
        self.has_delta = any(cell.delta for cell in cells)

    def th(self) -> str:
        extra = '<th class="d"></th>' if self.has_delta else ""
        return f"{self.header}{extra}"

    def td(self, row: int) -> str:
        cell = self.cells[row]
        extra = f'<td class="d">{cell.delta}</td>' if self.has_delta else ""
        return f"<td>{cell.number}</td>{extra}"
