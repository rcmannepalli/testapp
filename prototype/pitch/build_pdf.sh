#!/usr/bin/env bash
# Render pitch_deck.html to a slide-per-page 16:9 PDF using headless Chromium.
# (LibreOffice's pptx->pdf is the alternative, but on some sandboxes it's broken;
#  in PowerPoint, "Save as PDF" from the .pptx is the simplest route of all.)
set -euo pipefail
cd "$(dirname "$0")"

OUT="${1:-SugApp_Investor_Brief.pdf}"
PRINT_HTML="$(mktemp --suffix=.html)"
cat pitch_deck.html > "$PRINT_HTML"
printf '\n<style>\n' >> "$PRINT_HTML"; cat pitch_print.css >> "$PRINT_HTML"; printf '\n</style>\n' >> "$PRINT_HTML"

# Find a Chromium/Chrome binary (Playwright's, or a system install).
CHROME=""
for c in \
  /opt/pw-browsers/chromium-*/chrome-linux/chrome \
  "$(command -v chromium 2>/dev/null || true)" \
  "$(command -v google-chrome 2>/dev/null || true)" \
  "$(command -v chromium-browser 2>/dev/null || true)"; do
  [ -x "$c" ] && { CHROME="$c"; break; }
done
[ -n "$CHROME" ] || { echo "No Chromium/Chrome found."; exit 1; }

"$CHROME" --headless --no-sandbox --disable-gpu --no-pdf-header-footer \
  --run-all-compositor-stages-before-draw --virtual-time-budget=8000 \
  --print-to-pdf="$PWD/$OUT" "file://$PRINT_HTML" 2>/dev/null
rm -f "$PRINT_HTML"
echo "wrote $OUT"
