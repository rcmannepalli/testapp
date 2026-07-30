# Investor pitch deck — SugApp

The LaunchUNC investor brief and its sources. **Confidential & proprietary** — see
[`../../LICENSE`](../../LICENSE) and [`../../IP.md`](../../IP.md). It's deliberately
**IP-safe**: the vision, dashboards, and trust model are shown; the scoring method is
only ever "a proprietary, validated behavioral taxonomy," never the rubric itself.

## Files

| File | What it is |
|---|---|
| `pitch_deck.html` | **Source of truth for content** — the scrolling web deck (self-contained HTML). |
| `build_pptx.js` | Generates the editable PowerPoint from that content (`pptxgenjs`). |
| `pitch_print.css` | Print overrides that turn the web deck into one 16:9 page per slide. |
| `build_pdf.sh` | Renders `pitch_deck.html` → slide-per-page PDF via headless Chromium. |
| `SugApp_Investor_Brief.pptx` | Built output — editable in PowerPoint / Google Slides (13 slides). |
| `SugApp_Investor_Brief.pdf` | Built output — ready-to-share PDF (13 pages, 16:9). |

## Regenerate

```bash
# PowerPoint (needs Node; pptxgenjs auto-used):
npm install pptxgenjs        # once, if not present
node build_pptx.js           # → SugApp_Investor_Brief.pptx

# PDF, two options:
#  a) simplest: open the .pptx in PowerPoint → "Save as PDF"
#  b) from the web deck, headless Chromium:
./build_pdf.sh               # → SugApp_Investor_Brief.pdf
```

The `.pptx` (native slides) and the Chromium `.pdf` (the web deck paginated) share the
same 12-slide narrative but are laid out independently — they are not pixel-identical.
For an exact match, export the PDF straight from PowerPoint (option a).

## Before presenting

- Replace **`<Your Legal Name>`** (cover + close) with your legal name.
- Fill in the **pricing / ask numbers** on the Business model and Ask slides (placeholders).
- "SugApp" is a working codename — swap for the real (trademark-cleared) name when chosen.

## Deck outline (13 slides)

Cover · 01 Problem · 02 Broken incumbent (surveys) · 03 The moment (change / AI) ·
04 Why now · 05 What it is · 06 How culture shifts (self-reflection) ·
07 Self-managing teams · 08 Why we win (trust) · 09 Market & buyer ·
10 Business model · 11 Status · 12 The ask.
