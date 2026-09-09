#!/usr/bin/env bash
# Regenerate assets/files/CV_Joshua_Sims.pdf from build/cv-print.html.
# Edit cv-print.html, run this, commit the new PDF.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

"$chrome" --headless --disable-gpu --no-pdf-header-footer \
  --run-all-compositor-stages-before-draw --virtual-time-budget=6000 \
  --print-to-pdf="$root/assets/files/CV_Joshua_Sims.pdf" \
  "file://$root/build/cv-print.html"

echo "Wrote $root/assets/files/CV_Joshua_Sims.pdf"
