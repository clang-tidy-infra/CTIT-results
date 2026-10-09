"""about.html: what the site shows and where the data comes from."""

from __future__ import annotations

from ..markup import esc, render
from ..model import CTIT_URL
from ..writer import Site


def build_about(site: Site) -> None:
    body = render(
        "about.html",
        ctit_url=esc(CTIT_URL),
        repository=esc(site.repository),
        repository_url=esc(f"https://github.com/{site.repository}"),
    )
    site.write("about.html", "CTIT Results: About", body)
