"""Configuration loading."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yaml"
DATA_DIR = ROOT / "data"


def load_config(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh)
