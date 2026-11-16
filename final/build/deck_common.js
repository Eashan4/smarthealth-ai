// Shared theme + helpers for the two decks. Run with NODE_PATH pointing at a folder holding pptxgenjs and sharp.
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const path = require("path");
// apply_theme.js (writes the theme colours into the saved deck) is not committed: copy scripts/apply_theme.js from the
// pptx skill next to this file. Without it the decks still build but scheme colours fall back to Office defaults.
let applyTheme = async () => console.warn("apply_theme.js not found: scheme colours will use Office defaults");
try { ({ applyTheme } = require("./apply_theme.js")); } catch (e) { /* optional */ }

const ROOT = path.resolve(__dirname, "..", "..");
const A = path.join(ROOT, "final", "assets");
const TUT = path.join(ROOT, "tutorials");

const THEME = {
  name: "SmartHealth", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "10243E", lt1: "FFFFFF", dk2: "0B2A4A", lt2: "EEF3F7", accent1: "0E8C8C", accent2: "E4572E", accent3: "F2A93B",
            accent4: "7A5CFA", accent5: "6B7A8C", accent6: "2E7D32", hlink: "0E8C8C", folHlink: "6B7A8C" },
};
const HEX = { navy: "0B2A4A", teal: "0E8C8C", coral: "E4572E", gold: "F2A93B", slate: "6B7A8C", violet: "7A5CFA", green: "2E7D32", ink: "10243E", tint: "EEF3F7" };

function newDeck(title) {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";           // 10 x 5.625 in
  pres.title = title; pres.author = "Miman Nag, Eashan Jain";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;
  pres.defineSlideMaster({ title: "TITLE_DARK", background: { color: HEX.navy }, objects: [], slideNumber: undefined });
  pres.defineSlideMaster({
    title: "CONTENT", background: { color: "FFFFFF" },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.25, w: 9.0, h: 0.8, fontSize: 24, bold: true, color: C.text2, align: "left", valign: "middle", margin: 0 }, text: "" } },
      { text: { text: "SmartHealth AI  |  21CSE428T Healthcare Analytics", options: { x: 0.5, y: 5.28, w: 6, h: 0.25, fontSize: 10, color: C.accent5, margin: 0 } } },
    ],
    slideNumber: { x: 9.0, y: 5.28, w: 0.5, h: 0.25, fontSize: 10, color: C.accent5, align: "right" },
  });
  return { pres, C };
}

async function dims(p) { const m = await sharp(p).metadata(); return { w: m.width, h: m.height }; }
// place an image inside a box, keeping aspect ratio, centred (or left/top aligned)
async function img(slide, p, x, y, w, h, opts = {}) {
  const d = await dims(p); const r = Math.min(w / d.w, h / d.h); const iw = d.w * r, ih = d.h * r;
  const ix = opts.left ? x : x + (w - iw) / 2, iy = opts.top ? y : y + (h - ih) / 2;
  slide.addImage({ path: p, x: ix, y: iy, w: iw, h: ih, altText: opts.alt || path.basename(p) });
  return { x: ix, y: iy, w: iw, h: ih };
}
const card = (pres, C, slide, x, y, w, h, name, fill) => slide.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill || C.background2 }, line: { type: "none" }, objectName: name || "card" });
function stat(slide, C, x, y, w, big, label, color, bigSize = 34) {
  slide.addText(big, { x, y, w, h: 0.62, fontSize: bigSize, bold: true, color: color || C.accent2, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
  slide.addText(label, { x, y: y + 0.62, w, h: 0.45, fontSize: 12, color: C.accent5, margin: 0, valign: "top", isTextBox: true });
}
function bullets(slide, items, x, y, w, h, size = 14, color) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6 } })),
    { x, y, w, h, fontSize: size, color, valign: "top", margin: 0, isTextBox: true });
}
const caption = (slide, C, t, x, y, w) => slide.addText(t, { x, y, w, h: 0.28, fontSize: 11, italic: true, color: C.accent5, margin: 0, isTextBox: true });
async function finish(pres, file) { await pres.writeFile({ fileName: file }); await applyTheme(file, THEME); }

module.exports = { pptxgen, THEME, HEX, A, TUT, ROOT, newDeck, img, card, stat, bullets, caption, finish, dims };
