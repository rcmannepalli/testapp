const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
p.author = "SugApp";
p.title = "SugApp — Investor Brief";

// ---- palette (no # ; never 8-digit) ----
const INK = "0F2A2E", INKSOFT = "12312F", PAPER = "FFFFFF";
const JADE = "1C8D69", AMBER = "BF842A", MUTED = "5A716C";
const LINE = "D2DED9", CARD = "F4F8F6", GOOD = "2A9D6C", CRIT = "B5503F";
const ICE = "CDE7DD", PAPERLT = "EAF0EE";
const SERIF = "Cambria", SANS = "Calibri";

const shadow = () => ({ type: "outer", color: "10312B", blur: 9, offset: 3, angle: 90, opacity: 0.16 });
const W = 13.33, MX = 0.7, CW = W - MX * 2;

function eyebrow(s, txt, dark) {
  s.addText(txt.toUpperCase(), {
    x: MX, y: 0.55, w: CW, h: 0.3, fontFace: SANS, bold: true, fontSize: 11.5,
    color: dark ? ICE : JADE, charSpacing: 3, align: "left",
  });
}
function title(s, txt, dark, y = 0.92, size = 33) {
  s.addText(txt, {
    x: MX, y, w: CW, h: 1.0, fontFace: SERIF, bold: true, fontSize: size,
    color: dark ? PAPER : INKSOFT, align: "left", lineSpacingMultiple: 0.98,
  });
}
function card(s, x, y, w, h, fill = PAPER) {
  s.addShape(p.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.11, fill: { color: fill },
    line: { color: LINE, width: 1 }, shadow: shadow(),
  });
}
function bg(s, color) { s.background = { color }; }

// ===================== 1 · COVER =====================
let s = p.addSlide(); bg(s, INK);
s.addText("Workplace intelligence   ·   Change & AI transformation   ·   B2B SaaS", {
  x: MX, y: 0.7, w: 8.2, h: 0.3, fontFace: SANS, fontSize: 12.5, color: ICE, charSpacing: 1,
});
s.addText("The number no one measures:\nare people actually heard?", {
  x: MX, y: 1.55, w: 7.7, h: 2.4, fontFace: SERIF, bold: true, fontSize: 40,
  color: PAPER, lineSpacingMultiple: 1.0,
});
s.addText([
  { text: "SugApp turns everyday work conversations into a ", options: { color: "C9DBD3" } },
  { text: "Respect Index", options: { color: JADE, bold: true } },
  { text: " — and gives each person private coaching — without surveillance. When everything else is changing, it’s the signal that tells you whether your teams are holding together.", options: { color: "C9DBD3" } },
], { x: MX, y: 3.95, w: 7.4, h: 1.7, fontFace: SANS, fontSize: 16, lineSpacingMultiple: 1.15 });
s.addText("●  Working prototype built", {
  x: MX, y: 5.75, w: 4.5, h: 0.4, fontFace: SANS, bold: true, fontSize: 13, color: JADE,
});
// gauge (doughnut) right
s.addChart(p.ChartType.doughnut, [{ name: "idx", labels: ["Respect", "rest"], values: [78, 22] }], {
  x: 9.0, y: 1.7, w: 3.7, h: 3.7, holeSize: 74, showLegend: false, showTitle: false,
  showValue: false, chartColors: [JADE, "1E4A44"], dataBorder: { pt: 0, color: INK },
});
s.addText([
  { text: "78", options: { fontSize: 54, bold: true, color: PAPER, fontFace: SERIF } },
], { x: 9.0, y: 3.05, w: 3.7, h: 0.9, align: "center" });
s.addText("RESPECT INDEX", { x: 9.0, y: 3.92, w: 3.7, h: 0.3, align: "center", fontFace: SANS, fontSize: 11, color: ICE, charSpacing: 2 });
s.addText("A single, trending, team-level score — the highest-respect number, not the highest-sentiment one.", {
  x: 8.85, y: 5.55, w: 4.0, h: 0.9, align: "center", fontFace: SANS, italic: true, fontSize: 11.5, color: "9DB4AE",
});
s.addText("SugApp (working name)  ·  Confidential & Proprietary  ·  Prepared for LaunchUNC", {
  x: MX, y: 6.95, w: CW, h: 0.3, fontFace: SANS, fontSize: 10.5, color: "7E958F",
});

