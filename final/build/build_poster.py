"""Builds final/SmartHealth_AI_Poster_A3.pdf (A3 portrait; layout follows the reference poster)."""
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Image, KeepTogether, Paragraph, Spacer, Table, TableStyle
from common import *
import fonts  # noqa: registers the embedded Body font family

W, H = 841.89, 1190.55
M, GAP = 30, 18
MAROON, INK, GREY = colors.HexColor("#8C2F2A"), colors.HexColor("#1A1A1A"), colors.HexColor("#555555")
COLW = (W - 2 * M - 2 * GAP) / 3
S = lambda **k: ParagraphStyle("s", fontName=k.pop("fontName", "Body"), textColor=k.pop("textColor", INK), **k)
body = S(fontSize=10.4, leading=14.2, alignment=TA_LEFT, spaceAfter=5)
bul = S(fontSize=10.4, leading=14.2, leftIndent=11, bulletIndent=0, spaceAfter=4)
cap = S(fontName="Body-Oblique", fontSize=8.8, leading=11.4, textColor=GREY, spaceAfter=7, spaceBefore=2)
cell = S(fontSize=9.4, leading=11.6); cellb = S(fontName="Body-Bold", fontSize=9.4, leading=11.6)
sec = S(fontName="Body-Bold", fontSize=11.6, leading=14, spaceBefore=6, spaceAfter=5, keepWithNext=1)
call = S(fontName="Body-Bold", fontSize=10.2, leading=13.8)
bigp = S(fontName="Body-Bold", fontSize=22, leading=24, alignment=TA_CENTER, textColor=MAROON)
bigl = S(fontSize=8.2, leading=10, alignment=TA_CENTER, textColor=GREY)

def SEC(n, t): return Paragraph(f'<font color="#8C2F2A">{n}</font>&nbsp;&nbsp;{t.upper()}', sec)
def P(t, st=body): return Paragraph(t, st)
def BL(t): return Paragraph(t, bul, bulletText="–")
def IMG(path, w):
    iw, ih = ImageReader(str(path)).getSize(); return Image(str(path), width=w, height=w * ih / iw)
def table(head, rows, colw):
    d = [[Paragraph(h, cellb) for h in head]] + [[Paragraph(str(c), cellb if j == 0 and False else cell) for j, c in enumerate(r)] for r in rows]
    t = Table(d, colWidths=colw)
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), .8, INK), ("LINEBELOW", (0, 0), (-1, 0), .8, INK), ("LINEBELOW", (0, 1), (-1, -1), .3, colors.HexColor("#BBBBBB")),
                           ("LINEBELOW", (0, -1), (-1, -1), .8, INK), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t
def stats(items, w):
    n = len(items); cw = w / n
    t = Table([[P(a, bigp) for a, b in items], [P(b, bigl) for a, b in items]], colWidths=[cw] * n)
    t.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)])); return t
def callout(text, w):
    t = Table([[Paragraph(text, call)]], colWidths=[w])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF4D6")), ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#E3C77A")),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)])); return t
c_, l_ = R["selected_test"], R["other_test"]
lat = R["other_latency_ms"] / R["selected_latency_ms"]

col1 = [SEC(1, "The problem"), P("Falls are a leading cause of injury in older adults, and the danger is often lying undetected afterwards. Fall-alert pendants are expensive and single-purpose. "
        "<b>Can a very small neural network on a low-cost wrist wearable recognise activity and detect falls, and can the number it reports be trusted?</b>"),
        SEC(2, "The prototype"), IMG(A / "hw_wired.jpg", COLW), P("The assembled prototype: MAX30102 (green), MPU-6050 (blue) and an ESP8266 NodeMCU on a shared I²C bus.", cap),
        table(["Part", "Role"], [["MPU-6050", "6-axis motion, 50 Hz"], ["MAX30102", "heart rate, estimated SpO<sub>2</sub>"], ["NodeMCU ESP8266", "reads sensors, USB serial, buzzer"], ["Flask + SQLite", "ingest, model, alerts"]], [COLW * .38, COLW * .62]), Spacer(1, 8),
        SEC(3, "System pipeline"), IMG(A / "architecture.png", COLW), P("Same preprocessing code in training and in live inference: not equivalent, the same functions.", cap),
        SEC(4, "Is the data fit for use?"),
        BL("<b>Public data, matching sensors:</b> BITS-2, 41 subjects, recorded with an MPU-series IMU plus MAX30102."),
        BL("<b>205 of 980 trials dropped</b> (jumping, hand-swinging, lying transitions) rather than force-labelled; 775 windows remain."),
        BL("<b>Split by subject</b> (29 / 6 / 6): no person is in two splits; scaler fitted on train only; thresholds tuned on validation, never test."),
        BL("<b>Standing and tremor are not trained:</b> BITS-2 has neither. The dashboard says so instead of inventing a number."),
        table(["Split", "Subjects", "Windows"], [["train", "29", "547 (1,641 augmented)"], ["validation", "6", "114"], ["test", "6", "114"]], [COLW * .3, COLW * .25, COLW * .45])]

