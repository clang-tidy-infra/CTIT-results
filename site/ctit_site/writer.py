"""Writing pages into the output directory, and the URLs between pages."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from .markup import esc, link, render
from .model import LLVM_URL, Run, slug


class Site:
    def __init__(self, out: Path, repository: str, revision: str | None) -> None:
        self.out = out
        self.repository = repository
        self.revision = revision

    def write(self, rel: str, title: str, body: str) -> None:
        footer = ""
        if self.revision:
            commit_url = f"https://github.com/{self.repository}/commit/{self.revision}"
            footer = (
                f'<hr />\n<p class="dim">Generated from '
                f"{link(commit_url, self.revision[:10])}.</p>\n"
            )
        page = render(
            "page.html",
            title=esc(title),
            root="../" * rel.count("/"),
            body=body,
            footer=footer,
        )
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page)

    def results_url(self, run: Run) -> str:
        return f"https://github.com/{self.repository}/blob/main/{run.path}"


def run_href(run: Run, root: str = "") -> str:
    return f"{root}run/{run.id}.html"


def project_href(run: Run, project: str, root: str = "") -> str:
    return f"{root}run/{run.id}/{slug(project)}.html"


def compare_href(old: Run, new: Run, root: str = "") -> str:
    return f"{root}compare/{old.id}..{new.id}.html"


def group_title(run: Run, root: str = "") -> str:
    if run.pr:
        pr = link(f"{LLVM_URL}/pull/{run.pr}", f"PR #{run.pr}")
    else:
        pr = "main"
    return f"{pr}: {link(f'{root}index.html?q={quote(run.check)}', run.check)}"