// ===================== 2 · PROBLEM =====================
s = p.addSlide(); bg(s, PAPER);
eyebrow(s, "01 · The problem");
title(s, "Every company measures sentiment.\nNone measure respect.");
s.addText("Engagement surveys ask how people feel. They miss what actually drives attrition and silence: whether people are listened to and treated with dignity. “Toxic but polite” sails straight through a sentiment score.", {
  x: MX, y: 2.05, w: CW, h: 0.9, fontFace: SANS, fontSize: 15, color: INKSOFT, lineSpacingMultiple: 1.1,
});
// two cards + vs
const pcw = 5.35, pcy = 3.2, pch = 3.0;
card(s, MX, pcy, pcw, pch, CARD);
s.addText("What sentiment sees", { x: MX + 0.35, y: pcy + 0.3, w: pcw - 0.7, h: 0.4, fontFace: SANS, bold: true, fontSize: 16, color: CRIT });
s.addText("“Thanks for the input! We’ll take it from here.”", { x: MX + 0.35, y: pcy + 0.95, w: pcw - 0.7, h: 0.9, fontFace: SERIF, italic: true, fontSize: 17, color: INKSOFT, lineSpacingMultiple: 1.05 });
s.addText([{ text: "Reads as positive", options: { bold: true } }, { text: ". Cheerful words, high score.", options: {} }], { x: MX + 0.35, y: pcy + 2.05, w: pcw - 0.7, h: 0.7, fontFace: SANS, fontSize: 14, color: MUTED });
s.addText("vs.", { x: MX + pcw, y: pcy, w: W - 2 * MX - 2 * pcw, h: pch, align: "center", valign: "middle", fontFace: SERIF, italic: true, fontSize: 18, color: MUTED });
const px2 = W - MX - pcw;
card(s, px2, pcy, pcw, pch, PAPER);
s.addText("What actually happened", { x: px2 + 0.35, y: pcy + 0.3, w: pcw - 0.7, h: 0.4, fontFace: SANS, bold: true, fontSize: 16, color: JADE });
s.addText("A person was dismissed and stopped contributing.", { x: px2 + 0.35, y: pcy + 0.95, w: pcw - 0.7, h: 0.9, fontFace: SERIF, italic: true, fontSize: 17, color: INKSOFT, lineSpacingMultiple: 1.05 });
s.addText([{ text: "A ", options: {} }, { text: "respect", options: { bold: true } }, { text: " problem — invisible to the tools companies buy today.", options: {} }], { x: px2 + 0.35, y: pcy + 2.05, w: pcw - 0.7, h: 0.7, fontFace: SANS, fontSize: 14, color: MUTED });

// ===================== 3 · BROKEN INCUMBENT =====================
s = p.addSlide(); bg(s, PAPER);
eyebrow(s, "02 · The broken incumbent");
title(s, "Companies spend a fortune on surveys\nno one answers honestly.");
s.addText("Surveys are expensive, annual, and — worst of all — people don’t tell the truth on them for fear of being identified and facing retaliation. Leadership pays a lot to learn very little.", {
  x: MX, y: 2.05, w: CW, h: 0.8, fontFace: SANS, fontSize: 15, color: INKSOFT, lineSpacingMultiple: 1.1,
});
const bcy = 3.1, bch = 3.2, bcw = 5.85;
card(s, MX, bcy, bcw, bch, CARD);
s.addText("The survey trap", { x: MX + 0.35, y: bcy + 0.28, w: bcw - 0.7, h: 0.4, fontFace: SANS, bold: true, fontSize: 17, color: CRIT });
s.addText([
  { text: "Costly and annual — stale by the time results land.", options: { bullet: { indent: 15 }, breakLine: true, paraSpaceAfter: 8 } },
  { text: "Fear of retaliation kills candor — answers are cover-your-back, not truth.", options: { bullet: { indent: 15 }, breakLine: true, paraSpaceAfter: 8 } },
  { text: "Self-reported and gameable — a mirror that shows leaders nothing real.", options: { bullet: { indent: 15 } } },
], { x: MX + 0.35, y: bcy + 0.85, w: bcw - 0.7, h: 2.1, fontFace: SANS, fontSize: 14, color: INKSOFT, lineSpacingMultiple: 1.05 });
const bx2 = W - MX - bcw;
card(s, bx2, bcy, bcw, bch, PAPER);
s.addText("What SugApp gives leadership", { x: bx2 + 0.35, y: bcy + 0.28, w: bcw - 0.7, h: 0.4, fontFace: SANS, bold: true, fontSize: 17, color: JADE });
s.addText([
  { text: "Continuous — from real behavior, not a once-a-year form.", options: { bullet: { indent: 15 }, breakLine: true, paraSpaceAfter: 8 } },
  { text: "Aggregated and k-anonymized — no one is exposed, so nothing is hidden out of fear.", options: { bullet: { indent: 15 }, breakLine: true, paraSpaceAfter: 8 } },
  { text: "A clear org- and team-wide picture of how each team is growing through self-reflection.", options: { bullet: { indent: 15 } } },
], { x: bx2 + 0.35, y: bcy + 0.85, w: bcw - 0.7, h: 2.1, fontFace: SANS, fontSize: 14, color: INKSOFT, lineSpacingMultiple: 1.05 });