col2 = [SEC(5, "One small model"), P(f"A 1D CNN (two Conv-BN-ReLU-Pool blocks, global pooling, softmax) with <b>11,813 parameters and 52.9 KB</b>, compared with a two-layer LSTM of 52,037 parameters. "
        "Ten configurations were tried; selection used validation only; the held-out test set was scored once.", body),
        stats([(f"{100 * c_['accuracy']:.1f}%", "test accuracy"), (f"{100 * c_['fall_recall']:.1f}%", "fall recall"), (f"{lat:.0f}x", "faster than LSTM")], COLW), Spacer(1, 4),
        IMG(A / "cnn_vs_lstm.png", COLW), P("114 windows from six subjects never seen in training or tuning.", cap),
        table(["Model", "Acc.", "Macro-F1", "Fall recall", "Params"], [["CNN (deployed)", f"{c_['accuracy']:.3f}", f"{c_['macro_f1']:.3f}", f"{c_['fall_recall']:.3f}", "11,813"], ["LSTM", f"{l_['accuracy']:.3f}", f"{l_['macro_f1']:.3f}", f"{l_['fall_recall']:.3f}", "52,037"]],
              [COLW * .27, COLW * .13, COLW * .22, COLW * .18, COLW * .20]), Spacer(1, 5),
        SEC(6, "Where it is right and wrong"), IMG(A / "confusion.png", COLW * .72), P("Fall precision 0.956, recall 0.896: 43 of 48 test falls caught. Running and Lying have only 6 test windows each, so read them as indicative.", cap),
        callout("A live test caught a silent bug: a real fall scored 80% offline but 14% live. A rolling 3 s window was a different transform from training. Event-triggered segmentation with the same resampler fixed it.", COLW),
        Spacer(1, 7), SEC(7, "The tutorials, T1 to T15"),
        table(["Unit", "Result"], [
            ["T1-T3 EHR", "30 duplicates removed; missingness 15% to 0%"],
            ["T4-T6 imaging", "PSNR 20.1 to 25.3 dB; RANSAC 12.0° as 11.9°"],
            ["T7 staffing", f"forecast MAE {T7['models']['linear (calendar + Fourier)']['MAE']:.1f} vs {T7['models']['seasonal naive (t-7)']['MAE']:.1f} naive"],
            ["T8-T9 planning", f"515 beds needed in 2027 vs 420; LP +{T9['lp_gain_m']:.1f} M"],
            ["T10-T12 text", f"SVM {100 * T10['models']['Linear SVM']['test_acc']:.1f}%; BM25 P@10 {T12['ranking']['BM25']['P@10']:.2f}"],
            ["T13 dim. red.", f"{T13['k95']} PCs keep 95% of variance"],
            ["T14-T15 weight", f"activity is the top factor; leak {100 * T15['acc_leaky']:.0f}% vs {100 * T15['acc_behaviour_only']:.0f}%"]], [COLW * .30, COLW * .70])]

col3 = [SEC(8, "From a score to a fall decision"), P(f"The CNN gives P(fall). A threshold of <b>{TH['FALL_PROBABILITY_THRESHOLD']:.3f}</b> was chosen on validation: the highest-precision point with recall at least 0.90 (precision 1.00, recall 0.917)."),
        callout("The original design also required an acceleration rule. Measured: only 54% of real falls exceed it (many are soft falls onto a bed). Requiring it would roughly halve recall, so confirmation uses the AI probability alone and logs the rule for audit.", COLW),
        Spacer(1, 5), P("Four held-out scenarios pass end to end (walking, sitting, running, forward fall with buzzer). The cost of choosing recall: one short onset burst while running was flagged Fall at 52%. It is reported, not hidden."),
        SEC(9, "Tremor, without training data"), P("BITS-2 has no tremor class, so tremor is found by spectral analysis: a 3 s window, FFT, power in the 3 to 8 Hz band, a sharp peak, and little slow motion. Walking and running are rejected."),
        IMG(A / "tremor_spectra.png", COLW), P("Rest, a 5 Hz tremor and walking. All 10 synthetic test cases pass; <b>not yet validated on real tremor</b>.", cap),
        SEC(10, "Live dashboard"), IMG(ROOT / "docs" / "screenshots" / "dashboard-desktop.png", COLW * .7), Spacer(1, 4), IMG(ROOT / "docs" / "screenshots" / "dashboard-alert.png", COLW * .7),
        P("Calm state (top) and a confirmed-fall alert (bottom). The waveform is the acceleration signal the model classifies.", cap),
        SEC(11, "What is not measured"), BL("Accuracy on this prototype's own sensors: results come from BITS-2 recordings."), BL("Only 6 test subjects; read the percentages as indicative."),
        BL("Post-fall inactivity (1.5 s) is provisional; SpO<sub>2</sub> is a simplified estimate, not a medical reading."), BL("Tutorials use synthetic data except T13.")]

