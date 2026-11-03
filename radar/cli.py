"""Command line entry point: python -m radar run [options]."""
import argparse
import sys
from datetime import datetime

from dotenv import load_dotenv

from .ai import Review, Reviewer, ReviewUnavailable, load_reviews, save_reviews, stored_review
from .config import DATA_DIR, load_config
from .details import extract_details
from .feedback import Feedback
from .filters import JobFilter
from .models import Job
from .notify import mail_settings, send_email
from .report import render_html, render_text, subject
from .site import build_site
from .sources import SOURCES, build_sources
from .state import State

REVIEWS_PATH = DATA_DIR / "reviews.json"


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
    run.add_argument("--ai-defer", action="store_true",
                     help="queue the AI review for `radar review` instead of calling Claude Code (GitHub Actions)")
    review = sub.add_parser("review", help="AI-review queued jobs with the local Claude Code session (writes data/reviews.json)")
    review.add_argument("--limit", type=int, help="review at most this many jobs")
    review.add_argument("--config", metavar="PATH", help="alternative config.yaml")
    sub.add_parser("site", help="rebuild docs/index.html from data/seen.json without searching")
    sub.add_parser("test-mail", help="send a test email with the SMTP_* / MAIL_TO settings and report the result")
    return parser


def test_mail() -> int:
    settings = mail_settings()
    if not settings:
        print("Faltan SMTP_USER, SMTP_PASS o MAIL_TO.")
        return 1
    print(f"Servidor {settings['host']}:{settings['port']} · usuario {settings['user']} · destinatarios {', '.join(settings['recipients'])}")
    try:
        when = datetime.now()
        send_email(f"Radar empleo PM · correo de prueba · {when:%d/%m/%Y %H:%M}",
                   "Si lees esto, el envío de correo del radar funciona.",
                   "<p>Si lees esto, el envío de correo del radar funciona.</p>", settings)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1
    print("Correo de prueba enviado.")
    return 0


def build_reviewer(cfg: dict, defer: bool) -> Reviewer | None:
    """None when the AI stage is off. A deferred reviewer queues every job."""
    if not cfg.get("ai", {}).get("enabled"):
        return None
    reviewer = Reviewer(cfg)
    if defer:
        reviewer.available = False
    return reviewer


def passes_review(job: Job, review: Review, state: State, verbose: bool) -> bool:
    if not review.apta:
        state.mark(job, False, f"ai:{review.motivo}"[:200])
        if verbose:
            print(f"   ✗ {job.title} — {job.company} → IA: {review.motivo}")
        return False
    review.apply(job)
    return True


def drain_queue(state: State, feedback: Feedback, reviewer: Reviewer | None, verbose: bool) -> list[Job]:
    """Jobs queued by earlier runs: apply the reviews made locally, or review them now."""
    reviews = load_reviews(REVIEWS_PATH)
    accepted = []
    for job in state.review_queue():
        if state.duplicate_match(job) or feedback.is_discarded(job):
            state.unqueue(job.id)
            continue
        if job.id in reviews:
            review = stored_review(reviews[job.id])
        elif reviewer and reviewer.available:
            try:
                review = reviewer.review(job)
            except ReviewUnavailable:
                continue
        else:
            continue
        state.unqueue(job.id)
        if passes_review(job, review, state, verbose):
            state.add_match(job)
            accepted.append(job)
    return accepted


