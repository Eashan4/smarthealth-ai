// Tutorials deck: final/SmartHealth_AI_Tutorials_T1-T15.pptx  (one slide per tutorial, figures from tutorials/*/outputs)
const { THEME, HEX, A, TUT, ROOT, newDeck, img, card, stat, bullets, caption, finish } = require("./deck_common");
const path = require("path");
const O = (unit, f) => path.join(TUT, unit, "outputs", f);
const U1 = "unit1_ehr", U2 = "unit2_biomedical_imaging", U3 = "unit3_staffing_planning", U4 = "unit4_clinical_text", U5 = "unit5_dimensionality_behavioral";

const UNITS = [
  ["Unit 1", "Health records", "T1 T2 T3", "Understand, standardise and clean an EHR extract", "Synthetic EHR, 410 records"],
  ["Unit 2", "Biomedical imaging", "T4 T5 T6", "Enhance, restore, segment, match and visualise images", "scikit-image microscopy sample"],
  ["Unit 3", "Staffing and planning", "T7 T8 T9", "Forecast demand, then plan beds and staff", "Synthetic hospital data"],
  ["Unit 4", "Clinical text", "T10 T11 T12", "Classify, extract, rank and disambiguate notes", "Synthetic notes with gold labels"],
  ["Unit 5", "Reduction and behaviour", "T13 T14 T15", "Reduce dimensions; model behavioural drivers of weight", "Real breast-cancer data (T13); synthetic (T14-T15)"],
];