concl = [("Splits decide honesty.", "Splitting by subject and fitting preprocessing on training data only is what makes 85.1% believable."),
         ("Test the live path.", "Offline and live disagreed until segmentation used the training transform. Only a live test showed it."),
         ("Let data overrule the design.", "The rule gate would have halved fall recall, so the AI threshold decides and the rule explains."),
         ("Say what is unknown.", "Standing, real tremor and on-hardware accuracy are open items, written down rather than faked.")]

def build(fn):
    c = canvas.Canvas(fn, pagesize=(W, H)); c.setTitle("SmartHealth AI - Poster"); c.setAuthor("Miman Nag, Eashan Jain")
    c.setFillColor(MAROON); c.rect(0, H - 14, W, 14, stroke=0, fill=1)
    c.drawImage(str(A / "srm_logo.png"), M, H - 118, width=150, height=150 * 193 / 548, mask="auto")
    c.setFillColor(INK); c.setFont("Body-Bold", 38); c.drawCentredString(W / 2 + 60, H - 60, "SmartHealth AI")
    c.setFont("Body-Oblique", 11.5); c.setFillColor(GREY)
    c.drawCentredString(W / 2 + 60, H - 80, "A low-cost wearable for activity, fall, tremor and vital-sign monitoring with deep learning")
    c.setFont("Body-Bold", 11); c.setFillColor(MAROON)
    c.drawCentredString(W / 2 + 60, H - 98, f"{TEAM[0][0].title()} ({TEAM[0][1]})  ·  {TEAM[1][0].title()} ({TEAM[1][1]})  ·  {COURSE.replace('HEALTHCARE ANALYTICS', 'Healthcare Analytics')}")
    c.setFont("Body", 10); c.setFillColor(INK)
    c.drawCentredString(W / 2 + 60, H - 113, "Department of Data Science and Business Systems, SRM Institute of Science and Technology, Kattankulathur")
    top, bottom = H - 135, 170
    for i, content in enumerate((col1, col2, col3)):
        f = Frame(M + i * (COLW + GAP), bottom, COLW, top - bottom, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
        items = list(content); f.addFromList(items, c)
        if items: raise SystemExit(f"column {i + 1} overflows: {len(items)} flowables left")
        used = (top - bottom) - f._y1p + f._y1 if False else None
    # conclusions band
    c.setFillColor(INK); c.setFont("Body-Bold", 10.6); c.drawString(M, 152, ""); 
    c.setFillColor(MAROON); c.drawString(M, 150, "12"); c.setFillColor(INK); c.drawString(M + 16, 150, "CONCLUSIONS")
    bw = (W - 2 * M - 3 * 12) / 4
    for i, (h, t) in enumerate(concl):
        f = Frame(M + i * (bw + 12), 40, bw, 100, leftPadding=8, rightPadding=8, topPadding=7, bottomPadding=4, showBoundary=0)
        c.setFillColor(colors.HexColor("#F2F2F2")); c.rect(M + i * (bw + 12), 40, bw, 100, stroke=0, fill=1)
        items = [P(f"<b>{h}</b>", S(fontName="Body-Bold", fontSize=10, leading=12.5, textColor=MAROON, spaceAfter=3)), P(t, S(fontSize=9, leading=12))]
        f.addFromList(items, c)
        if items: raise SystemExit("conclusion box overflows")
    c.setStrokeColor(colors.HexColor("#BBBBBB")); c.line(M, 30, W - M, 30)
    c.setFont("Body", 7.6); c.setFillColor(GREY)
    c.drawString(M, 18, "Every figure is an output of the project's own code; every number is quoted from a run. Academic prototype: monitoring and classification, not a certified medical device.")
    c.drawRightString(W - M, 18, "Data: BITS-2, Zenodo 10.5281/zenodo.10013090")
    c.showPage(); c.save()

if __name__ == "__main__":
    build(str(OUT / "SmartHealth_AI_Poster_A3.pdf")); print("poster built")
