# Empleo Radar

Periodic job search for **Project Manager / project coordination roles** that fit a
non-technical PM profile: Spanish-language ads, either located in Galicia (any modality)
or 100% remote anywhere else. Ads that require a developer or engineering background are
discarded. New matches are emailed as a digest; nothing is emailed twice.

Sources in this version: LinkedIn (public guest API), Indeed Spain (via `python-jobspy`)
and Tecnoempleo (RSS). InfoJobs and Adzuna can be added later behind their API keys.

## How it works

```
sources ──► title gate ──► fetch description ──► exclusions ──► location ──► language ──► score
            (cheap)        (only candidates)     (dev/engineer)  (Galicia |   (Spanish)   (0-100)
                                                                 100% remote)
```

* Every rule lives in `config.yaml` as a regex over lowercased, accent-free text.
* `data/seen.json` remembers every job id already processed and every match already
  notified (title + company fingerprint), so the same offer seen on two portals is sent once.
* The email is only sent when at least one new match exists.

## Local usage

```bash
cd empleo-radar
uv venv .venv -p 3.12 && source .venv/bin/activate   # or python3 -m venv .venv
pip install -r requirements.txt

# Look without touching anything: prints matches and, with -v, every rejection reason.
python3 -m radar run --dry-run --since-hours 168 -v

# Same, but also write the HTML digest to inspect the email layout.
python3 -m radar run --dry-run --html data/preview.html

# Real run (updates data/seen.json, emails if SMTP_* and MAIL_TO are set in .env).
python3 -m radar run

# Restrict sources.
python3 -m radar run --dry-run --sources linkedin,tecnoempleo
```

Copy `.env.example` to `.env` for local email delivery. Run the tests with
`python3 -m unittest discover -s tests`.

## Scheduled runs on GitHub Actions

`.github/workflows/radar.yml` runs three times a day (07:00, 12:00 and 17:00 UTC) and
commits the updated `data/seen.json` back to the repo. Configure these repository secrets
(Settings → Secrets and variables → Actions):

| Secret      | Value                                                                 |
|-------------|-----------------------------------------------------------------------|
| `SMTP_USER` | Gmail address that sends the digest                                   |
| `SMTP_PASS` | Gmail **App Password** for that account (requires 2-Step Verification) |
| `MAIL_TO`   | Comma-separated recipients                                            |
| `SMTP_HOST` | optional, default `smtp.gmail.com`                                    |
| `SMTP_PORT` | optional, default `587`                                               |
| `MAIL_FROM` | optional, default `SMTP_USER`                                         |

Create the App Password at <https://myaccount.google.com/apppasswords>. The workflow can
also be launched by hand from the Actions tab (with a dry-run switch and a custom lookback).

If LinkedIn or Indeed start refusing requests from GitHub's IP range, the run still
completes with the other sources and lists the errors at the bottom of the digest.

## Tuning the filters

* **Missing a good offer?** Run with `--dry-run -v`, find its rejection reason
  (`title:excluded:<match>`, `text:excluded:<match>`, `degree:<match>`, `location:...`,
  `language:...`) and relax the corresponding list in `config.yaml`.
* **Too much noise?** Add patterns to `title_exclude` / `text_exclude`, or raise the
  weight of the relevant entry in `scoring.negative`.
* `queries` are the search terms sent to each portal; `lookback_hours` is the window each
  run looks back (runs overlap on purpose, `seen.json` deduplicates).
* Delete `data/seen.json` to start from scratch (the next run will re-notify everything
  inside the lookback window).

## Layout

```
config.yaml            search terms, sources, filter and scoring rules
radar/cli.py           orchestration (python -m radar run)
radar/filters.py       rule engine
radar/sources/         linkedin.py · indeed.py · tecnoempleo.py
radar/report.py        text + HTML digest
radar/notify.py        SMTP delivery
radar/state.py         data/seen.json persistence
tests/test_filters.py  rule regression tests with real-world titles
```
