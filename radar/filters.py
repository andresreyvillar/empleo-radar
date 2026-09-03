"""Filtering and scoring rules driven by config.yaml.

Pipeline for each job: title gate -> technical exclusions -> engineering degree
-> location rule (Galicia or 100% remote) -> language -> score.
"""
import re
from dataclasses import dataclass, field

from .models import Job
from .text import normalize, spanish_ratio


def _compile(patterns: list[str] | None) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns or []]


@dataclass
class Verdict:
    accepted: bool
    reason: str = ""            # rejection reason, empty when accepted
    score: int = 0
    modality: str = ""          # "remoto" | "galicia"
    workplace: str = ""         # "remoto" | "hibrido" | "presencial" | "sin especificar"
    signals: list[str] = field(default_factory=list)


class JobFilter:
    def __init__(self, cfg: dict):
        f = cfg["filters"]
        self.title_include = _compile(f["title_include"])
        self.title_exclude = _compile(f["title_exclude"])
        self.text_exclude = _compile(f["text_exclude"])
        self.text_neutralizers = _compile(f.get("text_neutralizers"))
        self.degree_exclude = _compile(f["degree_exclude"])
        self.degree_neutralizers = _compile(f.get("degree_neutralizers"))
        loc = f["location"]
        self.pontevedra = _compile(loc["pontevedra"])
        self.galicia = _compile(loc["galicia"])
        self.strong_remote = _compile(loc["strong_remote"])
        self.weak_remote = _compile(loc["weak_remote"])
        self.onsite = _compile(loc["onsite"])
        self.hybrid = _compile(loc["hybrid"])
        self.min_spanish_ratio = float(f["language"]["min_spanish_ratio"])
        sc = f["scoring"]
        self.base_score = int(sc["base"])
        self.positive = [(re.compile(p), int(w), label) for p, w, label in sc["positive"]]
        self.negative = [(re.compile(p), int(w), label) for p, w, label in sc["negative"]]

    # -- cheap gate used before fetching descriptions -------------------------
    def title_passes(self, title: str) -> bool:
        t = normalize(title)
        if not any(p.search(t) for p in self.title_include):
            return False
        return not any(p.search(t) for p in self.title_exclude)

    # -- full evaluation ------------------------------------------------------
    def evaluate(self, job: Job) -> Verdict:
        title = normalize(job.title)
        if not any(p.search(title) for p in self.title_include):
            return Verdict(False, "title:no-match")
        hit = self._first_hit(self.title_exclude, title)
        if hit:
            return Verdict(False, f"title:excluded:{hit}")

        text = normalize(f"{job.title}\n{job.location}\n{job.description}")
        hit = self._hit_with_context(self.text_exclude, text, self.text_neutralizers, before=60, after=0)
        if hit:
            return Verdict(False, f"text:excluded:{hit}")
        hit = self._hit_with_context(self.degree_exclude, text, self.degree_neutralizers, before=90, after=90)
        if hit:
            return Verdict(False, f"degree:{hit}")

        modality, workplace = self.modality(job, title, text)
        if not modality:
            return Verdict(False, f"location:{workplace}-outside-allowed-area", workplace=workplace)

        ratio = spanish_ratio(job.description)
        if ratio is not None and ratio < self.min_spanish_ratio:
            return Verdict(False, f"language:spanish-ratio={ratio:.2f}")

        score, signals = self.score(text)
        if workplace == "sin confirmar":
            score = max(0, score - 10)
            signals.append("-Remoto solo según el portal, sin confirmar en el texto")
        if not job.description:
            signals.append("Sin descripción disponible")
        return Verdict(True, "", score, modality, workplace, signals)

    def workplace(self, job: Job, text: str) -> str:
        """Workplace type: the portal's own label when it has one, checked against the text.

        A "remoto" label is kept only if the ad text does not describe office presence;
        an on-site/hybrid label is final. Without labels the text alone decides.
        """
        from_text = self.text_workplace(text)
        if job.labels:
            if "remoto" in job.labels:
                return from_text if from_text in ("hibrido", "presencial") else "remoto"
            return "hibrido" if "hibrido" in job.labels else "presencial"
        return from_text

    def text_workplace(self, text: str) -> str:
        if any(p.search(text) for p in self.strong_remote):
            return "remoto"
        onsite = self._hit_with_context(self.onsite, text, self.text_neutralizers, before=60, after=0)
        weak = any(p.search(text) for p in self.weak_remote)
        if onsite:
            return "hibrido" if (weak or any(p.search(text) for p in self.hybrid)) else "presencial"
        return "remoto" if weak else "sin especificar"

    def region(self, job: Job, title: str, text: str) -> str:
        """'pontevedra' | 'galicia' | '' from location and title (description as tie-breaker)."""
        where = f"{normalize(job.location)} | {title}"
        if any(p.search(where) for p in self.pontevedra):
            return "pontevedra"
        if any(p.search(where) for p in self.galicia):
            return "pontevedra" if any(p.search(text) for p in self.pontevedra) else "galicia"
        return ""

    def modality(self, job: Job, title: str, text: str) -> tuple[str, str]:
        """(modality for filtering, workplace). Empty modality means rejected.

        Pontevedra: any workplace. Rest of Galicia: no on-site. Elsewhere: remote only.
        """
        region = self.region(job, title, text)
        workplace = self.workplace(job, text)
        if region == "pontevedra":
            return "galicia", workplace
        if region == "galicia":
            return ("galicia" if workplace != "presencial" else ""), workplace
        if workplace == "remoto":
            return "remoto", "remoto"
        if workplace == "sin especificar" and job.remote_flag:
            return "remoto", "sin confirmar"     # portal says remote, text is silent: flagged for review
        return "", workplace

    def score(self, text: str) -> tuple[int, list[str]]:
        total = self.base_score
        signals: list[str] = []
        for pattern, weight, label in self.positive:
            if pattern.search(text):
                total += weight
                signals.append(f"+{label}")
        for pattern, weight, label in self.negative:
            if pattern.search(text):
                total -= weight
                signals.append(f"-{label}")
        return max(0, min(100, total)), signals

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _first_hit(patterns: list[re.Pattern], text: str) -> str:
        for p in patterns:
            m = p.search(text)
            if m:
                return m.group(0)
        return ""

    @staticmethod
    def _hit_with_context(patterns, text, neutralizers, before: int, after: int) -> str:
        """First match whose sentence (bounded to before/after chars) contains no neutraliser."""
        for p in patterns:
            for m in p.finditer(text):
                start = max(0, m.start() - before)
                end = min(len(text), m.end() + after)
                boundary = max(text.rfind(". ", start, m.start()), text.rfind("\n", start, m.start()))
                if boundary != -1:
                    start = boundary + 1
                for stop in (text.find(". ", m.end(), end), text.find("\n", m.end(), end)):
                    if stop != -1:
                        end = min(end, stop)
                window = text[start:end]
                if any(n.search(window) for n in neutralizers):
                    continue
                return m.group(0)
        return ""