const TUTS = [
  { id: "T1", unit: 1, title: "Understanding EHR", layout: "side", imgs: [O(U1, "t1_missingness.png")], stat: ["14.6%", "missing in the worst field (glucose)"],
    did: ["Built a deliberately messy 410-record EHR", "Mapped ICD-10 codes and record structure", "Measured barriers: gaps, duplicates, mixed labels"], take: "Every later tutorial fixes a problem found here.",
    notes: "T1 explores the EHR as an analyst would: schema, ICD-10 coding and a quantified list of data-quality barriers. Data is synthetic by design." },
  { id: "T2", unit: 1, title: "Standardisation and data cleaning", layout: "side", table: true, stat: ["42", "Fahrenheit readings mixed in with Celsius"],
    did: ["Merged 8 gender spellings into 2", "Parsed 3 date formats into one", "Flagged 27 impossible SpO2 values; z-scored vitals"], take: "A unit mix-up looks fine until you average it.",
    notes: "Standardise first so cleaning and imputation downstream are trustworthy." },
  { id: "T3", unit: 1, title: "Redundant and missing data", layout: "side", imgs: [O(U1, "t3_missingness_before_after.png")], stat: ["15% to 0%", "worst-field missingness after cleaning"],
    did: ["Removed 30 duplicate encounters", "Deleted 7 rows missing both labs", "Imputed the rest: median, mode, KNN"], take: "Two strategies, chosen per field, not one default.",
    notes: "Listwise deletion where too little signal remains; imputation elsewhere matched to the field type." },
  { id: "T4", unit: 2, title: "Biomedical image processing", layout: "wide",
    imgs: [[O(U2, "t4_original.png"), "Original"], [O(U2, "t4_enhancement_clahe.png"), "CLAHE"], [O(U2, "t4_restoration_denoised.png"), "Denoised"], [O(U2, "t4_segmentation_mask.png"), "Otsu mask"]],
    stat: ["25.3 dB", "PSNR after denoising, from 20.1 dB"], did: ["CLAHE contrast enhancement", "Bilateral denoising after added noise", "Otsu segmentation; JPEG q10 to q90"], take: "JPEG: 5.2 KB at q10 up to 23.8 KB at q90.",
    notes: "Four classic stages, each measured. PSNR 20.1 to 25.3 dB after denoising; the mask covers 3.2 percent of pixels." },
  { id: "T5", unit: 2, title: "SIFT, RANSAC and a small CNN", layout: "side", imgs: [O(U2, "t5_ransac_matches.png")], stat: ["11.9 deg", "recovered for a true 12.0 deg rotation"],
    did: ["SIFT keypoints, 13 of 14 kept as inliers", "RANSAC rejects the bad matches", "Toy CNN: 56.7% on 30 held-out patches"], take: "Honest: the toy CNN barely beats chance.",
    notes: "RANSAC recovers the transform despite deliberately wrong matches. The toy CNN trains but is weak; we report that as is." },
  { id: "T6", unit: 2, title: "Biomedical image visualisation", layout: "side", imgs: [O(U2, "t6_side_by_side.png")], stat: ["3.2%", "of pixels segmented as foreground"],
    did: ["Side-by-side original vs processed", "Intensity histograms", "Segmentation boundary overlay"], take: "A metric does not show whether a result is usable. Looking does.",
    notes: "These panels are what a reviewer checks before trusting T4 and T5." },
  { id: "T7", unit: 3, title: "Patient prediction for improved staffing", layout: "wide", imgs: [O(U3, "t7_forecast.png")],
    stat: ["24.5 vs 37.4", "MAE: model vs same weekday last week"], did: ["Forecast ED arrivals 7 days ahead", "Turned the forecast into a nurse roster", "Costed idle vs missing nurse shifts"], take: "Forecast roster with buffer cost 1,991 vs 3,631 for a flat roster.",
    notes: "A forecast is only useful once converted into a decision and costed against a simple baseline." },
  { id: "T8", unit: 3, title: "Strategic planning I: descriptive", layout: "side", imgs: [O(U3, "t8_matrix.png")], stat: ["91.3%", "occupancy of 420 beds in 2024"],
    did: ["Scorecard for 6 service lines", "Margin per bed-day, growth, length of stay", "Growth-vs-margin matrix: grow, protect, fix, review"], take: "Orthopaedics earns most per bed-day; pulmonology least.",
    notes: "Where are we? Volume, bed-days, margin and growth for each service line." },
  { id: "T9", unit: 3, title: "Strategic planning II: predictive and prescriptive", layout: "side", imgs: [O(U3, "t9_projection.png")], stat: ["515 beds", "needed in 2027 against 420 licensed"],
    did: ["Trend projection with 80% scenarios", "Linear programme allocates scarce beds", "Shadow price: a bed-day is worth about 1,397"], take: "The optimal mix adds 1.6 M margin over equal cuts.",
    notes: "Where are we heading and what should we do? Projection, then an LP with a stated 80 percent service floor." },
  { id: "T10", unit: 4, title: "Classification and clustering of clinical text", layout: "wide", imgs: [O(U4, "t10_clusters.png")], stat: ["98.0%", "specialty accuracy (linear SVM)"],
    did: ["TF-IDF with NB, logistic regression, SVM", "K-means on SVD embeddings", "Boilerplate hid the topics: ARI 0.00 to 0.89"], take: "Scores are a ceiling effect of templated notes.",
    notes: "The clustering lesson: boilerplate sentences dominated until removed." },
  { id: "T11", unit: 4, title: "Information extraction and entity recognition", layout: "wide", imgs: [O(U4, "t11_ner_scores.png")], stat: ["0% vs 100%", "unseen drugs found: lexicon tagger vs no lexicon"],
    did: ["Regex for dose, BP, HR; v2 fixes 'over'", "Dictionary vs learned BIO tagger", "Negation rule: 100% on symptoms"], take: "A lexicon feature became a shortcut that hurt.",
    notes: "Test on drugs never seen in training. The tagger given a lexicon learned in-lexicon means drug and failed on new names." },
  { id: "T12", unit: 4, title: "Ranking and word-sense disambiguation", layout: "wide", imgs: [O(U4, "t12_ranking.png"), O(U4, "t12_wsd.png")], stat: ["0.85", "BM25 P@10 (TF-IDF 0.76)"],
    did: ["BM25 vs TF-IDF ranking, TextRank terms", "Disambiguated RA, MS, PT, cold, discharge", "Context model 0.99 vs 0.50 baseline"], take: "Context, not word frequency, resolves the sense.",
    notes: "Ranking scored with P at 10, MAP and nDCG; WSD with a most-frequent-sense baseline, simplified Lesk and Naive Bayes." },
  { id: "T13", unit: 5, title: "Dimensionality reduction for exploratory analysis", layout: "wide", imgs: [O(U5, "t13_embeddings.png")], stat: ["10 of 30", "components keep 95% variance and 98.1% accuracy"],
    did: ["Real Wisconsin breast-cancer data", "PCA, LDA, t-SNE, Isomap compared", "Reduction fitted inside each CV fold"], take: "The only tutorial on a real dataset.",
    notes: "Compared on kNN accuracy, silhouette and trustworthiness. LDA uses labels so it is an upper bound." },
  { id: "T14", unit: 5, title: "Behavioural factors and weight, part 1", layout: "side", imgs: [O(U5, "t14_effect_sizes.png")], stat: ["0.28", "eta-squared of physical activity, the top factor"],
    did: ["Kruskal-Wallis tests and effect sizes", "Benjamini-Hochberg: 9 of 13 significant", "Diet x activity interaction"], take: "Small planted effects (smoking, water) were not detected.",
    notes: "Synthetic data with planted effects, so the analysis can be checked against what was put in." },
  { id: "T15", unit: 5, title: "Behavioural factors and weight, part 2", layout: "wide", imgs: [O(U5, "t15_partial_dependence.png")], stat: ["98% vs 49%", "leaky vs behaviour-only class accuracy"],
    did: ["Leakage check with height and weight", "Boosting R2 0.81 vs OLS 0.77", "Importance, partial dependence, 4 phenotypes"], take: "Left: activity lowers BMI. Middle: snacking is non-monotone. One-hot encoding catches it.",
    notes: "A feature that defines the label gives an impressive and useless score." },
];

