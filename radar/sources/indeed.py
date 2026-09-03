"""Indeed Spain through the python-jobspy library (uses Indeed's internal API)."""
import logging
from urllib.parse import parse_qs, urlparse

from ..models import Job
from ..text import markdown_to_text
from .base import Source

logging.getLogger("JobSpy").setLevel(logging.CRITICAL)


class IndeedSource(Source):
    name = "indeed"

    # JobSpy's is_remote flag does not narrow Indeed Spain results, so the remote
    # scope is expressed through the query itself and confirmed later by the
    # location rule on the description text.
    REMOTE_SUFFIXES = (" teletrabajo", " remoto")

    def _searches(self) -> list[tuple[str, dict]]:
        searches = []
        for query in self.queries:
            if self.scopes.get("remote_spain"):
                searches += [(query + suffix, {}) for suffix in self.REMOTE_SUFFIXES]
            if self.scopes.get("galicia"):
                searches.append((query, {"location": "Galicia"}))
        return searches

    def search(self) -> list[Job]:
        from jobspy import scrape_jobs  # heavy import (pandas), keep it lazy

        jobs: dict[str, Job] = {}
        wanted = int(self.options.get("results_wanted", 40))
        for query, extra in self._searches():
            try:
                df = scrape_jobs(
                    site_name=["indeed"], search_term=query, country_indeed="Spain",
                    hours_old=self.lookback_hours, results_wanted=wanted,
                    description_format="markdown", verbose=0, **extra,
                )
            except Exception as exc:  # jobspy raises assorted errors when blocked
                self.errors.append(f"'{query}' {extra}: {exc}")
                continue
            for row in df.to_dict("records"):
                job = self._to_job(row)
                if job:
                    jobs.setdefault(job.id, job)
        return list(jobs.values())

    def _to_job(self, row: dict) -> Job | None:
        url = _s(row.get("job_url"))
        job_key = parse_qs(urlparse(url).query).get("jk", [""])[0] or _s(row.get("id"))
        if not job_key:
            return None
        posted = row.get("date_posted")
        return Job(
            id=f"indeed:{job_key}",
            source=self.name,
            title=_s(row.get("title")),
            company=_s(row.get("company")),
            location=_s(row.get("location")),
            url=url,
            description=markdown_to_text(_s(row.get("description"))),
            posted=str(posted)[:10] if posted is not None and str(posted) not in ("NaT", "nan", "None") else None,
            remote_flag=row.get("is_remote") is True,
        )


def _s(value) -> str:
    return value if isinstance(value, str) else ""
