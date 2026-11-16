// Final project deck: final/SmartHealth_AI_Final_Presentation.pptx
const { THEME, HEX, A, ROOT, newDeck, img, card, stat, bullets, caption, finish } = require("./deck_common");
const fs = require("fs"), path = require("path");
const R = JSON.parse(fs.readFileSync(path.join(ROOT, "models", "training_results.json")));
const T = R.selected_test, L = R.other_test;
const SHOT = (n) => path.join(ROOT, "docs", "screenshots", n);

(async () => {
  const { pres, C } = newDeck("SmartHealth AI - Final Project Presentation");
  const add = (title, section, notes) => { const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section }); s.addText(title, { placeholder: "title" }); if (notes) s.addNotes(notes); return s; };

  // 1 ---- title
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Introduction" });
  s.addText("SmartHealth AI", { x: 0.6, y: 0.9, w: 5, h: 0.9, fontSize: 46, bold: true, color: C.background1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
  s.addText("A low-cost wearable for activity, fall, tremor and vital-sign monitoring with deep learning", { x: 0.6, y: 1.85, w: 4.5, h: 1.0, fontSize: 18, color: "CADCFC", margin: 0, valign: "top", isTextBox: true });
  s.addText([{ text: "Miman Nag  RA2311027010190", options: { breakLine: true } }, { text: "Eashan Jain  RA2311027010198" }], { x: 0.6, y: 3.2, w: 4.5, h: 0.7, fontSize: 15, color: C.background1, margin: 0, isTextBox: true });
  s.addText("21CSE428T Healthcare Analytics\nDepartment of Data Science and Business Systems, SRM Institute of Science and Technology", { x: 0.6, y: 4.2, w: 4.7, h: 0.8, fontSize: 11, color: "9FB3C8", margin: 0, valign: "top", isTextBox: true });
  const p = await img(s, path.join(A, "hw_wired.jpg"), 5.4, 0.8, 4.2, 3.2, { alt: "Assembled prototype on a breadboard" });
  caption(s, { accent5: "9FB3C8" }, "The assembled prototype: MAX30102, MPU-6050 and ESP8266 NodeMCU", 5.4, p.y + p.h + 0.08, 4.2);
  s.addText("Academic prototype: monitoring and classification, not a certified medical device.", { x: 5.4, y: 4.75, w: 4.2, h: 0.4, fontSize: 11, color: "9FB3C8", margin: 0, isTextBox: true });
  s.addNotes("SmartHealth AI is a wrist-style wearable we built for the Healthcare Analytics course. The photo is our real prototype. State the scope up front: monitoring and classification prototype, not a medical device.");

  // 2 ---- problem
  s = add("Falls go unnoticed; pendants are costly and single-purpose", "Introduction",
    "Criterion 1. Falls are a leading cause of injury in older adults; the real danger is lying undetected. We ask two questions: can a tiny network do this, and can its number be trusted?");
  card(pres, C, s, 0.5, 1.2, 4.0, 3.85, "problem card");
  s.addText("The problem", { x: 0.7, y: 1.3, w: 3.6, h: 0.4, fontSize: 18, bold: true, color: C.accent1, margin: 0, isTextBox: true });
  bullets(s, ["Falls are a leading cause of injury in older adults", "The danger: lying undetected afterwards", "Pendants: expensive, single-purpose, reactive"], 0.7, 1.8, 3.6, 1.8, 14);
  s.addText("Can a very small network on a cheap wearable detect falls, and can its number be trusted?", { x: 0.7, y: 3.75, w: 3.6, h: 1.1, fontSize: 15, bold: true, italic: true, color: C.text2, margin: 0, valign: "top", isTextBox: true });
  const objs = ["Assemble a wearable prototype and stream its data", "Prove the data is subject-disjoint and leakage-free", "Compare a 1D CNN with an LSTM; add a tremor detector", "Turn model output into a tested fall decision", "Complete tutorials T1 to T15 for the wider syllabus"];
  objs.forEach((t, i) => {
    const y = 1.2 + i * 0.78;
    s.addShape(pres.shapes.OVAL, { x: 4.9, y: y + 0.05, w: 0.5, h: 0.5, fill: { color: C.accent1 }, line: { type: "none" }, objectName: `objective ${i + 1} badge` });
    s.addText(String(i + 1), { x: 4.9, y: y + 0.05, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText(t, { x: 5.6, y, w: 3.9, h: 0.62, fontSize: 14, color: C.text1, valign: "middle", margin: 0, isTextBox: true });
  });

  // 3 ---- hardware
  pres.addSection({ title: "Method" });
  s = add("A three-board prototype streams motion and pulse over USB", "Method",
    "Show the photo. NodeMCU ESP8266 reads the MPU-6050 at 50 Hz and the MAX30102, both on one I2C bus, and sends lines over USB serial. Be clear on what is verified: the serial path against an emulated board. What is not measured is model accuracy on this exact hardware.");
  await img(s, path.join(A, "hw_parts.jpg"), 0.5, 1.2, 4.6, 3.3, { alt: "The three modules" });
  caption(s, C, "MAX30102 (green), MPU-6050 (blue), NodeMCU ESP8266", 0.5, 4.6, 4.6);
  const th = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 } } });
  s.addTable([[th("Part"), th("Role")], ["MPU-6050", "6-axis motion at 50 Hz"], ["MAX30102", "Heart rate, estimated SpO2"], ["NodeMCU ESP8266", "Reads both, streams over USB"], ["Buzzer + button", "Local fall alert, mute"]],
    { x: 5.4, y: 1.2, w: 4.1, colW: [1.6, 2.5], fontSize: 13, color: C.text1, border: { type: "solid", color: "D5DDE5", pt: 0.75 }, rowH: 0.36, objectName: "parts table" });
  card(pres, C, s, 5.4, 3.3, 4.1, 1.75, "verified card");
  s.addText([{ text: "Verified: ", options: { bold: true, color: C.accent6 } }, { text: "serial bridge ingested 83 samples from an emulated board and returned the buzzer command", options: { breakLine: true } },
             { text: "Not measured: ", options: { bold: true, color: C.accent2 } }, { text: "model accuracy on this exact hardware" }],
    { x: 5.55, y: 3.38, w: 3.8, h: 1.6, fontSize: 13, color: C.text1, valign: "middle", margin: 0, paraSpaceAfter: 6, isTextBox: true });

  // 4 ---- pipeline
  s = add("One pipeline, and the same preprocessing in training and live", "Method",
    "Criterion 2. Read the diagram top row left to right, then the bottom row right to left. The design rule: training and inference use the same preprocessing code, not an equivalent re-implementation. We learned why the hard way, which is on a later slide.");
  const a = await img(s, path.join(A, "architecture.png"), 0.5, 1.15, 9.0, 3.45, { alt: "Pipeline diagram" });
  s.addText("Every threshold lives in one config file, and each is derived from data or flagged provisional.", { x: 0.5, y: 4.7, w: 9.0, h: 0.4, fontSize: 14, italic: true, color: C.text2, margin: 0, align: "center", isTextBox: true });

  // 5 ---- data
  pres.addSection({ title: "Data and model" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Data and model" }); s.addText("Public data from matching sensors, split by person", { placeholder: "title" });
  s.addNotes("BITS-2 was chosen because its device has the same sensor pair as ours. 205 of 980 trials were dropped rather than force-labelled. The split is by subject, so no person appears in two splits, the scaler is fitted on training data only, and thresholds are tuned on validation, never test. Standing and tremor have no data, so they are not trained.");
  stat(s, C, 0.5, 1.2, 2.0, "41", "subjects, same sensor pair", C.accent2);
  stat(s, C, 2.6, 1.2, 2.0, "775", "usable windows", C.accent2);
  stat(s, C, 4.7, 1.2, 2.0, "205", "trials dropped, not force-labelled", C.accent2);
  s.addChart(pres.charts.BAR, [{ name: "Windows", labels: ["Fall", "Walking", "Sitting", "Running", "Lying"], values: [324, 246, 123, 41, 41] }],
    { x: 0.5, y: 2.35, w: 6.2, h: 2.8, barDir: "col", chartColors: [HEX.teal], showTitle: true, title: "Windows per class", titleFontSize: 13, titleColor: HEX.ink,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.ink, catAxisLabelColor: HEX.ink, valAxisLabelColor: HEX.slate, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
      valGridLine: { color: "E3E8EE", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, valAxisLabelFontSize: 10, catAxisLabelFontSize: 11 });
  card(pres, C, s, 7.0, 1.2, 2.5, 3.85, "discipline card");
  s.addText("Training discipline", { x: 7.15, y: 1.3, w: 2.2, h: 0.35, fontSize: 15, bold: true, color: C.accent1, margin: 0, isTextBox: true });
  bullets(s, ["Split by subject: 29 / 6 / 6", "Scaler fit on train only", "Thresholds tuned on validation", "Standing and tremor: no data, not trained"], 7.15, 1.75, 2.2, 3.2, 13);

  // 6 ---- model comparison
  s = add("An 11.8 k-parameter CNN beats the LSTM on every axis", "Data and model",
    "Ten configurations, selection on validation only, test set scored once. The CNN wins accuracy, macro-F1 and fall recall, is about 16 times faster and 4.4 times smaller. A plausible reason: small data and whole-trial windows favour the CNN's local-pattern bias.");
  s.addChart(pres.charts.BAR, [{ name: "1D CNN (deployed)", labels: ["Accuracy", "Macro-F1", "Fall recall"], values: [T.accuracy, T.macro_f1, T.fall_recall].map(v => +v.toFixed(3)) },
                               { name: "LSTM", labels: ["Accuracy", "Macro-F1", "Fall recall"], values: [L.accuracy, L.macro_f1, L.fall_recall].map(v => +v.toFixed(3)) }],
    { x: 0.5, y: 1.15, w: 5.6, h: 3.95, barDir: "col", chartColors: [HEX.coral, HEX.slate], showTitle: true, title: "Held-out test set (114 windows, 6 unseen subjects)", titleFontSize: 13, titleColor: HEX.ink,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.ink, dataLabelFormatCode: "0.000", valAxisLabelFormatCode: "0.0", valAxisMinVal: 0.5, valAxisMaxVal: 1.0, catAxisLabelColor: HEX.ink, valAxisLabelColor: HEX.slate,
      catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", valGridLine: { color: "E3E8EE", size: 0.5 }, catGridLine: { style: "none" }, showLegend: true, legendPos: "b", legendFontSize: 11, legendColor: HEX.ink, legendFontFace: "+mn-lt", valAxisLabelFontSize: 10, catAxisLabelFontSize: 11 });
  stat(s, C, 6.5, 1.2, 1.5, `${(100 * T.accuracy).toFixed(1)}%`, "test accuracy", C.accent2, 30);
  stat(s, C, 8.05, 1.2, 1.5, `${(100 * T.fall_recall).toFixed(1)}%`, "fall recall", C.accent2, 30);
  stat(s, C, 6.5, 2.55, 1.5, `${Math.round(R.other_latency_ms / R.selected_latency_ms)}x`, "faster than the LSTM", C.accent1, 30);
  stat(s, C, 8.05, 2.55, 1.5, "4.4x", "fewer parameters (11,813)", C.accent1, 30);
  s.addText("Fall recall was weighted first in model selection; the CNN wins it too, so this was not a trade-off.", { x: 6.5, y: 3.95, w: 3.0, h: 1.1, fontSize: 13, italic: true, color: C.text2, margin: 0, valign: "top", isTextBox: true });

  // 7 ---- confusion
  pres.addSection({ title: "Results" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" }); s.addText("Fall is caught 43 times out of 48 on unseen subjects", { placeholder: "title" });
  s.addNotes("Criterion 4. Fall precision 0.956, recall 0.896, F1 0.925. The five misses go to Sitting and Lying, the two quiet classes. Running and Lying have only six test windows each, so their scores are indicative, not precise.");
  await img(s, path.join(A, "confusion.png"), 0.5, 1.15, 4.6, 3.95, { alt: "Confusion matrix" });
  s.addText("Fall class", { x: 5.4, y: 1.2, w: 4.1, h: 0.35, fontSize: 16, bold: true, color: C.accent1, margin: 0, isTextBox: true });
  stat(s, C, 5.4, 1.6, 1.3, "0.956", "precision", C.accent2, 28); stat(s, C, 6.75, 1.6, 1.3, "0.896", "recall", C.accent2, 28); stat(s, C, 8.1, 1.6, 1.3, "0.925", "F1", C.accent2, 28);
  bullets(s, ["The 5 missed falls go to Sitting (2) and Lying (3), the two quiet classes", "Walking is confused with Sitting 6 times", "Running and Lying have 6 test windows each: indicative only"], 5.4, 2.85, 4.1, 1.5, 14);
  s.addText("Read 85.1% as \"this model on this 6-subject test set\", not as a general claim.", { x: 5.4, y: 4.4, w: 4.1, h: 0.65, fontSize: 13, italic: true, color: C.accent2, margin: 0, valign: "top", isTextBox: true });

  // 8 ---- decision engine
  s = add("Data overruled the design: the AI decides, the rule explains", "Results",
    "The original plan required AI and a rule check. We measured the rule: only 54 percent of real falls exceed the acceleration threshold, because many are soft falls onto a bed. Requiring it would roughly halve recall, so confirmation uses the AI probability alone and the rule signals are logged for audit. The cost is a measured false positive on a running onset burst, which we report.");
  s.addChart(pres.charts.DOUGHNUT, [{ name: "Falls", labels: ["Exceed the acceleration rule", "Do not"], values: [54, 46] }],
    { x: 0.5, y: 1.15, w: 3.6, h: 3.4, holeSize: 62, chartColors: [HEX.teal, "D5DDE5"], showLegend: true, legendPos: "b", legendFontSize: 11, legendColor: HEX.ink, legendFontFace: "+mn-lt", showPercent: false, showValue: true, dataLabelColor: "FFFFFF", dataLabelFontSize: 13, showTitle: true, title: "Real falls vs the rule", titleFontSize: 13, titleColor: HEX.ink });
  const steps = [["P(fall) at least 0.466", "threshold from validation: precision 1.00, recall 0.917"], ["Confirm on AI probability alone", "rule signals attached to every alert"], ["Buzzer, dashboard alert, cooldown", "no repeat until the AI stops flagging"]];
  steps.forEach((st, i) => {
    const y = 1.2 + i * 1.0;
    card(pres, C, s, 4.5, y, 5.0, 0.85, `step ${i + 1}`);
    s.addText(String(i + 1), { x: 4.6, y, w: 0.5, h: 0.85, fontSize: 24, bold: true, color: C.accent1, fontFace: THEME.headFontFace, valign: "middle", margin: 0, isTextBox: true });
    s.addText([{ text: st[0], options: { bold: true, fontSize: 15, breakLine: true } }, { text: st[1], options: { fontSize: 12, color: C.accent5 } }], { x: 5.15, y, w: 4.25, h: 0.85, valign: "middle", margin: 0, color: C.text1, isTextBox: true });
  });
  s.addText("Cost of choosing recall: one short onset burst while running was flagged Fall at 52%. Reported, not hidden.", { x: 4.5, y: 4.25, w: 5.0, h: 0.8, fontSize: 13, italic: true, color: C.accent2, margin: 0, valign: "top", isTextBox: true });

  // 9 ---- live bug story + tremor
  s = add("Tremor is found by its spectrum, not by a model with no data", "Results",
    "BITS-2 has no tremor class, so a trained tremor class would have no honest labels. The detector is signal processing: a 3 second window, FFT, power in the 3 to 8 hertz band, a sharp peak, little slow motion. All ten synthetic cases pass, but it has not been validated on a real tremor, and we say so.");
  await img(s, path.join(A, "tremor_spectra.png"), 0.5, 1.15, 9.0, 2.5, { alt: "Spectra of rest, tremor and walking" });
  [["Method", "3 s window, FFT, power in the 3 to 8 Hz band, sharp peak, little slow motion"], ["Validation", "10 of 10 synthetic cases pass: rest, tremors, walking, running, vibration"], ["Limit", "Not yet checked on a real tremor; thresholds are starting values"]].forEach((c, i) => {
    const x = 0.5 + i * 3.1;
    card(pres, C, s, x, 3.8, 2.9, 1.3, `tremor card ${i + 1}`);
    s.addText([{ text: c[0], options: { bold: true, fontSize: 14, color: i === 2 ? C.accent2 : C.accent1, breakLine: true } }, { text: c[1], options: { fontSize: 12 } }], { x: x + 0.12, y: 3.85, w: 2.66, h: 1.2, margin: 0, valign: "top", color: C.text1, isTextBox: true });
  });

  // 10 ---- dashboard
  s = add("Live dashboard: the waveform is the signal the model classifies", "Results",
    "Real screenshots against the live backend with the trained model, not mock-ups. Left: calm state. Middle: confirmed fall, the API returns buzzer true. Right: mobile layout. Tremor status and the serial port connect control are on the same page.");
  const d1 = await img(s, SHOT("dashboard-desktop.png"), 0.5, 1.15, 3.7, 2.9, { alt: "Dashboard calm" });
  await img(s, SHOT("dashboard-alert.png"), 4.35, 1.15, 3.7, 2.9, { alt: "Dashboard alert" });
  await img(s, SHOT("dashboard-mobile.png"), 8.2, 1.15, 1.3, 3.9, { alt: "Dashboard mobile" });
  caption(s, C, "Calm state: Walking, 82 bpm", 0.5, 4.15, 3.7); caption(s, C, "Confirmed fall alert", 4.35, 4.15, 3.7);
  s.addText("Cards: heart rate, SpO2, activity, fall, tremor. Polls every 2 s. Connects the USB board from the top bar.", { x: 0.5, y: 4.55, w: 7.5, h: 0.5, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });

  // 11 ---- tutorials
  pres.addSection({ title: "Coursework and close" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Coursework and close" }); s.addText("Tutorials T1 to T15 cover the rest of the syllabus", { placeholder: "title" });
  s.addNotes("All fifteen tutorials are in one folder and run with one command; all pass their self-checks. They use synthetic or built-in data, except T13 which uses a real dataset. The separate tutorial deck walks through each one.");
  const units = [["Unit 1", "T1 to T3  Health records", "410-record EHR cleaned: duplicates out, missingness 15% to 0%"], ["Unit 2", "T4 to T6  Biomedical imaging", "PSNR 20.1 to 25.3 dB; RANSAC recovers 12.0 deg as 11.9 deg"],
                 ["Unit 3", "T7 to T9  Staffing, planning", "Forecast MAE 24.5 vs 37.4; 515 beds needed in 2027 vs 420"], ["Unit 4", "T10 to T12  Clinical text", "98.0% specialty accuracy; BM25 P@10 0.85; WSD 0.99"],
                 ["Unit 5", "T13 to T15  Reduction, behaviour", "10 of 30 components keep 95%; height + weight leak the label"]];
  units.forEach((u, i) => {
    const y = 1.2 + Math.floor(i / 3) * 1.95;
    const px = i < 3 ? 0.5 + i * 3.1 : 0.5 + (i - 3) * 4.6, pw = i < 3 ? 2.9 : 4.4;
    card(pres, C, s, px, y, pw, 1.75, `unit ${i + 1}`);
    s.addText(u[0], { x: px + 0.15, y: y + 0.1, w: pw - 0.3, h: 0.3, fontSize: 12, bold: true, color: C.accent2, margin: 0, isTextBox: true });
    s.addText(u[1], { x: px + 0.15, y: y + 0.4, w: pw - 0.3, h: 0.35, fontSize: 15, bold: true, color: C.text2, margin: 0, isTextBox: true });
    s.addText(u[2], { x: px + 0.15, y: y + 0.8, w: pw - 0.3, h: 0.85, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText("15 of 15 pass their self-checks. Synthetic data except T13.", { x: 0.5, y: 5.0, w: 6, h: 0.25, fontSize: 11, italic: true, color: C.accent5, margin: 0, isTextBox: true });

  // 12 ---- limits
  s = add("What is not yet measured, and what we do next", "Coursework and close",
    "Honest limits. The biggest: accuracy on this prototype is unmeasured because every number comes from BITS-2 recordings. Tremor thresholds are starting values validated only on simulated signals. Post-fall inactivity is a provisional 1.5 seconds.");
  const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 } } });
  s.addTable([[hdr("Open item"), hdr("Why"), hdr("Next step")],
    ["Accuracy on our hardware", "Model trained on BITS-2's device", "Record labelled trials on the prototype"],
    ["Real tremor", "Validated on synthetic signals only", "Test with a real or deliberate 5 Hz tremor"],
    ["Standing class", "BITS-2 has no standing activity", "Collect it on the prototype"],
    ["Post-fall inactivity", "1.5 s is provisional", "Derive from continuous recordings"],
    ["Onset false positive", "Recall-over-precision choice", "Labelled transition-onset data, re-validate"],
    ["SpO2", "Simplified estimate, not clinical", "Use the reference algorithm"]],
    { x: 0.5, y: 1.2, w: 9.0, colW: [2.4, 3.2, 3.4], fontSize: 13, color: C.text1, border: { type: "solid", color: "D5DDE5", pt: 0.75 }, rowH: 0.5, valign: "middle", objectName: "open items table" });

  // 13 ---- conclusion
  s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Coursework and close" });
  s.addText("Conclusion", { x: 0.6, y: 0.5, w: 8.8, h: 0.7, fontSize: 34, bold: true, color: C.background1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
  [["Splits decide honesty", "Splitting by subject is what makes 85.1% believable."], ["Test the live path", "A real fall scored 80% offline and 14% live until segmentation used the training transform."], ["Let data overrule the design", "The rule gate would have halved fall recall, so the AI threshold decides."]].forEach((c, i) => {
    const x = 0.6 + i * 3.0;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.5, w: 2.8, h: 2.6, fill: { color: "14375E" }, line: { type: "none" }, objectName: `takeaway ${i + 1}` });
    s.addText(c[0], { x: x + 0.15, y: 1.6, w: 2.5, h: 0.8, fontSize: 17, bold: true, color: C.accent3, margin: 0, valign: "top", isTextBox: true });
    s.addText(c[1], { x: x + 0.15, y: 2.45, w: 2.5, h: 1.6, fontSize: 14, color: C.background1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText("Thank you. Questions?", { x: 0.6, y: 4.4, w: 6, h: 0.5, fontSize: 22, color: C.background1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
  s.addNotes("Three takeaways. Then offer the live demo: python -m tests.demo_5min --fast streams a five-minute activity arc ending in a fall.");

  await finish(pres, path.join(ROOT, "final", "SmartHealth_AI_Final_Presentation.pptx"));
  console.log("project deck built");
})().catch(e => { console.error(e); process.exit(1); });