// ===================== helper: 3-card row =====================
function threeCards(slideEyebrow, slideTitle, subtitle, items) {
  const sl = p.addSlide(); bg(sl, PAPER);
  eyebrow(sl, slideEyebrow);
  title(sl, slideTitle);
  if (subtitle) sl.addText(subtitle, { x: MX, y: 2.0, w: CW, h: 0.6, fontFace: SANS, fontSize: 15, color: INKSOFT, lineSpacingMultiple: 1.1 });
  const n = items.length, gap = 0.4, cw = (CW - gap * (n - 1)) / n, cy = subtitle ? 2.85 : 2.5, ch = 3.4;
  items.forEach((it, i) => {
    const x = MX + i * (cw + gap);
    card(sl, x, cy, cw, ch, CARD);
    sl.addShape(p.ShapeType.ellipse, { x: x + 0.35, y: cy + 0.35, w: 0.5, h: 0.5, fill: { color: JADE } });
    sl.addText(String(i + 1), { x: x + 0.35, y: cy + 0.35, w: 0.5, h: 0.5, align: "center", valign: "middle", fontFace: SERIF, bold: true, fontSize: 18, color: PAPER });
    sl.addText(it.h, { x: x + 0.35, y: cy + 1.05, w: cw - 0.7, h: 0.75, fontFace: SANS, bold: true, fontSize: 16.5, color: INKSOFT, lineSpacingMultiple: 0.98 });
    sl.addText(it.b, { x: x + 0.35, y: cy + 1.85, w: cw - 0.7, h: 1.4, fontFace: SANS, fontSize: 13.5, color: MUTED, lineSpacingMultiple: 1.08 });
  });
  return sl;
}

// ===================== 4 · THE MOMENT =====================
threeCards("03 · The moment", "Built for the most uncertain workplace in a generation.",
  "AI transformation is reorganizing every team at once. How people treat each other decides whether change lands — or your best people quietly leave.", [
  { h: "Change breaks trust first", b: "Reorgs and AI rollouts erode psychological safety long before it shows up in output or a quarterly survey." },
  { h: "Sentiment is noise now", b: "In upheaval, mood swings with the daily news. Respect & listening is the durable signal that a team is intact." },
  { h: "The cost is silent", b: "Disengagement and regretted attrition surface months late. Respect is the early-warning light that comes on first." },
]);

// ===================== 5 · WHY NOW =====================
threeCards("04 · Why now", "The signal was always there. The reader just arrived.", null, [
  { h: "Work is text now", b: "Slack, Teams, and chat hold the real record of how colleagues treat each other — dense, continuous, and unmined." },
  { h: "LLMs read nuance", b: "Judging acknowledgement, dismissal, or credit-sharing needs context, not keywords. That capability is new." },
  { h: "Trust is the gate", b: "The winner isn’t whoever reads the most — it’s whoever people trust to. That’s a design choice we make on line one." },
]);

