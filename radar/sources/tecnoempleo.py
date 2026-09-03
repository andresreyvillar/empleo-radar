"""Tecnoempleo RSS feeds (national + Galician provinces)."""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from ..models import Job
from ..text import html_to_text, normalize
from .base import USER_AGENT, Source

FIELD_RE = re.compile(r"<b>\s*(Empresa|Provincia|Población|Descripción)\s*:\s*</b>(.*?)(?=<b>\s*(?:Empresa|Provincia|Población|Descripción)\s*:|\Z)", re.S)


class TecnoempleoSource(Source):
    name = "tecnoempleo"

    def search(self) -> list[Job]:
        jobs: dict[str, Job] = {}
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours + 12)
        for url in self.options["feeds"]:
            try:
                resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
                resp.raise_for_status()
                root = ET.fromstring(resp.content)
            except (requests.RequestException, ET.ParseError) as exc:
                self.errors.append(f"{url}: {exc}")
                continue
            for item in root.iter("item"):
                job = self._to_job(item, cutoff)
                if job:
                    jobs.setdefault(job.id, job)
        return list(jobs.values())

    def _to_job(self, item, cutoff) -> Job | None:
        link = (item.findtext("link") or "").strip()
        if not link:
            return None
        posted_dt = None
        pub = item.findtext("pubDate")
        if pub:
            try:
                posted_dt = parsedate_to_datetime(pub)
            except (TypeError, ValueError):
                posted_dt = None
        if posted_dt and posted_dt < cutoff:
            return None
        fields = {k: html_to_text(v) for k, v in FIELD_RE.findall(item.findtext("description") or "")}
        provincia = fields.get("Provincia", "")
        poblacion = fields.get("Población", "")
        location = ", ".join(p for p in (poblacion, provincia) if p)
        return Job(
            id=f"tecnoempleo:{link.rstrip('/').rsplit('/', 1)[-1]}",
            source=self.name,
            title=(item.findtext("title") or "").strip(),
            company=fields.get("Empresa", ""),
            location=location,
            url=link,
            description=fields.get("Descripción", ""),
            posted=posted_dt.date().isoformat() if posted_dt else None,
            labels=_labels(provincia),
        )


def _labels(provincia: str) -> list[str]:
    """Tecnoempleo puts the modality in the province field ("100% En remoto", "hibrido", "presencial")."""
    n = normalize(provincia)
    if "remoto" in n or "teletrabajo" in n:
        return ["remoto"]
    if "hibrid" in n:
        return ["hibrido"]
    if "presencial" in n:
        return ["presencial"]
    return []
