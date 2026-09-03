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
    remote_flag: bool = False   # the source itself declares the job remote
    # Filled in by the filter when the job is accepted.
    score: int = 0
    modality: str = ""          # "remoto" | "galicia"
    signals: list[str] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        from .text import normalize
        return f"{normalize(self.title)}|{normalize(self.company)}"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["description"] = (self.description or "")[:400]
        return data