// ===================== 6 · WHAT IT IS =====================
s = p.addSlide(); bg(s, PAPER);
eyebrow(s, "05 · What it is");
title(s, "A respect & listening layer for the\nmodern workplace.");
s.addText("Connect a channel. SugApp reads the conversation with consent, and produces two things:", {
  x: MX, y: 2.05, w: 6.6, h: 0.7, fontFace: SANS, fontSize: 15, color: INKSOFT, lineSpacingMultiple: 1.1,
});
s.addText([
  { text: "A private mirror for each person", options: { bold: true, color: INKSOFT, bullet: { indent: 15 }, breakLine: true } },
  { text: "their own words, what’s landing well, and one concrete thing to try next.", options: { color: MUTED, bullet: false, breakLine: true, paraSpaceAfter: 12, indentLevel: 1 } },
  { text: "An anonymized Respect Index for the org", options: { bold: true, color: INKSOFT, bullet: { indent: 15 }, breakLine: true } },
  { text: "trends over time, never a name, never a quote.", options: { color: MUTED, bullet: false, indentLevel: 1 } },
], { x: MX, y: 2.85, w: 6.6, h: 2.3, fontFace: SANS, fontSize: 14.5, lineSpacingMultiple: 1.05 });
s.addText("The scoring engine is powered by a proprietary, validated behavioral taxonomy — our core IP, held as a trade secret and not shown here.", {
  x: MX, y: 5.5, w: 6.6, h: 0.9, fontFace: SANS, italic: true, fontSize: 12.5, color: MUTED, lineSpacingMultiple: 1.1,
});
// mock dashboard card (right)
const mx = 7.7, my = 2.05, mw = W - MX - mx, mh = 4.5;
card(s, mx, my, mw, mh, PAPER);
s.addText("Team · this quarter", { x: mx + 0.4, y: my + 0.35, w: 2.8, h: 0.35, fontFace: SANS, bold: true, fontSize: 12.5, color: MUTED });
s.addText([{ text: "78", options: { fontSize: 30, bold: true, fontFace: SERIF, color: JADE } }, { text: " /100", options: { fontSize: 14, color: MUTED } }], { x: mx + mw - 2.0, y: my + 0.2, w: 1.6, h: 0.6, align: "right" });
const rows = [["Listening", 0.74, GOOD], ["Disagree w/ dignity", 0.61, GOOD], ["Dismissive moments", 0.22, AMBER]];
let ry = my + 1.25;
rows.forEach(([lab, frac, col]) => {
  s.addText(lab, { x: mx + 0.4, y: ry - 0.02, w: 2.3, h: 0.3, fontFace: SANS, fontSize: 12, color: INKSOFT });
  const tx = mx + 2.75, tw = mw - 3.15;
  s.addShape(p.ShapeType.roundRect, { x: tx, y: ry + 0.03, w: tw, h: 0.16, rectRadius: 0.08, fill: { color: LINE }, line: { type: "none" } });
  s.addShape(p.ShapeType.roundRect, { x: tx, y: ry + 0.03, w: tw * frac, h: 0.16, rectRadius: 0.08, fill: { color: col }, line: { type: "none" } });
  ry += 0.5;
});
s.addText("RESPECT INDEX · 8 WEEKS", { x: mx + 0.4, y: my + 2.95, w: mw - 0.8, h: 0.3, fontFace: SANS, fontSize: 10, color: MUTED, charSpacing: 2 });
const spark = [0.52, 0.58, 0.55, 0.64, 0.69, 0.66, 0.74, 0.78];
const sbw = (mw - 0.9) / spark.length;
spark.forEach((v, i) => {
  s.addShape(p.ShapeType.rect, { x: mx + 0.45 + i * sbw, y: my + 4.15 - v * 0.85, w: sbw - 0.12, h: v * 0.85, fill: { color: JADE }, line: { type: "none" } });
});

