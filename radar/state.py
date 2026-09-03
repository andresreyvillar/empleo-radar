"""Persistent memory of jobs already processed (data/seen.json)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Job

RETENTION_DAYS = 90


class State:
    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            with open(path, encoding="utf-8") as fh:
                self.data = json.load(fh)
        else:
            self.data = {"seen": {}, "matches": []}
        # Recompute so that improvements to the fingerprint apply to stored matches too.
        self._match_fps = {_fingerprint(m) for m in self.data["matches"]}

    def is_seen(self, job: Job) -> bool:
        return job.id in self.data["seen"]

    def duplicate_match(self, job: Job) -> bool:
        """Same title+company already notified from another source or run."""
        return job.fingerprint in self._match_fps

    def mark(self, job: Job, accepted: bool, reason: str) -> None:
        self.data["seen"][job.id] = {
            "first_seen": _now(),
            "title": job.title,
            "accepted": accepted,
            "reason": reason,
        }

    def add_match(self, job: Job) -> None:
        entry = job.to_dict()
        entry["fingerprint"] = job.fingerprint
        entry["notified_at"] = _now()
        self.data["matches"].append(entry)
        self._match_fps.add(job.fingerprint)

    def set_last_run(self, stats: dict) -> None:
        self.data["last_run"] = {"at": _now(), "stats": stats}

    def prune(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
        self.data["seen"] = {k: v for k, v in self.data["seen"].items() if v["first_seen"] >= cutoff}
        self.data["matches"] = [m for m in self.data["matches"] if m["notified_at"] >= cutoff]

    def save(self) -> None:
        self.prune()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=1)


def _fingerprint(match: dict) -> str:
    from .text import company_key, normalize
    return f"{normalize(match.get('title'))}|{company_key(match.get('company'))}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
