"""AI review of candidate jobs against the candidate profile in config.yaml.

Runs after the regex filters: the model reads the whole ad, decides whether it fits and
scores the fit. The model is reached through a Claude Code sidecar (`claude -p`, the
logged-in session of the local machine), so no API key is involved. Where Claude Code is
not available (GitHub Actions) the job is queued and reviewed later by `radar review`.
"""
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import ROOT
from .models import Job

WORKPLACES = ["remoto", "hibrido", "presencial", "sin especificar"]

SCHEMA = {
    "type": "object",
    "properties": {
        "apta": {"type": "boolean"},
        "encaje": {"type": "integer"},
        "modalidad": {"type": "string", "enum": WORKPLACES},
        "motivo": {"type": "string"},
        "fortalezas": {"type": "array", "items": {"type": "string"}},
        "carencias": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["apta", "encaje", "modalidad", "motivo", "fortalezas", "carencias"],
    "additionalProperties": False,
}

INSTRUCTIONS = """Revisas ofertas de empleo para una candidata concreta. Lee la oferta completa y decide si merece que la candidata la vea.

Devuelve:
- apta: true solo si la oferta cumple todos los criterios obligatorios.
- encaje: 0-100, cuánto encaja la oferta con su perfil y objetivos (100 = encaje ideal).
- modalidad: la modalidad que describe el anuncio (remoto, hibrido, presencial o sin especificar). Si el anuncio no la dice, "sin especificar"; no la deduzcas del portal.
- motivo: una frase en español que explique la decisión, citando el dato decisivo del anuncio.
- fortalezas: hasta 3 puntos breves del perfil que encajan con esta oferta.
- carencias: hasta 3 puntos breves que la oferta pide y el perfil no cubre.

<perfil>
{profile}
</perfil>

<criterios_obligatorios>
{criteria}
</criterios_obligatorios>"""


class ReviewUnavailable(Exception):
    """Claude Code is missing, logged out or failing: the job must wait for a later review."""


@dataclass
class Review:
    apta: bool
    encaje: int
    modalidad: str
    motivo: str
    fortalezas: list[str] = field(default_factory=list)
    carencias: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, data: dict) -> "Review":
        """Coerce and bound the model's (or a stored) verdict: its text ends up on the public
        page, and an ad could try to steer the reviewer into writing long promotional text."""
        def text(s, limit=240):
            return str(s or "").strip()[:limit]
        workplace = str(data.get("modalidad", ""))
        return cls(apta=bool(data.get("apta")), encaje=max(0, min(100, int(data.get("encaje") or 0))),
                   modalidad=workplace if workplace in WORKPLACES else "sin especificar",
                   motivo=text(data.get("motivo"), 400),
                   fortalezas=[text(s) for s in (data.get("fortalezas") or [])[:3]],
                   carencias=[text(s) for s in (data.get("carencias") or [])[:3]])

    def to_dict(self) -> dict:
        return asdict(self)

    def apply(self, job: Job) -> None:
        job.score = max(0, min(100, self.encaje))
        job.workplace = self.modalidad
        job.ai_reason = self.motivo
        job.signals = [f"+{s}" for s in self.fortalezas] + [f"-{s}" for s in self.carencias]


class Reviewer:
    """Runs one headless Claude Code call per job: no tools, no MCP servers, no hooks, no
    saved session; only the logged-in account of this machine is reused."""

    def __init__(self, cfg: dict, run=subprocess.run):
        ai = cfg["ai"]
        self.command = shutil.which(ai.get("command", "claude"))
        self.model = ai["model"]
        self.effort = ai.get("effort", "medium")
        self.timeout = int(ai.get("timeout_seconds", 180))
        profile = _read_profile(ai)
        self.system = INSTRUCTIONS.format(profile=profile, criteria=ai["criteria"].strip())
        self.run = run
        self.available = self.command is not None and bool(profile)
        self.consecutive_failures = 0

    def review(self, job: Job) -> Review:
        if not self.available:
            raise ReviewUnavailable("Claude Code o el perfil local (ai_profile.local.md) no están disponibles")
        args = [self.command, "-p", _job_prompt(job), "--model", self.model, "--effort", self.effort,
                "--system-prompt", self.system, "--json-schema", json.dumps(SCHEMA),
                "--output-format", "json", "--tools", "", "--strict-mcp-config",
                "--no-session-persistence", "--setting-sources", ""]
        try:
            proc = self.run(args, capture_output=True, text=True, timeout=self.timeout, stdin=subprocess.DEVNULL)
            out = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            return self._fail(f"{type(exc).__name__}: {exc}")
        if proc.returncode != 0 or out.get("is_error") or not out.get("structured_output"):
            return self._fail(str(out.get("result") or proc.stderr or f"exit {proc.returncode}")[:300])
        self.consecutive_failures = 0
        return Review.parse(out["structured_output"])

    def _fail(self, reason: str):
        # Logged out, quota exhausted or offline: stop calling after a few failures in a row.
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.available = False
        raise ReviewUnavailable(reason)


def load_reviews(path: Path) -> dict[str, dict]:
    """Reviews made on the local machine, keyed by job id (data/reviews.json).

    Only `radar review` writes this file and only `radar run` consumes it, so the local
    machine and GitHub Actions never edit the same file."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["reviews"]


def save_reviews(path: Path, reviews: dict[str, dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"reviews": reviews}, fh, ensure_ascii=False, indent=1)


def stored_review(entry: dict) -> Review:
    return Review.parse(entry)


def _read_profile(ai: dict) -> str:
    """The profile lives in a gitignored file (the repo is public); missing means no review."""
    path = ROOT / ai.get("profile_file", "ai_profile.local.md")
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _job_prompt(job: Job) -> str:
    return (f"<oferta>\nTítulo: {job.title}\nEmpresa: {job.company or 'no indicada'}\n"
            f"Ubicación: {job.location or 'no indicada'}\nPortal: {job.source}\n\n"
            f"{job.description or '(sin descripción)'}\n</oferta>")
