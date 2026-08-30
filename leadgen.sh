#!/usr/bin/env bash
# Inditó a scraperhez. BARMELYIK konyvtarbol futtathato.
#
#   ./leadgen.sh review
#   ./leadgen.sh export --dry
#   ./leadgen.sh ui
#
# Miert kell: a scraper sajat venv-ben fut (Python 3.12), a kuldo pedig a
# rendszer python3-jan (3.9.6) -- konnyu osszekeverni oket. Ez a script
# megtalalja a repo gyokeret, oda lep, es a helyes interpretert hasznalja.
set -euo pipefail
GYOKER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$GYOKER"                       # a `python -m leadgen.cli` a gyokerbol mukodik

if [ "${1:-}" = "ui" ]; then
    # A webes felulet: FastAPI (8000) + Next.js (3000), csak 127.0.0.1-en
    # (WEBUI-TERV.md Invariansok #5). Ctrl+C mindkettot leallitja.
    PIDS=()
    cleanup() {
        for pid in "${PIDS[@]:-}"; do
            kill "$pid" 2>/dev/null || true
        done
    }
    trap cleanup EXIT INT TERM

    "$GYOKER/.venv/bin/python" -m uvicorn webui.api.main:app \
        --host 127.0.0.1 --port 8000 &
    PIDS+=($!)

    (cd "$GYOKER/webui/app" && npm run dev -- --hostname 127.0.0.1 --port 3000) &
    PIDS+=($!)

    sleep 2
    if command -v open >/dev/null 2>&1; then
        open "http://127.0.0.1:3000"
    fi
    wait
fi

exec "$GYOKER/.venv/bin/python" -m leadgen.cli "$@"
