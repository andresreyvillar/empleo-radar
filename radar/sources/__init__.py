from .indeed import IndeedSource
from .linkedin import LinkedInSource
from .tecnoempleo import TecnoempleoSource

SOURCES = {cls.name: cls for cls in (LinkedInSource, IndeedSource, TecnoempleoSource)}


def build_sources(cfg: dict, lookback_hours: int, only: list[str] | None = None):
    sources = []
    for name, cls in SOURCES.items():
        if only and name not in only:
            continue
        if not only and not cfg["sources"].get(name, {}).get("enabled", True):
            continue
        sources.append(cls(cfg, lookback_hours))
    return sources
