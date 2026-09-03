"""Statuses set from the web page (data/feedback.json): saved / applied / discarded.

The page writes this file through the GitHub Contents API. The radar uses the discarded
entries so that a discarded offer, or the same offer republished or found on another
portal (same title + company), is never notified again.
"""
import json
from pathlib import Path

from .models import Job
from .text import company_key, normalize

DISCARDED = "discarded"


class Feedback:
    def __init__(self, path: Path):
        self.statuses: dict[str, str] = {}
        if path.exists():
            with open(path, encoding="utf-8") as fh:
                self.statuses = json.load(fh).get("statuses", {}) or {}
        self.discarded_ids = {job_id for job_id, status in self.statuses.items() if status == DISCARDED}
        self._discarded_fps: set[str] = set()

    def learn_fingerprints(self, matches: list[dict]) -> None:
        """Remember title+company of every discarded match so republished copies are caught."""
        for m in matches:
            if m.get("id") in self.discarded_ids:
                self._discarded_fps.add(f"{normalize(m.get('title'))}|{company_key(m.get('company'))}")

    def is_discarded(self, job: Job) -> bool:
        return job.id in self.discarded_ids or job.fingerprint in self._discarded_fps
