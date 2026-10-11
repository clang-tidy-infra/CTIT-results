"""Project source links, recovered from the history of CTIT's projects.json."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from .model import parse_time

PROJECTS_JSON_PATHS = ("testers/projects.json", "projects.json")


class ProjectSources:
    """Maps a run start time to the project sources CTIT used at that time."""

    def __init__(self, ctit_dir: Path | None) -> None:
        self.history: list[tuple[datetime, dict[str, str]]] = []
        if ctit_dir is not None:
            self._load(ctit_dir)

    def _git(self, ctit_dir: Path, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(ctit_dir), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def _load(self, ctit_dir: Path) -> None:
        log = self._git(
            ctit_dir, "log", "--format=%H %cI", "HEAD", "--", *PROJECTS_JSON_PATHS
        )
        for line in log.splitlines():
            sha, date = line.split()
            for path in PROJECTS_JSON_PATHS:
                try:
                    text = self._git(ctit_dir, "show", f"{sha}:{path}")
                except subprocess.CalledProcessError:
                    continue
                sources = self._parse(text)
                if sources:
                    self.history.append((parse_time(date), sources))
                break
        self.history.sort(key=lambda item: item[0])

    @staticmethod
    def _parse(text: str) -> dict[str, str]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {}
        projects = data.get("projects", data) if isinstance(data, dict) else {}
        sources = {}
        for name, project in projects.items():
            if isinstance(project, dict) and "url" in project and "commit" in project:
                base = project["url"].removesuffix(".git")
                sources[name] = f"{base}/blob/{project['commit']}"
        return sources

    def at(self, when: datetime) -> dict[str, str]:
        current: dict[str, str] = {}
        for date, sources in self.history:
            if date > when:
                break
            current = sources
        return current
