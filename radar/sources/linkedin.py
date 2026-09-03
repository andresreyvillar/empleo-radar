"""LinkedIn public (guest) job search — no login required."""
import time

import requests
from bs4 import BeautifulSoup

from ..models import Job
from ..text import html_to_text
from .base import USER_AGENT, Source

LIST_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
GEO_SPAIN = "105646813"
PAGE_SIZE = 10


class RateLimited(Exception):
    pass


class LinkedInSource(Source):
    name = "linkedin"

    def __init__(self, cfg, lookback_hours):
        super().__init__(cfg, lookback_hours)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es;q=0.9"})
        self.delay = float(self.options.get("delay_seconds", 1.5))
        self.max_pages = int(self.options.get("max_pages", 3))
        self.blocked = False

    def _scopes(self) -> list[tuple[dict, bool]]:
        """(query params, came through LinkedIn's remote filter). f_WT=2 only narrows the
        candidate list: the guest search pads results ignoring the filter and the public
        pages carry no workplace label, so the ad text decides and the flag is a mere hint."""
        scopes = []
        if self.scopes.get("remote_spain"):
            scopes.append(({"geoId": GEO_SPAIN, "f_WT": "2"}, True))
        if self.scopes.get("galicia"):
            scopes.append(({"location": "Galicia, España"}, False))
        return scopes

    def search(self) -> list[Job]:
        jobs: dict[str, Job] = {}
        time_filter = f"r{self.lookback_hours * 3600}"
        for query in self.queries:
            for params, remote_hint in self._scopes():
                for page in range(self.max_pages):
                    if self.blocked:
                        return list(jobs.values())
                    try:
                        html = self._get(LIST_URL, {"keywords": query, "f_TPR": time_filter,
                                                    "start": page * PAGE_SIZE, **params})
                    except RateLimited:
                        self.errors.append(f"rate limited during '{query}' page {page}")
                        self.blocked = True
                        break
                    except requests.RequestException as exc:
                        self.errors.append(f"'{query}' page {page}: {exc}")
                        break
                    cards = self._parse_cards(html)
                    for job in cards:
                        job = jobs.setdefault(job.id, job)
                        job.remote_flag = job.remote_flag or remote_hint
                    if len(cards) < PAGE_SIZE:
                        break
        return list(jobs.values())

    def enrich(self, job: Job) -> None:
        if self.blocked:
            return
        job_id = job.id.split(":", 1)[1]
        try:
            html = self._get(DETAIL_URL.format(job_id=job_id))
        except RateLimited:
            self.blocked = True
            self.errors.append(f"rate limited fetching {job_id}")
            return
        soup = BeautifulSoup(html, "html.parser")
        block = soup.select_one(".show-more-less-html__markup")
        if block:
            job.description = html_to_text(str(block))
        labels = ["Nivel", "Tipo de empleo", "Función", "Sector"]   # LinkedIn's fixed criteria order
        criteria = [c.get_text(" ", strip=True) for c in soup.select(".description__job-criteria-text")]
        extra = [f"{label}: {value}" for label, value in zip(labels, criteria) if label != "Función"]
        if extra:
            job.description += "\n\n" + "\n".join(extra)

    def _get(self, url: str, params: dict | None = None) -> str:
        for attempt in range(2):
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                if attempt == 0:
                    time.sleep(30)
                    continue
                raise RateLimited()
            resp.raise_for_status()
            time.sleep(self.delay)
            return resp.text
        raise RateLimited()

    def _parse_cards(self, html: str) -> list[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []
        for card in soup.select("[data-entity-urn]"):
            urn = card.get("data-entity-urn", "")
            job_id = urn.rsplit(":", 1)[-1]
            if not job_id.isdigit():
                continue
            title = card.select_one(".base-search-card__title")
            company = card.select_one(".base-search-card__subtitle")
            location = card.select_one(".job-search-card__location")
            posted = card.select_one("time[datetime]")
            jobs.append(Job(
                id=f"linkedin:{job_id}",
                source=self.name,
                title=title.get_text(" ", strip=True) if title else "",
                company=company.get_text(" ", strip=True) if company else "",
                location=location.get_text(" ", strip=True) if location else "",
                url=f"https://www.linkedin.com/jobs/view/{job_id}",
                posted=posted["datetime"] if posted else None,
            ))
        return jobs