// ===================== 7 · CULTURE FLYWHEEL =====================
s = p.addSlide(); bg(s, PAPER);
eyebrow(s, "06 · How culture actually shifts");
title(s, "Culture changes when people see\nthemselves — not when they’re told.");
s.addText([
  { text: "Culture doesn’t shift with yearly surveys, performance reviews, or 1:1s — those are watched, rated, and remembered. It shifts with ", options: {} },
  { text: "self-reflection", options: { bold: true } },
  { text: ", the part every program skips. The private mirror creates a quiet feedback loop no policy can: each person sees, in their own words, how they’re landing — and adjusts one small thing.", options: {} },
], { x: MX, y: 2.0, w: CW, h: 1.15, fontFace: SANS, fontSize: 15, color: INKSOFT, lineSpacingMultiple: 1.12 });
const steps = ["See yourself\n(your own words)", "Reflect,\nprivately", "Adjust one\nbehavior", "The room\nshifts"];
const fcw = 2.55, fgap = ((CW) - fcw * 4) / 3, fy = 3.5, fh = 1.7;
steps.forEach((st, i) => {
  const x = MX + i * (fcw + fgap);
  card(s, x, fy, fcw, fh, CARD);
  s.addText([{ text: (i + 1) + "  ", options: { color: JADE, bold: true, fontFace: SERIF, fontSize: 20 } }, { text: st, options: { color: INKSOFT, bold: true, fontSize: 14 } }],
    { x: x + 0.2, y: fy, w: fcw - 0.4, h: fh, align: "center", valign: "middle", fontFace: SANS, lineSpacingMultiple: 0.95 });
  if (i < 3) s.addText("→", { x: x + fcw, y: fy, w: fgap, h: fh, align: "center", valign: "middle", fontFace: SANS, fontSize: 22, color: MUTED });
});
s.addText([
  { text: "Because ", options: {} },
  { text: "no one is watching but you", options: { bold: true } },
  { text: ", people actually use it — no fear, no scoring, no manager in the middle. One person changing one behavior, repeated across a team, is what ", options: {} },
  { text: "slowly moves the needle", options: { bold: true } },
  { text: " — and the Respect Index turns that invisible shift into a trend leaders can finally see.", options: {} },
], { x: MX, y: 5.5, w: CW, h: 1.0, fontFace: SANS, italic: true, fontSize: 13, color: MUTED, lineSpacingMultiple: 1.1 });

// ===================== 8 · SELF-MANAGING TEAMS =====================
threeCards("07 · Self-managing teams", "Teams that steady themselves through change — no surveillance.",
  "In uncertain times, teams need to self-correct fast. SugApp gives a team a shared, private signal of its own health — a mirror for the group, not a report up the chain.", [
  { h: "A team mirror, not a manager’s dashboard", b: "The team sees its own health first and owns the response — support, not scrutiny." },
  { h: "Early warning during change", b: "Rising dismissiveness and falling acknowledgement show up weeks before resignations do." },
  { h: "Self-correction", b: "Shared awareness lets a team reset its own norms mid-reorg — the fastest, cheapest intervention there is." },
]);

// ===================== 9 · WHY WE WIN (2x2) =====================
s = p.addSlide(); bg(s, PAPER);
eyebrow(s, "08 · Why we win");
title(s, "Trust is the product, not the disclaimer.");
s.addText("Anyone can score text. The moat is being the tool a workforce will actually allow in — especially when they’re already anxious about AI watching them. We engineered that in from the first commit:", {
  x: MX, y: 1.95, w: CW, h: 0.8, fontFace: SANS, fontSize: 15, color: INKSOFT, lineSpacingMultiple: 1.1,
});
const pillars = [
  ["Opt-in, with a real opt-out", "No one is scored without consent. Withdrawing deletes what was collected. Enforced in code, not policy."],
  ["You see yourself first", "The person always sees their own feedback before anyone else — a mirror, not a report to your manager."],
  ["The org sees aggregates only", "Team-level trends, k-anonymized; small teams suppressed. Never a name, never a quote, up the chain."],
  ["Authenticated identity (SSO)", "Sign-in-with-Slack ties consent to a verified identity — no impersonation, reliable opt-out."],
];
const gw = 5.85, gh = 1.65, ggap = CW - gw * 2, gy0 = 3.0;
pillars.forEach((pl, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = MX + col * (gw + ggap), y = gy0 + row * (gh + 0.3);
  card(s, x, y, gw, gh, CARD);
  s.addText(pl[0], { x: x + 0.35, y: y + 0.22, w: gw - 0.7, h: 0.4, fontFace: SANS, bold: true, fontSize: 15.5, color: JADE });
  s.addText(pl[1], { x: x + 0.35, y: y + 0.68, w: gw - 0.7, h: 0.85, fontFace: SANS, fontSize: 13, color: MUTED, lineSpacingMultiple: 1.05 });
});

