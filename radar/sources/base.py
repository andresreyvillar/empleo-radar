"""Common interface for job sources."""
from ..models import Job

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


class Source:
    name = "base"

    def __init__(self, cfg: dict, lookback_hours: int):
        self.cfg = cfg
        self.options = cfg["sources"][self.name]
        self.queries: list[str] = cfg["queries"]
        self.scopes: dict = cfg["scopes"]
        self.lookback_hours = lookback_hours
        self.errors: list[str] = []

    def search(self) -> list[Job]:
        """Return candidate jobs (descriptions may be empty until enrich())."""
        raise NotImplementedError

    def enrich(self, job: Job) -> None:
        """Fetch the full description for a job that passed the title gate."""
