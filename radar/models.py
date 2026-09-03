"""Data model shared by sources, filters and reporting."""
from dataclasses import asdict, dataclass, field


@dataclass
class Job:
    id: str                 # "<source>:<native id>"
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    posted: str | None = None   # ISO date (YYYY-MM-DD) when known
    remote_flag: bool = False   # came through the portal's remote filter (hint only)
    labels: list[str] = field(default_factory=list)   # portal workplace labels: remoto | hibrido | presencial
    # Filled in by the filter when the job is accepted.
    score: int = 0
    modality: str = ""          # "remoto" | "galicia"
    workplace: str = ""         # remoto | hibrido | presencial | sin especificar | sin confirmar
    signals: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)   # requisitos / ofrecen / claves

    @property
    def fingerprint(self) -> str:
        from .text import company_key, normalize
        return f"{normalize(self.title)}|{company_key(self.company)}"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["description"] = (self.description or "")[:400]
        return data
