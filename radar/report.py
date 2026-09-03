"""Digest rendering (plain text + HTML) for the notification email."""
import html
from datetime import datetime

from .models import Job

MODALITY_LABEL = {"remoto": "100% remoto", "galicia": "Galicia"}


def subject(matches: list[Job], when: datetime) -> str:
    n = len(matches)
    plural = "oferta nueva" if n == 1 else "ofertas nuevas"
    return f"Radar empleo PM · {n} {plural} · {when:%d/%m/%Y %H:%M}"


def render_text(matches: list[Job], stats: dict, when: datetime) -> str:
    lines = [f"Ofertas nuevas que pasan los filtros ({when:%d/%m/%Y %H:%M})", ""]
    for job in matches:
        lines.append(f"[{job.score}] {job.title} — {job.company or 'empresa no indicada'}")
        lines.append(f"    {MODALITY_LABEL.get(job.modality, job.modality)} · {job.location} · {job.source} · {job.posted or 'fecha n/d'}")
        if job.signals:
            lines.append(f"    {', '.join(job.signals)}")
        lines.append(f"    {job.url}")
        lines.append("")
    lines.append(_stats_text(stats))
    return "\n".join(lines)


def render_html(matches: list[Job], stats: dict, when: datetime) -> str:
    cards = "\n".join(_card(job) for job in matches)
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Radar empleo PM</title></head>
<body style="margin:0;padding:24px;background:#f4f5f7;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f2933">
<div style="max-width:680px;margin:0 auto">
<h1 style="font-size:20px;margin:0 0 4px">Radar empleo PM</h1>
<p style="margin:0 0 20px;color:#52606d">{len(matches)} ofertas nuevas · {when:%d/%m/%Y %H:%M}. Ordenadas por afinidad con el perfil.</p>
{cards}
<p style="font-size:12px;color:#7b8794;margin-top:24px">{html.escape(_stats_text(stats))}</p>
</div></body></html>"""


def _card(job: Job) -> str:
    modality = MODALITY_LABEL.get(job.modality, job.modality)
    color = "#0f766e" if job.modality == "remoto" else "#1d4ed8"
    signals = " · ".join(html.escape(s) for s in job.signals) or "Sin señales adicionales"
    snippet = html.escape((job.description or "")[:260]).strip()
    return f"""<div style="background:#fff;border:1px solid #e4e7eb;border-radius:8px;padding:16px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;gap:12px">
    <a href="{html.escape(job.url)}" style="font-size:16px;font-weight:600;color:#111827;text-decoration:none">{html.escape(job.title)}</a>
    <span style="font-weight:700;color:#111827;white-space:nowrap">{job.score}/100</span>
  </div>
  <div style="margin:6px 0;color:#3e4c59">{html.escape(job.company or 'Empresa no indicada')} · {html.escape(job.location or 'ubicación n/d')}</div>
  <div style="margin:6px 0">
    <span style="background:{color};color:#fff;border-radius:4px;padding:2px 8px;font-size:12px">{modality}</span>
    <span style="background:#e4e7eb;border-radius:4px;padding:2px 8px;font-size:12px;margin-left:4px">{html.escape(job.source)}</span>
    <span style="color:#7b8794;font-size:12px;margin-left:6px">{html.escape(job.posted or '')}</span>
  </div>
  <div style="font-size:12px;color:#52606d;margin:6px 0">{signals}</div>
  <p style="font-size:13px;color:#3e4c59;margin:8px 0 0">{snippet}…</p>
</div>"""


def _stats_text(stats: dict) -> str:
    parts = []
    for name, st in stats.items():
        piece = f"{name}: {st['fetched']} leídas, {st['candidates']} candidatas, {st['accepted']} aceptadas"
        if st["errors"]:
            piece += f", {len(st['errors'])} errores"
        parts.append(piece)
    return "Fuentes → " + " | ".join(parts)
