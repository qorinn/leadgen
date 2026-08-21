#!/usr/bin/env bash
# Inditó a scraperhez. BARMELYIK konyvtarbol futtathato.
#
#   ./leadgen.sh review
#   ./leadgen.sh export --dry
#
# Miert kell: a scraper sajat venv-ben fut (Python 3.12), a kuldo pedig a
# rendszer python3-jan (3.9.6) -- konnyu osszekeverni oket. Ez a script
# megtalalja a repo gyokeret, oda lep, es a helyes interpretert hasznalja.
set -euo pipefail
GYOKER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$GYOKER"                       # a `python -m leadgen.cli` a gyokerbol mukodik
exec "$GYOKER/.venv/bin/python" -m leadgen.cli "$@"
