"""Static web page (docs/index.html) listing every match, with client-side filters."""
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT

TEMPLATE = Path(__file__).parent / "templates" / "site.html"
SITE_DIR = ROOT / "docs"


def build_site(state_data: dict, feedback: dict | None = None, site_cfg: dict | None = None,
               out_dir: Path = SITE_DIR) -> Path:
    site_cfg = site_cfg or {}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": site_cfg.get("github_repo", ""),
        "workflow": site_cfg.get("workflow_file", "radar.yml"),
        "feedback": feedback or {},
        "last_run": state_data.get("last_run"),
        "matches": state_data.get("matches", []),
    }
    # "</" must not appear inside the inline <script> block.
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", data_json)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".nojekyll").touch()
    out = out_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
