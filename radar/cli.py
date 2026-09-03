"""Command line entry point: python -m radar run [options]."""
import argparse
import sys
from datetime import datetime

from dotenv import load_dotenv

from .config import DATA_DIR, load_config
from .filters import JobFilter
from .models import Job
from .notify import mail_settings, send_email
from .report import render_html, render_text, subject
from .site import build_site
from .sources import SOURCES, build_sources
from .state import State


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="radar", description="Job radar for PM roles.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="search sources, filter, notify")
    run.add_argument("--dry-run", action="store_true", help="no email and no state changes")
    run.add_argument("--no-mail", action="store_true", help="update state but do not send email")
    run.add_argument("--sources", help=f"comma-separated subset of {', '.join(SOURCES)}")
    run.add_argument("--since-hours", type=int, help="override lookback_hours from config")
    run.add_argument("--html", metavar="PATH", help="also write the HTML digest to this file")
    run.add_argument("--config", metavar="PATH", help="alternative config.yaml")
    run.add_argument("-v", "--verbose", action="store_true", help="print rejected candidates and why")
    sub.add_parser("site", help="rebuild docs/index.html from data/seen.json without searching")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    if args.command == "site":
        print(f"Página generada: {build_site(State(DATA_DIR / 'seen.json').data)}")
        return 0
    cfg = load_config(args.config)
    lookback = args.since_hours or int(cfg["lookback_hours"])
    only = [s.strip() for s in args.sources.split(",")] if args.sources else None
    job_filter = JobFilter(cfg)
    state = State(DATA_DIR / "seen.json")

    matches: list[Job] = []
    stats: dict[str, dict] = {}
    for source in build_sources(cfg, lookback, only):
        st = {"fetched": 0, "candidates": 0, "accepted": 0, "errors": []}
        print(f"→ {source.name}: buscando (últimas {lookback}h)…", flush=True)
        try:
            jobs = source.search()
        except Exception as exc:  # a broken source must not stop the others
            st["errors"].append(f"search failed: {exc}")
            jobs = []
        for job in jobs:
            st["fetched"] += 1
            if state.is_seen(job):
                continue
            if not job_filter.title_passes(job.title):
                state.mark(job, False, "title")
                continue
            st["candidates"] += 1
            try:
                source.enrich(job)
            except Exception as exc:
                st["errors"].append(f"enrich {job.id}: {exc}")
            verdict = job_filter.evaluate(job)
            state.mark(job, verdict.accepted, verdict.reason)
            if not verdict.accepted:
                if args.verbose:
                    print(f"   ✗ {job.title} — {job.company} [{job.location}] → {verdict.reason}")
                continue
            if state.duplicate_match(job):
                continue
            job.score, job.modality, job.signals = verdict.score, verdict.modality, verdict.signals
            state.add_match(job)
            matches.append(job)
            st["accepted"] += 1
        st["errors"].extend(source.errors)
        stats[source.name] = st
        print(f"   {st['fetched']} leídas · {st['candidates']} candidatas · {st['accepted']} aceptadas"
              + (f" · {len(st['errors'])} errores" if st["errors"] else ""), flush=True)
        for err in st["errors"]:
            print(f"   ! {err}")

    matches.sort(key=lambda j: j.score, reverse=True)
    now = datetime.now()
    print()
    print(render_text(matches, stats, now))

    if args.html:
        with open(args.html, "w", encoding="utf-8") as fh:
            fh.write(render_html(matches, stats, now))
        print(f"\nHTML escrito en {args.html}")

    if args.dry_run:
        print("\n(dry-run: sin email y sin cambios en data/seen.json)")
        return 0

    if matches and not args.no_mail:
        settings = mail_settings()
        if settings:
            send_email(subject(matches, now), render_text(matches, stats, now),
                       render_html(matches, stats, now), settings)
            print(f"\nEmail enviado a {', '.join(settings['recipients'])}")
        else:
            print("\nAviso: SMTP_USER / SMTP_PASS / MAIL_TO no configurados; no se envía email.")
    state.set_last_run(stats)
    state.save()
    print(f"Página generada: {build_site(state.data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