def review_queued(cfg: dict, limit: int | None) -> int:
    reviewer = Reviewer(cfg)
    if not reviewer.available:
        print("No se encuentra Claude Code (`claude`) en el PATH o falta ai_profile.local.md.")
        return 1
    state = State(DATA_DIR / "seen.json")
    feedback = Feedback(DATA_DIR / "feedback.json")
    feedback.learn_fingerprints(state.data["matches"])
    queue = state.review_queue()
    # Reviews of jobs no longer queued were already applied by a `run`.
    reviews = {k: v for k, v in load_reviews(REVIEWS_PATH).items() if k in {j.id for j in queue}}
    todo = [j for j in queue if j.id not in reviews and not feedback.is_discarded(j)][:limit]
    print(f"→ revisión IA: {len(todo)} ofertas en cola")
    done = 0
    for job in todo:
        try:
            review = reviewer.review(job)
        except ReviewUnavailable as exc:
            print(f"   ! {job.title} — {job.company}: {exc}")
            if not reviewer.available:
                break
            continue
        reviews[job.id] = {**review.to_dict(), "reviewed_at": datetime.now().astimezone().isoformat(timespec="seconds")}
        done += 1
        print(f"   {'✓' if review.apta else '✗'} [{review.encaje}] {job.title} — {job.company} → {review.motivo}", flush=True)
    save_reviews(REVIEWS_PATH, reviews)
    print(f"{done} revisadas · {len(todo) - done} siguen pendientes")
    return 0 if reviewer.available else 1


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    cfg = load_config(getattr(args, "config", None))
    feedback = Feedback(DATA_DIR / "feedback.json")
    if args.command == "site":
        print(f"Página generada: {build_site(State(DATA_DIR / 'seen.json').data, feedback.statuses, cfg.get('site'))}")
        return 0
    if args.command == "test-mail":
        return test_mail()
    if args.command == "review":
        return review_queued(cfg, args.limit)
    lookback = args.since_hours or int(cfg["lookback_hours"])
    only = [s.strip() for s in args.sources.split(",")] if args.sources else None
    job_filter = JobFilter(cfg)
    state = State(DATA_DIR / "seen.json")
    feedback.learn_fingerprints(state.data["matches"])
    reviewer = build_reviewer(cfg, args.ai_defer)

    matches: list[Job] = drain_queue(state, feedback, reviewer, args.verbose) if reviewer else []
    if matches:
        print(f"→ revisión IA: {len(matches)} ofertas de la cola aceptadas", flush=True)
    stats: dict[str, dict] = {}
    for source in build_sources(cfg, lookback, only):
        st = {"fetched": 0, "candidates": 0, "accepted": 0, "discarded": 0, "queued": 0, "ai_rejected": 0, "errors": []}
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
            if feedback.is_discarded(job):          # Laura discarded it (or its twin) on the page
                state.mark(job, False, "discarded-by-user")
                st["discarded"] += 1
                if args.verbose:
                    print(f"   ⊘ {job.title} — {job.company} → descartada previamente en la web")
                continue
            job.score, job.modality, job.signals = verdict.score, verdict.modality, verdict.signals
            job.workplace = verdict.workplace
            job.details = extract_details(job.description)
            if job.labels:
                job.details["claves"]["etiqueta"] = ", ".join(job.labels)
            if reviewer:
                try:
                    review = reviewer.review(job)
                except ReviewUnavailable as exc:
                    state.queue_review(job)
                    st["queued"] += 1
                    if args.verbose:
                        print(f"   … {job.title} — {job.company} → pendiente de revisión IA ({exc})")
                    continue
                if not passes_review(job, review, state, args.verbose):
                    st["ai_rejected"] += 1
                    continue
            state.add_match(job)
            matches.append(job)
            st["accepted"] += 1
        st["errors"].extend(source.errors)
        stats[source.name] = st
        print(f"   {st['fetched']} leídas · {st['candidates']} candidatas · {st['accepted']} aceptadas"
              + (f" · {st['discarded']} descartadas por Laura" if st["discarded"] else "")
              + (f" · {st['ai_rejected']} rechazadas por la IA" if st["ai_rejected"] else "")
              + (f" · {st['queued']} pendientes de revisión IA" if st["queued"] else "")
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

    # Matches that earlier runs could not email (SMTP down / not configured) ride along.
    pending = state.pending_email(feedback.discarded_ids)
    digest = pending + matches
    mail = {"status": "sin ofertas nuevas", "error": "", "sent": 0, "pending": 0}
    if args.no_mail:
        mail["status"] = "desactivado (--no-mail)"
    elif digest:
        settings = mail_settings()
        if not settings:
            mail["status"] = "sin configurar"
            print("\nAviso: SMTP_USER / SMTP_PASS / MAIL_TO no configurados; el envío queda pendiente.")
        else:
            try:
                send_email(subject(digest, now), render_text(digest, stats, now),
                           render_html(digest, stats, now), settings)
                print(f"\nEmail enviado a {', '.join(settings['recipients'])} con {len(digest)} ofertas"
                      + (f" ({len(pending)} pendientes de envíos anteriores)" if pending else ""))
                mail.update(status="enviado", sent=len(digest))
                digest = []
            except Exception as exc:  # keep the state and retry next run; the page shows the error
                mail.update(status="error", error=f"{type(exc).__name__}: {exc}"[:300])
                print(f"\nAviso: no se pudo enviar el email, se reintentará en la próxima ejecución: {mail['error']}")
    mail["pending"] = len(digest) if not args.no_mail else 0
    state.set_pending_email([job.id for job in digest] if not args.no_mail else [])
    state.set_last_run(stats, mail, len(state.review_queue()))
    state.save()
    print(f"Página generada: {build_site(state.data, feedback.statuses, cfg.get('site'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