(async () => {
  const { pres, C } = newDeck("SmartHealth AI - Tutorials T1 to T15");
  pres.addSection({ title: "Overview" });
  let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Overview" });
  s.addText("Healthcare Analytics Tutorials", { x: 0.6, y: 1.2, w: 8.8, h: 0.9, fontSize: 42, bold: true, color: C.background1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
  s.addText("T1 to T15  |  five units, one folder, one command", { x: 0.6, y: 2.2, w: 8.8, h: 0.5, fontSize: 20, color: "CADCFC", margin: 0, isTextBox: true });
  s.addText([{ text: "Miman Nag  RA2311027010190", options: { breakLine: true } }, { text: "Eashan Jain  RA2311027010198" }], { x: 0.6, y: 3.3, w: 5, h: 0.7, fontSize: 15, color: C.background1, margin: 0, isTextBox: true });
  s.addText("21CSE428T Healthcare Analytics  |  SRM Institute of Science and Technology", { x: 0.6, y: 4.5, w: 8.8, h: 0.4, fontSize: 12, color: "9FB3C8", margin: 0, isTextBox: true });
  s.addNotes("Fifteen tutorials across five units. Each is a self-contained fixed-seed script that prints its results, saves figures and ends with assert-based checks. python tutorials/run_all.py runs everything.");

  // overview
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Overview" }); s.addText("Five units, fifteen tutorials, all passing their self-checks", { placeholder: "title" });
  s.addNotes("Most tutorials use synthetic or built-in data because the project itself uses no health records or imaging. Only T13 uses a real dataset.");
  UNITS.forEach((u, i) => {
    const y = 1.15 + i * 0.78;
    card(pres, C, s, 0.5, y, 9.0, 0.68, `unit ${i + 1} row`);
    s.addText(u[0], { x: 0.65, y, w: 0.9, h: 0.68, fontSize: 14, bold: true, color: C.accent2, valign: "middle", margin: 0, isTextBox: true });
    s.addText([{ text: u[1], options: { bold: true, fontSize: 15, color: C.text2, breakLine: true } }, { text: u[2], options: { fontSize: 12, color: C.accent5 } }], { x: 1.55, y, w: 2.5, h: 0.68, valign: "middle", margin: 0, isTextBox: true });
    s.addText(u[3], { x: 4.1, y, w: 3.0, h: 0.68, fontSize: 13, color: C.text1, valign: "middle", margin: 0, isTextBox: true });
    s.addText(u[4], { x: 7.15, y, w: 2.3, h: 0.68, fontSize: 12, italic: true, color: C.accent5, valign: "middle", margin: 0, isTextBox: true });
  });

  const th = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text2 } } });
  let lastUnit = 0;
  for (const t of TUTS) {
    if (t.unit !== lastUnit) { pres.addSection({ title: `Unit ${t.unit}: ${UNITS[t.unit - 1][1]}` }); lastUnit = t.unit; }
    s = pres.addSlide({ masterName: "CONTENT", sectionTitle: `Unit ${t.unit}: ${UNITS[t.unit - 1][1]}` });
    s.addText(`${t.id}  ${t.title}`, { placeholder: "title" }); s.addNotes(t.notes);
    if (t.layout === "side") {
      if (t.table) {
        s.addTable([[th("Check"), th("Before"), th("After")], ["Gender labels", "8 spellings", "2 (M, F)"], ["Date formats", "3 mixed", "1 (ISO)"], ["Temperature", "42 values in F", "all in C"], ["SpO2 out of range", "27 impossible", "flagged as missing"], ["Vitals scale", "mixed units", "z-scored"]],
          { x: 0.5, y: 1.3, w: 5.3, colW: [1.8, 1.7, 1.8], fontSize: 13, color: C.text1, border: { type: "solid", color: "D5DDE5", pt: 0.75 }, rowH: 0.5, valign: "middle", objectName: "T2 cleaning table" });
      } else await img(s, t.imgs[0], 0.5, 1.15, 5.3, 3.95, { alt: `${t.id} figure` });
      stat(s, C, 6.1, 1.15, 3.4, t.stat[0], t.stat[1], C.accent2, 30);
      s.addText("What we did", { x: 6.1, y: 2.3, w: 3.4, h: 0.3, fontSize: 14, bold: true, color: C.accent1, margin: 0, isTextBox: true });
      bullets(s, t.did, 6.1, 2.65, 3.4, 1.75, 13);
      s.addText(t.take, { x: 6.1, y: 4.4, w: 3.4, h: 0.7, fontSize: 13, italic: true, color: C.text2, margin: 0, valign: "top", isTextBox: true });
    } else {
      const n = t.imgs.length, gap = 0.2, w = (9.0 - gap * (n - 1)) / n;
      for (let i = 0; i < n; i++) {
        const p = Array.isArray(t.imgs[i]) ? t.imgs[i][0] : t.imgs[i];
        await img(s, p, 0.5 + i * (w + gap), 1.15, w, 2.3, { alt: `${t.id} figure ${i + 1}` });
        if (Array.isArray(t.imgs[i])) caption(s, C, t.imgs[i][1], 0.5 + i * (w + gap), 3.4, w);
      }
      card(pres, C, s, 0.5, 3.75, 3.5, 1.4, "did card"); card(pres, C, s, 4.15, 3.75, 2.4, 1.4, "stat card"); card(pres, C, s, 6.7, 3.75, 2.8, 1.4, "takeaway card");
      s.addText("What we did", { x: 0.62, y: 3.8, w: 3.3, h: 0.28, fontSize: 13, bold: true, color: C.accent1, margin: 0, isTextBox: true });
      bullets(s, t.did, 0.62, 4.1, 3.3, 1.05, 12);
      s.addText(t.stat[0], { x: 4.25, y: 3.82, w: 2.2, h: 0.5, fontSize: 22, bold: true, color: C.accent2, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
      s.addText(t.stat[1], { x: 4.25, y: 4.35, w: 2.2, h: 0.75, fontSize: 12, color: C.accent5, margin: 0, valign: "top", isTextBox: true });
      s.addText(t.take, { x: 6.82, y: 3.85, w: 2.6, h: 1.25, fontSize: 13, italic: true, color: C.text2, margin: 0, valign: "top", isTextBox: true });
    }
  }

  // synthesis
  pres.addSection({ title: "Close" });
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Close" }); s.addText("What carries over to the SmartHealth AI project", { placeholder: "title" });
  s.addNotes("Close by linking the tutorials to the project and by being clear about the data: synthetic except T13, and near-perfect text scores are a ceiling effect of templated notes.");
  [["Leakage and honest splits", "T3, T13, T15: fit on training data only; a feature that defines the label is a score you cannot trust."], ["Decisions, not just forecasts", "T7, T9: cost a forecast against a baseline; price scarce capacity with an LP."],
   ["Silent failures", "T10, T11: boilerplate dominated clusters; a lexicon feature became a shortcut."], ["Small and sufficient", "T13: 30 correlated features compress to 10 with no loss, like the 11.8 k-parameter CNN."]].forEach((c, i) => {
    const x = 0.5 + (i % 2) * 4.6, y = 1.2 + Math.floor(i / 2) * 1.85;
    card(pres, C, s, x, y, 4.4, 1.7, `lesson ${i + 1}`);
    s.addText(c[0], { x: x + 0.15, y: y + 0.1, w: 4.1, h: 0.4, fontSize: 16, bold: true, color: C.accent1, margin: 0, isTextBox: true });
    s.addText(c[1], { x: x + 0.15, y: y + 0.55, w: 4.1, h: 1.05, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText("Data: synthetic except T13 (real Wisconsin breast-cancer data). Near-perfect text scores (T10 to T12) are a ceiling effect of templated notes.", { x: 0.5, y: 4.95, w: 9.0, h: 0.3, fontSize: 11, italic: true, color: C.accent5, margin: 0, isTextBox: true });

  await finish(pres, path.join(ROOT, "final", "SmartHealth_AI_Tutorials_T1-T15.pptx"));
  console.log("tutorial deck built");
})().catch(e => { console.error(e); process.exit(1); });
