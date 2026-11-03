#!/bin/sh
# Once a day, the first time after 08:00 that this Mac has a logged-in Claude Code session:
#   1. run a fresh search on GitHub Actions (new offers wait in the review queue),
#   2. review the queue with Claude Code (`radar review` writes data/reviews.json),
#   3. push the verdicts and run the workflow again so the page and the email get them.
# launchd calls it every hour; days already done and hours without a session exit quietly.
set -u
cd "$(dirname "$0")/.."
STAMP="$HOME/Library/Caches/empleo-radar/last-daily-run"
today=$(date +%F)
log() { echo "$(date '+%F %T') $*"; }

[ "$(cat "$STAMP" 2>/dev/null)" = "$today" ] && exit 0
[ "$(date +%H)" -lt 8 ] && exit 0
claude auth status 2>/dev/null | grep -q '"loggedIn": true' || { log "sin sesión de Claude Code; se reintenta en una hora"; exit 0; }
gh auth status >/dev/null 2>&1 || { log "gh sin sesión; se reintenta en una hora"; exit 0; }

log "búsqueda diaria"
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run radar.yml || exit 1
run_id=""
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  sleep 10
  run_id=$(gh run list --workflow radar.yml --event workflow_dispatch --limit 5 --json databaseId,createdAt \
    --jq "map(select(.createdAt >= \"$since\"))[0].databaseId // empty")
  [ -n "$run_id" ] && break
done
# A failed run still saves the queue (the persist step always runs), so it is not fatal here.
[ -n "$run_id" ] && { gh run watch "$run_id" --interval 30 --exit-status >/dev/null 2>&1 || log "la búsqueda terminó con avisos"; }

git pull --quiet --rebase --autostash origin main || exit 1
.venv/bin/python -m radar review
status=$?

git add data/reviews.json
if ! git diff --cached --quiet; then
  git commit --quiet -m "chore: update offer reviews" -- data/reviews.json || exit 1
  git pull --quiet --rebase --autostash origin main && git push --quiet || exit 1
  gh workflow run radar.yml || exit 1
  log "veredictos publicados; la web se actualiza en unos minutos"
fi
if [ $status -eq 0 ]; then
  mkdir -p "$(dirname "$STAMP")" && echo "$today" > "$STAMP"
fi
exit $status