// ===================== 10 · MARKET & BUYER =====================
s = p.addSlide(); bg(s, PAPER);
eyebrow(s, "09 · Market & buyer");
title(s, "Sold to the people who now own\n“managing through change.”");
s.addText([
  { text: "The buyer is People / HR, People Analytics, and Transformation leaders", options: { bold: true, color: INKSOFT } },
  { text: " — already spending on engagement, DEI, and change-management, and now under acute pressure to carry a workforce through AI transformation without losing it.", options: { color: INKSOFT } },
], { x: MX, y: 2.1, w: 6.7, h: 1.6, fontFace: SANS, fontSize: 15, lineSpacingMultiple: 1.12 });
s.addText("We’re not creating a new budget; we’re a sharper instrument for one that already exists — and one regulators and works councils increasingly require to be privacy-first.", {
  x: MX, y: 3.85, w: 6.7, h: 1.3, fontFace: SANS, fontSize: 13.5, italic: true, color: MUTED, lineSpacingMultiple: 1.12,
});
const stx = 8.2, stw = W - MX - stx;
[["Land", "Start with one team that opts in — a fast, low-friction pilot, not a company-wide rollout.", 2.2],
 ["Expand", "Team wins become org rollout; the Respect Index becomes a tracked people-analytics KPI.", 4.4]].forEach(([h, b, y]) => {
  card(s, stx, y, stw, 2.0, CARD);
  s.addText(h, { x: stx + 0.35, y: y + 0.28, w: stw - 0.7, h: 0.6, fontFace: SERIF, bold: true, fontSize: 26, color: JADE });
  s.addText(b, { x: stx + 0.35, y: y + 0.95, w: stw - 0.7, h: 0.9, fontFace: SANS, fontSize: 13, color: MUTED, lineSpacingMultiple: 1.08 });
});

// ===================== 11 · BUSINESS MODEL =====================
s = p.addSlide(); bg(s, PAPER);
eyebrow(s, "10 · Business model");
title(s, "Per-seat SaaS — and every employee is a seat.", false, 0.92, 30);
s.addText([
  { text: "A mirror for ", options: {} },
  { text: "everyone", options: { italic: true } },
  { text: ", not a dashboard for a few managers — whole-company adoption, priced per seat. The cost to serve stays tiny because it scales with ", options: {} },
  { text: "message volume, not headcount", options: { bold: true } },
  { text: ".", options: {} },
], { x: MX, y: 1.72, w: CW, h: 0.75, fontFace: SANS, fontSize: 14.5, color: INKSOFT, lineSpacingMultiple: 1.1 });
const bmCards = [
  ["Recurring", "Per-active-participant monthly subscription; annual contracts at the org tier."],
  ["Every seat, margin-accretive", "Universal adoption, not power-users; each new seat adds far more revenue than cost."],
  ["Defensible margin", "Cost scales with scored volume; the taxonomy and trust posture are the durable moat."],
];
const bmcw = (CW - 0.8) / 3, bmy = 2.65, bmh = 1.5;
bmCards.forEach(([h, b], i) => {
  const x = MX + i * (bmcw + 0.4);
  card(s, x, bmy, bmcw, bmh, CARD);
  s.addText(h, { x: x + 0.28, y: bmy + 0.2, w: bmcw - 0.56, h: 0.55, fontFace: SANS, bold: true, fontSize: 15, color: INKSOFT, lineSpacingMultiple: 0.95 });
  s.addText(b, { x: x + 0.28, y: bmy + 0.75, w: bmcw - 0.56, h: 0.65, fontFace: SANS, fontSize: 12.5, color: MUTED, lineSpacingMultiple: 1.03 });
});
const stats = [
  ["≈ $0.30", "per opted-in employee / month to serve on Sonnet (~$0.10 on Haiku).", 34],
  ["~90%+", "modeled gross margin at an illustrative $4 / seat / month.", 34],
  ["Volume-based", "cost tracks messages, not seats — so it holds at 50 or 50,000 people.", 22],
];
const sy = 4.4, sh = 1.5;
stats.forEach(([n, lab, fs], i) => {
  const x = MX + i * (bmcw + 0.4);
  card(s, x, sy, bmcw, sh, PAPER);
  s.addText(n, { x: x + 0.28, y: sy + 0.2, w: bmcw - 0.56, h: 0.55, fontFace: SERIF, bold: true, fontSize: fs, color: JADE });
  s.addText(lab, { x: x + 0.28, y: sy + 0.8, w: bmcw - 0.56, h: 0.6, fontFace: SANS, fontSize: 12, color: MUTED, lineSpacingMultiple: 1.03 });
});
s.addText("Modeled from LLM token costs at ~75% opt-in (250-person example ≈ $35–70/mo to serve). Message volume is the main driver; $4/seat is illustrative — replace with your numbers before presenting.", {
  x: MX, y: 6.15, w: CW, h: 0.6, fontFace: SANS, italic: true, fontSize: 11.5, color: MUTED, lineSpacingMultiple: 1.05,
});

