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

## Web page

Every real run regenerates `docs/index.html`: a self-contained page (no server, no external
dependencies) listing every match found in the last 90 days with client-side filters — text
search, source, modality (100% remote / Galicia), publication window, minimum score — and a
button that opens each offer on the portal where it was published. Each card shows the key
facts detected in the ad (salary, schedule, modality, years of experience, contract) and a
collapsible "Requisitos y qué ofrecen" section extracted from the ad's own headings
(`radar/details.py`). Each offer can be marked as saved, applied or discarded; that state
lives in the visitor's browser (`localStorage`).

The page can also **run a search on demand** ("Ejecutar búsqueda ahora"): it dispatches the
GitHub Actions workflow, follows the run and reloads when the new page is published. The
saved / applied / discarded marks are **shared through the repo** (`data/feedback.json`), so
every device sees the same marks and the radar never notifies a discarded offer again, even
when it is republished or shows up on another portal. Both features need a GitHub token
entered once in the page (link "Configurar token de GitHub"); it is kept only in that
browser's `localStorage`. Create a fine-grained token at
<https://github.com/settings/personal-access-tokens/new> → Only select repositories →
this repo → Permissions: *Actions: Read and write*, *Contents: Read and write*.

It is published with GitHub Pages at <https://andresreyvillar.github.io/empleo-radar/>
(Settings → Pages → Deploy from branch `main`, folder `/docs`) and can also be opened locally. `python3 -m radar site` rebuilds the page from
`data/seen.json` without searching.

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
commits the updated `data/seen.json` and `docs/index.html` back to the repo. Configure these repository secrets
(Settings → Secrets and variables → Actions):

| Secret      | Value                                                                 |
|-------------|-----------------------------------------------------------------------|
| `SMTP_USER` | Gmail address that sends the digest                                   |
| `SMTP_PASS` | Gmail **App Password** for that account (requires 2-Step Verification) |
| `MAIL_TO`   | Comma-separated recipients                                            |
| `SMTP_HOST` | optional, default `smtp.gmail.com`                                    |
| `SMTP_PORT` | optional, default `587`                                               |
| `MAIL_FROM` | optional, default `SMTP_USER`                                         |

Create the App Password at <https://myaccount.google.com/apppasswords> **on the same Google
account as `SMTP_USER`** (2-Step Verification must be on). To check the credentials without
waiting for new offers run `python3 -m radar test-mail` locally (reads `.env`) or launch the
workflow from the Actions tab with the *test_mail* switch; the SMTP error, if any, is printed
in the run log. The workflow can also be launched by hand with a dry-run switch and a custom
lookback.

If LinkedIn or Indeed start refusing requests from GitHub's IP range, the run still
completes with the other sources and lists the errors at the bottom of the digest. If the
email cannot be sent, the state and the page are still saved and the unsent offers are kept
in `data/seen.json` (`pending_email`) to ride along with the next successful digest.

## Tuning the filters

* **Missing a good offer?** Run with `--dry-run -v`, find its rejection reason
  (`title:excluded:<match>`, `text:excluded:<match>`, `degree:<match>`, `location:...`,
  `language:...`) and relax the corresponding list in `config.yaml`.
* **Too much noise?** Add patterns to `title_exclude` / `text_exclude`, or raise the
  weight of the relevant entry in `scoring.negative`.
* **Languages:** ads demanding English above B2 (alto, fluido, C1, bilingüe) or any other
  language are rejected; intermediate, conversational or professional English is accepted.
  Catalan-language ads are rejected too.
* **Workplace:** LinkedIn's Presencial/Híbrido/Remoto label is not readable from public
  pages and its remote search filter returns on-site ads, so the ad text decides. Outside
  Galicia only text-confirmed remote offers pass; `filters.location.unconfirmed_remote: flag`
  would instead accept silent ads with a "Remoto sin confirmar" badge and a score penalty.
* `queries` are the search terms sent to each portal; `lookback_hours` is the window each
  run looks back (runs overlap on purpose, `seen.json` deduplicates).
* Delete `data/seen.json` to start from scratch (the next run will re-notify everything
  inside the lookback window).

## Layout

```
config.yaml            search terms, sources, filter and scoring rules
radar/cli.py           orchestration (python -m radar run)
radar/filters.py       rule engine
radar/details.py       requirements / benefits / key facts extraction
radar/sources/         linkedin.py · indeed.py · tecnoempleo.py
radar/report.py        text + HTML email digest
radar/site.py          docs/index.html generator (template in radar/templates/site.html)
radar/notify.py        SMTP delivery
radar/state.py         data/seen.json persistence (seen ids, matches, pending email)
radar/feedback.py      data/feedback.json (saved/applied/discarded marks written by the page)
tests/test_filters.py  rule regression tests with real-world titles
```