// ===================== 12 · STATUS =====================
s = p.addSlide(); bg(s, PAPER);
eyebrow(s, "11 · Status");
title(s, "Not a slideware idea — a working prototype.");
s.addText("The full loop runs today, end-to-end and offline-validated:", {
  x: MX, y: 1.95, w: CW, h: 0.5, fontFace: SANS, fontSize: 15, color: INKSOFT,
});
const built = [
  ["Live Slack connector", "OAuth token, real channel ingestion."],
  ["Consent gate + Sign-in-with-Slack SSO", "Opt-in enforced, tamper-proof."],
  ["Scoring engine", "Evidence + coaching rewrite per moment."],
  ["Personal mirror", "The private, name-attached view."],
  ["Org & team dashboards", "Respect Index, trends, k-anonymized."],
  ["Data layer", "Identity-keyed, penalty-free purge on opt-out."],
];
const colw = 5.85, cgap = CW - colw * 2, y0 = 2.75, rh = 1.15;
built.forEach((it, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = MX + col * (colw + cgap), y = y0 + row * rh;
  s.addShape(p.ShapeType.ellipse, { x, y: y + 0.06, w: 0.22, h: 0.22, fill: { color: GOOD } });
  s.addText("✓", { x, y: y + 0.02, w: 0.22, h: 0.28, align: "center", valign: "middle", fontFace: SANS, bold: true, fontSize: 11, color: PAPER });
  s.addText([{ text: it[0] + "  ", options: { bold: true, color: INKSOFT } }, { text: it[1], options: { color: MUTED } }],
    { x: x + 0.35, y, w: colw - 0.35, h: 0.9, fontFace: SANS, fontSize: 14, lineSpacingMultiple: 1.03 });
});
s.addText("Next: design partners for a live pilot, and calibration of the Index against real retention / engagement outcomes.", {
  x: MX, y: 6.35, w: CW, h: 0.6, fontFace: SANS, italic: true, fontSize: 13, color: MUTED,
});

// ===================== 13 · THE ASK (dark close) =====================
s = p.addSlide(); bg(s, INK);
eyebrow(s, "12 · The ask", true);
title(s, "What we want from LaunchUNC.", true, 0.95, 34);
const acw = 5.85, ach = 2.0, ay = 2.35;
[["Design partners", "Warm intros to 3–5 teams (10–40 people) going through change, willing to run a consented 6-week pilot and co-develop the Index.", MX],
 ["Pre-seed & mentorship", "Runway to calibrate the model and land the first paying pilots, plus go-to-market and enterprise-privacy guidance.", W - MX - acw]].forEach(([h, b, x]) => {
  s.addShape(p.ShapeType.roundRect, { x, y: ay, w: acw, h: ach, rectRadius: 0.11, fill: { color: INKSOFT }, line: { color: "24534C", width: 1 }, shadow: shadow() });
  s.addText(h, { x: x + 0.4, y: ay + 0.3, w: acw - 0.8, h: 0.5, fontFace: SANS, bold: true, fontSize: 18, color: JADE });
  s.addText(b, { x: x + 0.4, y: ay + 0.9, w: acw - 0.8, h: 1.0, fontFace: SANS, fontSize: 13.5, color: "C9DBD3", lineSpacingMultiple: 1.1 });
});
s.addText([
  { text: "Every company is asking their people to change faster than ever. ", options: { color: PAPER } },
  { text: "Respect is the leading indicator of whether they can", options: { color: JADE, bold: true } },
  { text: " — and no one else is measuring it.", options: { color: PAPER } },
], { x: MX, y: 4.9, w: CW, h: 1.3, fontFace: SERIF, fontSize: 23, lineSpacingMultiple: 1.1 });
s.addText("SugApp (working name)  ·  © 2026 <Your Legal Name>. All rights reserved.  ·  Confidential & Proprietary — contains trade-secret methodology.", {
  x: MX, y: 6.9, w: CW, h: 0.3, fontFace: SANS, fontSize: 10, color: "7E958F",
});

p.writeFile({ fileName: "/tmp/claude-0/-home-user-testapp/5c385122-4c38-5138-bc93-17090acbf689/scratchpad/SugApp_Investor_Brief.pptx" })
  .then(f => console.log("WROTE", f));
