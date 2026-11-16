"""Builds final/SmartHealth_AI_Project_Report.pdf (layout follows the reference report: cover, abstract, contents,
list of figures, numbered chapters, tables with captions, references, appendices)."""
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents
from common import *
import fonts  # noqa: registers the embedded Body font family

S = lambda **k: ParagraphStyle("s", fontName=k.pop("fontName", "Body"), **k)
body = S(fontSize=10, leading=14.2, alignment=TA_JUSTIFY, spaceAfter=6)
bullet = S(fontSize=10, leading=14, alignment=TA_JUSTIFY, leftIndent=16, bulletIndent=4, spaceAfter=3)
h1 = S(fontName="Body-Bold", fontSize=18, leading=22, spaceBefore=0, spaceAfter=10, textColor=colors.black)
h2 = S(fontName="Body-Bold", fontSize=12, leading=15, spaceBefore=9, spaceAfter=4, keepWithNext=1)
cap_t = S(fontName="Body-Bold", fontSize=9.5, leading=12, spaceBefore=6, spaceAfter=3, keepWithNext=1)
cap_f = S(fontName="Body-Oblique", fontSize=9, leading=11.5, alignment=TA_CENTER, spaceBefore=3, spaceAfter=9, textColor=colors.HexColor("#333333"))
cell = S(fontSize=8.6, leading=10.8)
cellb = S(fontName="Body-Bold", fontSize=8.6, leading=10.8)
note = S(fontSize=8.8, leading=12, alignment=TA_JUSTIFY, textColor=colors.HexColor("#333333"), spaceAfter=6)
P = lambda t, st=body: Paragraph(t, st)
B = lambda t: Paragraph(t, bullet, bulletText="■")

class FigList(TableOfContents):
    def notify(self, kind, stuff):
        if kind == "FigEntry":
            super().notify("TOCEntry", stuff)


class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm, topMargin=2.2 * cm, bottomMargin=2.2 * cm,
                         title="SmartHealth AI - Project Report", author="Miman Nag, Eashan Jain")
        fr = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate("cover", [fr], onPage=lambda c, d: None, autoNextPageTemplate="main"),
                               PageTemplate("main", [fr], onPage=self.numbers)])
        self.f_n = self.t_n = 0
    def numbers(self, c, d):
        c.setFont("Body", 9); c.setFillColor(colors.HexColor("#444444")); c.drawRightString(A4[0] - 2.3 * cm, 1.2 * cm, str(d.page - 1))
    def afterFlowable(self, fl):
        if getattr(fl, "_toc", None):
            lvl, txt = fl._toc
            self.notify("TOCEntry", (lvl, txt, self.page - 1))
        if getattr(fl, "_fig", None):
            self.notify("FigEntry", (0, fl._fig, self.page - 1))

def H1(t):
    p = P(t, h1); p._toc = (0, t); return p
def H2(t): return P(t, h2)
def fig(path, w_cm, caption, h_cm=None):
    ir = ImageReader(str(path)); iw, ih = ir.getSize(); w = w_cm * cm; h = w * ih / iw
    self_n = fig.n = getattr(fig, "n", 0) + 1
    c = P(f"Figure {self_n}: {caption}", cap_f); c._fig = f"Figure {self_n}: {caption}".replace("<sub>2</sub>", "2").upper()
    return KeepTogether([Image(str(path), width=w, height=h), c])
def tbl(caption, head, rows, colw, bold_first=False, align_num=True):
    tbl.n = getattr(tbl, "n", 0) + 1
    data = [[Paragraph(str(h), cellb) for h in head]] + [[Paragraph(str(c), cellb if (bold_first and j == 0) else cell) for j, c in enumerate(r)] for r in rows]
    t = Table(data, colWidths=[w * cm for w in colw], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8ECF1")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return [KeepTogether([P(f"Table {tbl.n}: {caption}", cap_t), t]), Spacer(1, 8)] if len(rows) <= 12 else [P(f"Table {tbl.n}: {caption}", cap_t), t, Spacer(1, 8)]
pct = lambda x: f"{100 * x:.1f}%"

# =============================================================================== content
story = []
# ---- cover
logo = Image(str(A / "srm_logo.png"), width=7.2 * cm, height=7.2 * cm * 193 / 548)
story += [Spacer(1, 1.2 * cm), P("<b>SMARTHEALTH AI:<br/>A LOW-COST WEARABLE FOR ACTIVITY, FALL, TREMOR AND VITAL-SIGN MONITORING WITH DEEP LEARNING</b>", S(fontSize=15, leading=21, alignment=TA_CENTER)),
          Spacer(1, 1.2 * cm), P("<b>A PROJECT REPORT</b>", S(fontSize=11.5, alignment=TA_CENTER, leading=16)), P("<i><b>Submitted by</b></i>", S(fontSize=11, alignment=TA_CENTER, leading=16)),
          Spacer(1, .2 * cm)]
for n, r in TEAM: story.append(P(f"<b>{n} ({r})</b>", S(fontSize=11.5, alignment=TA_CENTER, leading=17)))
story += [Spacer(1, 1 * cm), P("<i>for the course</i>", S(fontSize=11, alignment=TA_CENTER, leading=16)), P(f"<b>{COURSE}</b>", S(fontSize=12, alignment=TA_CENTER, leading=17)),
          P("<i>in partial fulfillment of the requirements for the degree of</i>", S(fontSize=10.5, alignment=TA_CENTER, leading=16)), P("<b>BACHELOR OF TECHNOLOGY</b>", S(fontSize=12, alignment=TA_CENTER, leading=17)),
          Spacer(1, .9 * cm), logo, Spacer(1, 1 * cm)]
for t in ("DEPARTMENT OF DATA SCIENCE AND BUSINESS SYSTEMS", "SCHOOL OF COMPUTING", "FACULTY OF ENGINEERING AND TECHNOLOGY", "SRM INSTITUTE OF SCIENCE AND TECHNOLOGY", "KATTANKULATHUR - 603 203."):
    story.append(P(f"<b>{t}</b>", S(fontSize=9.5, alignment=TA_CENTER, leading=15)))
story.append(PageBreak())

# ---- abstract
c, l = R["selected_test"], R["other_test"]
story += [H1("Abstract"), P(
    "This report presents SmartHealth AI, an end-to-end healthcare analytics system built around a low-cost wrist-style wearable. "
    "A NodeMCU (ESP8266) board reads a 6-axis MPU-6050 motion sensor at 50 Hz and a MAX30102 pulse-oximetry sensor, and streams both to a Flask "
    "backend that turns raw motion into decisions: which activity the wearer is doing, whether a fall has happened, whether a rhythmic tremor is "
    "present, and what the heart rate and estimated SpO<sub>2</sub> are. A live dashboard shows the result and a buzzer sounds on a confirmed fall. "
    "The deep-learning core is a one-dimensional convolutional network of 11,813 parameters trained on BITS-2, a public geriatric-fall dataset "
    "recorded with the same sensor pair (41 subjects, 775 usable windows). On 114 windows from six subjects never seen in training or tuning, it reaches "
    f"{pct(c['accuracy'])} accuracy, macro-F1 {c['macro_f1']:.3f} and {pct(c['fall_recall'])} fall recall, and it beats a comparison LSTM on every measured axis while being "
    f"about {l and R['other_latency_ms'] / R['selected_latency_ms']:.0f} times faster and 4.4 times smaller. The report explains one deliberate departure from the original design: fall confirmation "
    "rests on the network's probability alone, because the acceleration rule corroborates only 54% of real falls in the data. Tremor is detected "
    "by spectral analysis rather than a trained model, since no tremor data exists in BITS-2; it is validated on ten synthetic cases and is not claimed as a clinical result. "
    "Finally, the report summarises fifteen hands-on analytics tutorials (T1 to T15) covering health records, biomedical imaging, staffing and strategic planning, clinical text, "
    "dimensionality reduction and behavioural factors in adult weight. Every figure and table is produced by the project's own code. The report concludes that the "
    "difficulty in this kind of project lies less in fitting the model than in showing that its number can be trusted, and it states plainly what has "
    "not been measured: accuracy on the prototype hardware itself.")]
story.append(PageBreak())

# ---- contents
toc = TableOfContents(); toc.levelStyles = [S(fontSize=9.5, leading=15, rightIndent=20), S(fontSize=9, leading=13), S(fontSize=8.5, leading=12.5, leftIndent=0)]
toc.dotsMinLevel = 0
story += [P("<b>Table of Contents</b>", h1), toc, PageBreak()]
story.append(P("<b>List of Figures</b>", h1)); story.append(Spacer(1, 1))
FIGLIST_MARK = len(story)  # figure list inserted after build pass (see below)
story.append(PageBreak())

# ---- 1 introduction
story += [H1("1. Introduction"), H2("1.1 Background"), P(
    "Falls are a leading cause of injury in older adults, and the danger is often not the fall itself but lying undetected afterwards. Commercial fall-alert pendants "
    "exist, but they are expensive, single-purpose and reactive. At the same time, wearables now put an inertial sensor and a pulse sensor on the wrist for a few dollars. "
    "The gap between a sensor that streams numbers and a system that can be trusted to raise an alert is a data-analytics gap: signals must be validated, segmented, "
    "classified, thresholded and explained, and each of those steps can quietly fail."),
    P("This project asks two questions at once. Can a very small neural network, running on a laptop-class backend, recognise everyday activities and detect falls from a "
      "low-cost wearable's motion stream? And can the numbers it reports be trusted? The second question drives most of the engineering. A model evaluated on a careless "
      "split reports an accuracy it cannot reproduce in service, so the guiding rule throughout is that a claim must be measured rather than asserted, and that where the data "
      "provides no ground truth, the report says so instead of inventing a number."),
    H2("1.2 Objectives"), P("The work is organised around five objectives, each of which becomes a group of sections in this report:")]
for t in ("<b>Sensing:</b> assemble a wearable prototype from a NodeMCU, an MPU-6050 and a MAX30102 and move its data to a backend over a documented protocol.",
          "<b>Data fitness:</b> establish by measurement that the training data is subject-disjoint, leakage-free and mapped to the target classes honestly.",
          "<b>Detection:</b> train and fairly compare a 1D CNN against an LSTM for activity and fall classification, and add a tremor detector.",
          "<b>Decision:</b> convert model output into a fall decision with thresholds derived from data, and test it end to end.",
          "<b>Analytics practice:</b> complete the fifteen course tutorials (T1 to T15) that cover the wider healthcare analytics syllabus."): story.append(B(t))
story += [H2("1.3 Scope and Dataset"), P(
    "The deliverable is a monitoring and classification prototype. It is <b>not</b> a certified medical device, it does not diagnose disease, and its SpO<sub>2</sub> value is an estimate. "
    "One public dataset is used for the neural network: BITS-2 (BITS Pilani K. K. Birla Goa Campus, Zenodo, doi 10.5281/zenodo.10013090), a geriatric-fall dataset recorded with a custom "
    "wrist-worn device that carries an MPU-series IMU and a MAX30102, the same sensor pair as this project's hardware. Table 1 gives the counts the code read from disk.")]
story += tbl("The dataset", ["Property", "Value"], [
    ["Source", "BITS-2, \"Inertial Measurement and Heart-Rate sensor-based dataset for Geriatric fall detection using custom built wrist-worn device\", Zenodo"],
    ["Subjects", "41 subjects; 16 daily-activity types and 8 fall types, about 5 trials each"],
    ["Files seen", "980 trial files; 205 excluded as unmappable, 775 usable windows"],
    ["Native rates", "about 20 Hz motion sensor, 1 Hz heart rate (resampled onto the 150-step model grid)"],
    ["Class balance", "Walking 246, Sitting 123, Lying 41, Running 41, Fall 324 windows (42% Fall)"]], [3.2, 12.8], bold_first=True)
story.append(P("The domain gap between BITS-2's device and the prototype of Section 3 is unmeasured (Section 10).", note))
story.append(PageBreak())

# ---- 2 system design
story += [H1("2. System Design"), H2("2.1 Pipeline Architecture"), P(
    "The system is one connected program rather than a set of isolated exercises. Data flows forward: the sensor stream arrives over USB serial (or Wi-Fi), is validated, "
    "segmented into motion events, classified, and then judged by a decision engine whose result is stored and displayed. Figure 1 shows the arrangement."),
    fig(A / "architecture.png", 15.5, "SmartHealth AI pipeline from sensors to dashboard"),
    P("Two design rules recur throughout. First, <b>the preprocessing used at training time and at inference time is the same code</b>, not an equivalent re-implementation. "
      "Second, every threshold lives in one configuration file (ml/config.py) and is derived from data or flagged as provisional."),
    H2("2.2 Components"), P(
    "The code base is about 3,500 lines of Python, JavaScript and C++ in separate layers: firmware (an Arduino sketch for the NodeMCU and a PlatformIO build for an ESP32 alternative), "
    "a Flask backend with a SQLite database, a machine-learning package (datasets, preprocessing, segmentation, CNN, LSTM, training, evaluation, inference, tremor), a dependency-free "
    "dashboard drawn on HTML canvas, and a tests folder with a simulated device, an end-to-end demo and unit checks. The Python stack is PyTorch, NumPy, pandas, scikit-learn and Flask."),
    H2("2.3 Design Constraints"), P("Four constraints shape the decisions taken, and each recurs in later sections (Table 2).")]
story += tbl("Design constraints", ["Constraint", "What it means in practice", "Design consequence"], [
    ["Team and budget", "Two students, a NodeMCU and two breakout sensors", "Small model (11.8 k parameters), CPU-only inference, no cloud"],
    ["Evidence", "No claim may rest on one favourable trace", "Subject-wise held-out test set, one honest accounting of every excluded class"],
    ["Ground truth", "BITS-2 has no standing or tremor class", "Standing is not trained; tremor is detected by signal processing and labelled as unvalidated"],
    ["Same transform", "A model sees one preprocessing at training and another live, silently", "Shared resampling and scaler code; event-triggered segmentation after a measured mismatch"]], [3, 6.2, 6.8], bold_first=True)
story += [H2("2.4 Outputs"), P("Table 3 lists what the project produces and where it lives.")]
story += tbl("Artefacts of the project", ["Artefact", "Contents"], [
    ["models/deployed_model.pt, scaler.json", "Trained 1D CNN (11,813 parameters, 52.9 KB) and the channel scaler fitted on the training subjects only"],
    ["models/training_results.json", "Every configuration tried, validation and test metrics, confusion matrices, latency"],
    ["models/threshold_experiment.json", "The fall-probability and acceleration thresholds with the experiment that produced them"],
    ["firmware/esp8266_ino, firmware/esp32", "Sketch for the NodeMCU (USB serial) and a PlatformIO Wi-Fi build for an ESP32"],
    ["tutorials/", "Tutorials T1 to T15 (scripts, figures, logs) with a one-command runner"],
    ["final/", "This report, the A3 poster and the two presentation decks, with the scripts that build them"]], [5.6, 10.4], bold_first=True)
story.append(PageBreak())

# ---- 3 sensing platform
story += [H1("3. The Sensing Platform"), H2("3.1 Hardware"), P(
    "The prototype is wired on a breadboard from three modules (Figure 2 shows them unmounted, Figure 3 shows the wired assembly): an ESP-12E NodeMCU board with an ESP8266 "
    "microcontroller, a blue breakout carrying the MPU-6050 6-axis accelerometer and gyroscope, and a green MAX30102 pulse-oximeter breakout. Both sensors share one I²C bus. "
    "The design also includes a buzzer and a push button, which are not in the photographs."),
    fig(A / "hw_parts.jpg", 12.5, "The three modules: MAX30102 (green), MPU-6050 (blue) and the ESP8266 NodeMCU (hand for scale)"),
    fig(A / "hw_wired.jpg", 12.5, "The assembled prototype on the breadboard, wired over a shared I²C bus")]
story += tbl("Hardware and pin map (NodeMCU v3, all sensors at 3.3 V)", ["Part and pin", "NodeMCU pin", "Notes"], [
    ["MPU-6050 VCC / GND", "3V3 / GND", "Never 5 V on these breakouts"],
    ["MPU-6050 and MAX30102 SDA", "D2 (GPIO4)", "Shared I²C bus; addresses 0x68 and 0x57"],
    ["MPU-6050 and MAX30102 SCL", "D1 (GPIO5)", "Shared I²C bus"],
    ["MPU-6050 AD0", "GND", "Fixes the address at 0x68"],
    ["Active buzzer +", "D5 (GPIO14)", "Use a transistor or buzzer module"],
    ["Push button", "D6 (GPIO12) to GND", "Silences the buzzer"]], [5, 3.6, 7.4], bold_first=True)
story += [H2("3.2 Firmware and Serial Protocol"), P(
    "The sketch initialises each sensor independently, so a missing sensor does not stop the other: without the MPU-6050 there is no motion data and therefore no activity, fall or tremor "
    "detection, but heart rate and SpO<sub>2</sub> still stream. It samples the IMU at a fixed 50 Hz (20 ms) to match the model, and sets the accelerometer to ±16 g, the gyroscope to "
    "±500 °/s and the digital low-pass filter to 21 Hz. Data leaves over a plain text protocol on USB at 115,200 baud (Table 5), so no Wi-Fi credentials are needed for a demonstration."),
    ]
story += tbl("Serial protocol between the board and the backend", ["Direction", "Line", "Meaning"], [
    ["board to host", "D,ax,ay,az,gx,gy,gz,hr,spo2", "One line per 50 Hz sample (m/s², rad/s, bpm, %); hr and spo2 are -1 when unknown"],
    ["board to host", "V,hr,spo2", "1 Hz, only while the MPU-6050 is missing (vitals-only mode)"],
    ["board to host", "# sensors imu=1 vitals=0", "Which sensors are alive, on change and every 5 s"],
    ["host to board", "B", "Confirmed fall: sound the buzzer for 3 s (button mutes for 10 s)"]], [2.6, 5.2, 8.2], bold_first=True)
story += [P(
    "On the host, <font face='Courier'>backend/services/serial_bridge.py</font> parses these lines and feeds exactly the same ingestion function as the Wi-Fi route, so the dashboard behaves identically "
    "over either transport. <font face='Courier'>tests/test_serial_bridge.py</font> verifies the bridge by emulating the board on a pseudo-terminal: 83 samples were ingested and the buzzer command was "
    "seen by the emulated board, and vitals-only, IMU-only and no-sensor modes behaved correctly. An ESP32 Wi-Fi build (HTTP POST of the JSON payload in Appendix A) also compiles against the real "
    "toolchain but is not what the photographed prototype runs."),
    H2("3.3 What Has and Has Not Been Verified"), P(
    "The hardware is assembled and the serial path is verified against an emulated board. What has <b>not</b> been measured is the network's accuracy on this specific "
    "MPU-6050 and MAX30102 unit: every accuracy figure in this report comes from the public BITS-2 recordings. Closing that gap needs labelled recordings from the prototype itself, "
    "which the logger firmware is written to collect.")]
story.append(PageBreak())

# ---- 4 data quality
story += [H1("4. Data Preparation and Quality"), H2("4.1 Mapping the Dataset to Target Classes"), P(
    "BITS-2's activities do not map perfectly to the classes the application needs. Table 6 shows what mapped cleanly. Activities with no honest match were excluded rather than force-labelled: "
    "205 trials of 980 (jumping, swinging hands and three lying-transition types, 41 each).")]
story += tbl("Dataset activities mapped to application classes", ["BITS-2 activity", "Class", "Windows"], [
    ["Walking slowly/quickly; climbing up/down stairs (slow, normal)", "Walking", "246"],
    ["Slowly/rapidly sitting down; nearly sitting and getting up", "Sitting", "123"],
    ["Jogging", "Running", "41"],
    ["Lying on bed", "Lying", "41"],
    ["All 8 fall types", "Fall", "324"],
    ["Jumping; swinging hands; 3 lying-transition activities", "excluded", "0 (205 trials dropped)"],
    ["(no static standing activity exists; no tremor activity exists)", "not trained", "-"]], [9, 3, 4], bold_first=False)
story += [H2("4.2 Subject-wise Split and Leakage Prevention"), P(
    "The data is split by <b>subject</b>, seed 42, in a 70/15/15 ratio, so no person appears in more than one split. Per-channel z-score statistics are fitted on the training subjects only. "
    "Thresholds are tuned on validation and never on test. The correct order is: split subjects, fit preprocessing on training data, apply to validation and test, then train and evaluate.")]
story += tbl("Subject-wise split", ["Split", "Subjects", "Windows", "Subject ids"], [
    ["train", "29", "547 (1,641 after augmentation)", "1, 4, 5, 6, 7, 8, 10, 11, 12, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 36, 38, 39, 41"],
    ["validation", "6", "114", "13, 15, 16, 18, 35, 40"],
    ["test", "6", "114 (Walking 36, Running 6, Sitting 18, Lying 6, Fall 48)", "2, 3, 9, 14, 34, 37"]], [2.2, 1.8, 4.5, 7.5], bold_first=True)
story += [H2("4.3 Preprocessing"), P(
    "Each trial is resampled onto a fixed 150-step grid with six channels (three accelerometer, three gyroscope), then normalised with the training-set scaler. Training windows are augmented with two "
    "extra jittered and scaled copies of the real recorded windows; the augmentation is applied to the training set only. Because BITS-2 trials are short discrete recordings (about 1 to 3 s) "
    "at a native 20 Hz, the resampling grid, rather than a sliding window, is the training transform. That choice has a consequence for live inference, described in Section 6.")]
story.append(PageBreak())

# ---- 5 models
story += [H1("5. Deep Learning Models"), H2("5.1 The Two Architectures"), P(
    "The primary model is a 1D CNN: Conv1D, batch normalisation, ReLU and max-pooling twice, then global average pooling, dropout and a softmax layer over five classes "
    "(Walking, Running, Sitting, Lying, Fall). The deployed configuration uses 32 and 64 filters, kernel size 5 and dropout 0.3: <b>11,813 parameters, 52.9 KB on disk</b>. "
    "The comparison model is a two-layer LSTM with 64 hidden units and dropout 0.4 on the same 150 × 6 input (52,037 parameters). Both are trained with Adam, a reduce-on-plateau "
    "learning rate and early stopping on validation macro-F1."),
    H2("5.2 Model Selection"), P("Six CNN configurations and four LSTM configurations were trained. Selection used validation macro-F1 with fall recall weighted first. The held-out test set was evaluated once, for the winner of each architecture (Figure 4).")]
runs = R["all_val_runs"]
rows = []
for r in runs:
    cfg = r["config"]; desc = (f"filters {tuple(cfg['filters'])}, k={cfg['kernel_size']}, dropout {cfg['dropout']}" if r["model_name"] == "CNN" else f"hidden {cfg['hidden_size']}, layers {cfg['num_layers']}, dropout {cfg['dropout']}")
    rows.append([r["model_name"], desc, f"{r['params']:,}", f"{r['val_accuracy']:.3f}", f"{r['val_macro_f1']:.3f}", f"{r['val_fall_recall']:.3f}", r["epochs_trained"]])
story += [fig(A / "val_sweep.png", 11.5, "Validation macro-F1 of every configuration tried")]
story += tbl("All ten configurations on the validation set", ["Model", "Configuration", "Params", "Val acc", "Val macro-F1", "Val fall recall", "Epochs"], rows, [1.4, 6.2, 1.8, 1.6, 2.0, 2.0, 1.4])
story += [H2("5.3 Test Results"), P(
    f"On the 114 held-out windows from six unseen subjects the selected CNN reaches <b>{pct(c['accuracy'])} accuracy, macro-F1 {c['macro_f1']:.3f} and fall recall {pct(c['fall_recall'])}</b>. "
    f"It beats the LSTM on accuracy, macro-F1 and fall recall, runs in {R['selected_latency_ms']:.3f} ms per window against {R['other_latency_ms']:.3f} ms (about {R['other_latency_ms'] / R['selected_latency_ms']:.0f} times faster) "
    "and has 4.4 times fewer parameters. It is a clean win rather than a precision-recall trade-off. A plausible reason is that the training set is small (547 base windows) and each window is a whole "
    "resampled trial rather than a long natural sequence, which favours the CNN's local-pattern bias over the LSTM's need for more sequence data."),
    fig(A / "cnn_vs_lstm.png", 14.5, "CNN against LSTM on the held-out test set, with CPU latency")]
story += tbl("Held-out test results", ["Model", "Accuracy", "Macro-F1", "Fall recall", "Latency (CPU)", "Parameters", "Size"], [
    ["1D CNN (deployed)", f"{c['accuracy']:.3f}", f"{c['macro_f1']:.3f}", f"{c['fall_recall']:.3f}", f"{R['selected_latency_ms']:.3f} ms", f"{R['selected_params']:,}", "52.9 KB"],
    ["LSTM (comparison)", f"{l['accuracy']:.3f}", f"{l['macro_f1']:.3f}", f"{l['fall_recall']:.3f}", f"{R['other_latency_ms']:.3f} ms", f"{R['other_params']:,}", "about 209 KB"]], [3.4, 1.8, 1.9, 1.9, 2.6, 2.2, 2.2], bold_first=True)
story += [fig(A / "confusion.png", 8.3, "Confusion matrix of the CNN on the test set"),
          P("Fall is the strongest class (precision 0.956, recall 0.896, F1 0.925), which matters because it is the safety-critical one. Of the 48 test falls, 43 are caught; the five misses are "
            "split between Sitting (2) and Lying (3), the two quiet classes a soft fall can resemble. Walking is confused with Sitting 6 times. Running and Lying have only 6 test windows each, so their "
            "scores are indicative only.")]
story += tbl("Per-class test scores of the CNN", ["Class", "Precision", "Recall", "F1", "Test windows"], [
    [k, f"{c['per_class_precision'][i]:.3f}", f"{c['per_class_recall'][i]:.3f}", f"{c['per_class_f1'][i]:.3f}", n] for i, (k, n) in enumerate(zip(["Walking", "Running", "Sitting", "Lying", "Fall"], [36, 6, 18, 6, 48]))], [3.5, 3, 3, 3, 3.5], bold_first=True)
story.append(P("<b>Caveat.</b> A test set of 114 windows from six subjects carries wide confidence intervals. Read \"85.1%\" as \"this model on this specific held-out set\", not as a general claim.", note))
story.append(PageBreak())

# ---- 6 fall detection
story += [H1("6. Fall Detection and the Decision Engine"), H2("6.1 Event-Triggered Segmentation"), P(
    "The first live design fed the model a rolling 3-second window. Live testing showed it was a different transform from training: a real fall trial that scored above 80% fall probability "
    "offline scored 14% live, and was labelled Lying. The cause was a silent mismatch, since the training data is whole resampled trials. The fix was event-triggered segmentation: onset is declared when "
    "|acceleration magnitude - 9.8| exceeds 2.0 m/s², raw samples are accumulated until ten consecutive near-rest samples (or a 200-sample cap), and the captured segment is resampled to 150 × 6 "
    "with the <i>same function</i> used in training. After the change, live and offline results agreed. This produces exactly one classification per physical motion event, so debouncing is per event, not "
    "per overlapping window."),
    H2("6.2 Two-Stage Decision, and a Deliberate Deviation"), P(
    "The original design confirmed a fall only if the AI said Fall <i>and</i> a rule check agreed (peak acceleration above a threshold, then post-event stillness). The rule was measured against the data: "
    "only <b>54%</b> of real BITS-2 fall trials exceed the acceleration threshold, because many are controlled falls onto a bed that never spike the accelerometer. Requiring the rule would have roughly halved "
    "fall recall with no precision gain the data supports, since the tuned AI threshold alone reaches precision 1.00 on validation. The decision engine therefore confirms on the AI probability alone and "
    "attaches the rule signals to every alert for explanation and audit. This is a recall-over-precision choice and it has a measured cost, shown in Section 6.4.")]
story += tbl("Thresholds and how each was derived", ["Threshold", "Value", "Derivation"], [
    ["FALL_PROBABILITY_THRESHOLD", f"{TH['FALL_PROBABILITY_THRESHOLD']:.3f}", "Precision-recall sweep on the validation set; highest-precision point with recall at least 0.90 (precision 1.00, recall 0.917)"],
    ["ACCELERATION_THRESHOLD", f"{TH['ACCELERATION_THRESHOLD']:.2f} m/s²", "95th percentile of peak acceleration across non-fall activity trials; corroborates only 54% of falls, so logged, not gating"],
    ["POST_FALL_INACTIVITY_SECONDS", "1.5 s", "<b>Provisional</b>, not derived: BITS-2 trials are trimmed to 1 to 3 s and hold no real post-fall settling period (measured within-trial run 0.01 s)"]], [5, 2.6, 8.4], bold_first=True)
story += [H2("6.3 Alert Logic"), P(
    "A confirmed fall writes a critical alert, returns <font face='Courier'>\"buzzer\": true</font> to the device and flips the dashboard to an alert state. While an alert is active for a device, "
    "a new critical alert is not inserted until the model stops flagging a fall candidate: a cooldown, not a debounce by repetition. The push button silences the buzzer locally.")]
story += [H2("6.4 End-to-End Scenarios"), P("Four scenarios were run through the full pipeline (backend, segmentation, CNN, decision engine, database) using trials from the six held-out test subjects.")]
story += tbl("End-to-end scenarios on held-out subjects", ["Scenario", "Subject", "Result", "Verdict"], [
    ["Walking (walking slowly)", "2", "Walking, confidence 89%, P(fall) 9%", "Pass"],
    ["Sitting (slowly sitting on chair)", "3", "Sitting, confidence 82%, P(fall) 5%", "Pass"],
    ["Running (jogging)", "9", "Running, confidence 100% on the steady segment; an earlier short onset burst was labelled Fall at 52% and raised a real false alert", "Pass, with a documented false positive"],
    ["Safe simulated fall (forward fall)", "14", "Fall, confidence 50%, confirmed_fall true, buzzer flag returned; motion_verified false (low acceleration peak)", "Pass"],
    ["Tremor-like movement", "-", "Not part of this run: tremor is detected by a separate signal-processing module (Section 7)", "See Section 7"]], [4.4, 1.6, 7.2, 2.8], bold_first=True)
story.append(P("The false positive in the Running scenario is a direct consequence of the recall-over-precision choice combined with algorithmic (not human-curated) segmentation: a short, ambiguous burst at the "
               "start of movement can cross the threshold. It is reported, not hidden. Collecting labelled transition-onset examples from the prototype is the proper fix; an ad hoc threshold tweak would need full re-validation."))
story.append(PageBreak())

# ---- 7 tremor
story += [H1("7. Tremor Detection"), H2("7.1 Why Signal Processing, Not a Network"), P(
    "BITS-2 contains no tremor activity, so a trained tremor class would have no honest labels. Rest and postural tremor is a rhythmic oscillation, roughly 3 to 8 Hz (Parkinsonian rest tremor is typically "
    "4 to 6 Hz), which makes it a good fit for spectral analysis. The module is therefore a detector built on physics and validated on controlled synthetic signals. It reports only a "
    "\"tremor-like movement pattern\" and never a disease name.")
    , H2("7.2 Method"), P(
    "A rolling 3-second window of accelerometer samples is kept per device. Every 0.5 s the detector removes the mean (gravity and posture), applies a Hann window and computes the FFT. It then measures (i) the RMS amplitude in "
    "the 3 to 8 Hz band, (ii) the share of total 0.5 to 15 Hz energy in that band, (iii) how sharp a spectral peak sits in the band compared with the median power (rhythmic, not broadband noise), and (iv) how large slow voluntary "
    "motion (0.5 to 2.5 Hz) is relative to the tremor. Walking and running are rejected because their low-frequency motion dominates; stillness is rejected by the minimum amplitude. Three consecutive positive evaluations "
    "(1.5 s) switch tremor on and four negatives (2 s) switch it off, which stops flicker. The real sample rate is estimated from arrival times, so the reported frequency stays right if the stream runs slow.")]
story += tbl("Tremor detector parameters (ml/config.py)", ["Parameter", "Value", "Meaning"], [
    ["TREMOR_BAND_HZ", "3.0 to 8.0 Hz", "Band searched for the tremor peak"],
    ["TREMOR_MIN_RMS", "0.15 m/s²", "Below this the band is sensor noise"],
    ["TREMOR_MIN_BAND_RATIO", "0.45", "Band power as a share of total 0.5 to 15 Hz power"],
    ["TREMOR_MIN_PEAK_RATIO", "4.0", "Peak power over median power: rhythmic, not broadband"],
    ["TREMOR_MAX_LOW_TO_BAND_RMS", "2.0", "Slow voluntary motion may be at most twice the tremor amplitude"],
    ["TREMOR_ON_EVALS / OFF_EVALS", "3 / 4", "Debounce: 1.5 s to switch on, 2 s to switch off"]], [5.6, 3.4, 7], bold_first=True)
import json as _j
cases = _j.load(open(A / "tremor_cases.json"))
rows = [[n, "tremor" if e else "no tremor", "tremor" if g else "no tremor", f"{d['freq_hz']:.1f}", f"{d['amplitude']:.2f}", f"{d['band_ratio']:.2f}", "PASS" if e == g else "FAIL"] for n, e, g, d in cases]
story += [H2("7.3 Validation on Synthetic Signals"), P(
    "tests/test_tremor.py generates ten 8-second signals at 50 Hz with gravity on one axis and sensor noise on all three, and checks that the detector fires only when it should. All ten pass (Table 14). "
    "Figure 7 shows why: a 5 Hz tremor gives one sharp peak inside the band, walking puts its energy at 1.9 Hz and its harmonics, and rest is flat noise."),
    fig(A / "tremor_spectra.png", 15.5, "Spectra of rest, a 5 Hz tremor and walking, with the 3 to 8 Hz band shaded")]
story += tbl("Ten synthetic cases: detector output and last-window measurements", ["Signal", "Expected", "Detected", "Peak (Hz)", "Band RMS (m/s²)", "Band ratio", "Test"], rows, [4.5, 1.9, 1.9, 1.4, 2.2, 1.6, 1.6], bold_first=True)
story.append(P("<b>Limit.</b> These are simulated signals. The thresholds are starting values chosen for a clear margin on them. They must be verified against a real tremor or a deliberate 5 Hz hand shake "
               "recorded on the prototype before any claim is made, and adjusted in ml/config.py, not inside the detector.", note))
story.append(PageBreak())

# ---- 8 backend dashboard
story += [H1("8. Backend, Database and Dashboard"), H2("8.1 API"), P(
    "The Flask backend validates every payload and rejects malformed ones with HTTP 400 and a specific message: missing device_id, missing or wrong-typed imu fields, non-object bodies and non-JSON bodies. "
    "Real requests confirmed each rejection. Two real bugs were found this way and fixed: a missing tremor_probability key in the live prediction, and dashboard assets returning 404 because Flask's default static route shadowed the custom one.")]
story += tbl("Endpoints", ["Endpoint", "Purpose"], [
    ["POST /api/sensor-data", "Validate, store, run segmentation, CNN and decision engine (Wi-Fi path)"],
    ["GET /api/latest, /api/activity, /api/vitals", "Latest reading, activity with confidence and fall probability, heart rate and SpO<sub>2</sub>"],
    ["GET /api/tremor", "Live tremor state: warming up, none, detected (frequency, amplitude, band ratio) or no data"],
    ["GET /api/alerts, /api/history", "Recent alerts; recent readings, predictions and alerts"],
    ["GET /api/health", "Liveness check"],
    ["GET /api/serial/ports, /status; POST /api/serial/connect, /disconnect", "List ports, show bridge state, connect or disconnect the USB board from the dashboard"]], [6.8, 9.2], bold_first=True)
story += tbl("SQLite schema (device_id and an index on device_id, timestamp on every table)", ["Table", "Columns"], [
    ["sensor_readings", "id, device_id, timestamp, ax, ay, az, gx, gy, gz, heart_rate, spo2"],
    ["predictions", "id, device_id, timestamp, activity, confidence, fall_probability, tremor_probability, model_name"],
    ["alerts", "id, device_id, timestamp, alert_type, severity, status, message"]], [3.6, 12.4], bold_first=True)
story += [H2("8.2 Dashboard"), P(
    "The dashboard is a mobile-first, config-driven page of plain HTML, CSS and JavaScript with hand-drawn canvas traces. The hero waveform is the actual acceleration magnitude the model classifies. "
    "Cards show heart rate, SpO<sub>2</sub>, current activity, fall status and tremor status; a top bar lists serial ports and connects the board. It polls the backend every two seconds. The screenshots below are from real runs against the live backend with the trained model."),
    fig(ROOT / "docs" / "screenshots" / "dashboard-desktop.png", 13.5, "Dashboard, calm state: Walking, 82 bpm, 97% SpO<sub>2</sub> and the live acceleration trace"),
    fig(ROOT / "docs" / "screenshots" / "dashboard-alert.png", 13.5, "Dashboard during a confirmed fall alert, with the event in the log"),
    fig(ROOT / "docs" / "screenshots" / "dashboard-mobile.png", 4.6, "Mobile layout (single column)")]
story.append(PageBreak())

# ---- 9 tutorials
story += [H1("9. Coursework Tutorials T1 to T15"), P(
    "The course syllabus also requires hands-on tutorials across five units. All fifteen are in the tutorials folder, each a self-contained, fixed-seed script that prints its results, saves figures and ends "
    "with assert-based checks. A single command (python tutorials/run_all.py) runs all of them; all pass. SmartHealth AI itself uses no health-record or imaging data, so the tutorials use synthetic data "
    "or built-in sample data, stated for each below. Only T13 uses a real dataset.")]
rows = [
    ["T1", "Understanding EHR: structure, ICD-10 coding, barriers", "Synthetic EHR, 410 records, 13 fields; up to 15% missing per field; 8 spellings of gender"],
    ["T2", "Standardisation and cleaning", "8 gender labels to 2; 42 Fahrenheit readings corrected; 27 impossible SpO<sub>2</sub> values flagged"],
    ["T3", "Redundant data and missing data", "30 duplicates removed; listwise deletion plus median, mode and KNN imputation; missingness 15% to 0%"],
    ["T4", "Image enhancement, restoration, segmentation, compression", "CLAHE; denoising PSNR 20.1 to 25.3 dB; Otsu mask 3.2% of pixels; JPEG 5.2 KB (q10) to 23.8 KB (q90)"],
    ["T5", "SIFT, RANSAC, CNN", "13 of 14 matches kept as inliers, rotation 12.0° recovered as 11.9°; toy CNN 56.7% on 30 held-out patches (weak, reported as is)"],
    ["T6", "Biomedical image visualisation", "Side-by-side panels, histograms and boundary overlay for the T4 and T5 results"],
    ["T7", "Patient prediction for improved staffing", f"7-day-ahead ED arrivals: MAE {T7['models']['linear (calendar + Fourier)']['MAE']:.1f} against {T7['models']['seasonal naive (t-7)']['MAE']:.1f} seasonal-naive; forecast roster with buffer cost {T7['staffing']['forecast + 40-patient buffer']['cost']:.0f} against {T7['staffing']['flat roster (train mean)']['cost']:.0f} for a flat one"],
    ["T8", "Strategic planning I: descriptive", f"Service-line scorecard; {T8['occupancy_2024_pct']:.1f}% occupancy of 420 beds; orthopaedics earns most per bed-day"],
    ["T9", "Strategic planning II: predictive, prescriptive", f"Base case needs {T9['beds_needed']['base'][2]} beds in 2027 against 420; the LP bed allocation adds {T9['lp_gain_m']:.1f} M margin over equal cuts; a bed-day is worth about {T9['shadow_price_per_bed_day']:,.0f}"],
    ["T10", "Classification and clustering of clinical text", f"TF-IDF + linear SVM {pct(T10['models']['Linear SVM']['test_acc'])} test accuracy; k-means ARI {T10['ari_all_words']:.2f} on all words but {T10['ari']:.2f} once boilerplate is removed"],
    ["T11", "Information extraction and NER", f"Regex blood-pressure accuracy {T11['regex_v1']['bp']:.3f} to 1.000 after fixing the \"over\" format; a tagger without a lexicon finds 100% of unseen drugs, a lexicon-fed one 0%"],
    ["T12", "Ranking and word-sense disambiguation", f"BM25 P@10 {T12['ranking']['BM25']['P@10']:.2f} against {T12['ranking']['TF-IDF cosine']['P@10']:.2f} for TF-IDF; WSD {T12['wsd']['Naive Bayes (5-fold CV)']:.2f} against {T12['wsd']['most frequent sense']:.2f} for most-frequent-sense"],
    ["T13", "Dimensionality reduction (real breast-cancer data)", f"{T13['k90']} components keep 90% of variance, {T13['k95']} keep 95%; 10 components match all 30 features ({pct(T13['acc_full'])})"],
    ["T14", "Behavioural factors in adult weight I", f"Physical activity explains the most BMI variance (eta-squared {T14['factors'][0]['eta2']:.2f}); {T14['n_significant']} of 13 factors significant after Benjamini-Hochberg correction"],
    ["T15", "Behavioural factors in adult weight II", f"Height and weight leak the class ({pct(T15['acc_leaky'])}) against {pct(T15['acc_behaviour_only'])} from behaviour alone; boosting R² {T15['r2']['Gradient boosting']:.2f} against OLS {T15['r2']['OLS (linear)']:.2f}"]]
story += tbl("Tutorial summary (numbers from tutorials/logs)", ["", "Topic", "Key result"], rows, [1.1, 5.2, 9.7], bold_first=True)
story += [H2("9.1 Lessons that Transfer to This Project"), B("<b>T3 and T15 (leakage and missingness):</b> the same discipline as the subject-wise split here; a feature that defines the label gives an impressive and useless score."),
          B("<b>T7 and T9 (forecast and cost):</b> a forecast is only useful once converted into a decision and costed against a simple baseline."),
          B("<b>T10 and T11 (text):</b> boilerplate dominated clustering until removed, and a lexicon feature acted as a shortcut that hurt generalisation: both are the kind of silent failure this project guards against."),
          B("<b>T13 (dimensionality):</b> 30 correlated features compress to about 10 with no loss, the reasoning behind keeping the CNN small."),
          fig(TUT / "unit3_staffing_planning" / "outputs" / "t9_projection.png", 10.5, "T9: projected bed demand against 420 licensed beds, with 80% scenario band"),
          fig(TUT / "unit5_dimensionality_behavioral" / "outputs" / "t13_embeddings.png", 15.5, "T13: PCA, LDA, t-SNE and Isomap maps of the breast-cancer data")]
story.append(PageBreak())

# ---- 10 results
story += [H1("10. Results, Evaluation and Limitations"), H2("10.1 Summary of Results"), P("Table 18 gathers the headline numbers, each traceable to a run.")]
story += tbl("Headline results", ["Item", "Result", "Source"], [
    ["Deployed CNN, test", f"{pct(c['accuracy'])} accuracy, macro-F1 {c['macro_f1']:.3f}, fall recall {pct(c['fall_recall'])}", "ml/training/train.py, models/training_results.json"],
    ["Fall precision, recall, F1", "0.956, 0.896, 0.925", "same"],
    ["CNN against LSTM", f"{R['selected_latency_ms']:.3f} against {R['other_latency_ms']:.3f} ms; 11,813 against 52,037 parameters", "same"],
    ["Fall threshold (validation)", f"{TH['FALL_PROBABILITY_THRESHOLD']:.3f}: precision 1.00, recall 0.917", "ml/evaluation/threshold_analysis.py"],
    ["Rule corroboration of falls", "54% of real falls exceed the acceleration threshold", "same"],
    ["End-to-end scenarios", "4 of 4 runnable scenarios pass on unseen subjects", "tests/e2e_demo.py"],
    ["Tremor detector", "10 of 10 synthetic cases correct", "tests/test_tremor.py"],
    ["Serial bridge", "83 samples ingested via emulated board; buzzer command seen", "tests/test_serial_bridge.py"],
    ["Tutorials", "15 of 15 pass their self-checks", "tutorials/run_all.py"]], [4.2, 7.2, 4.6], bold_first=True)
story += [H2("10.2 Known Limitations"), P("Table 19 lists the limitations found while building and testing, in order of importance. None has been hidden or tuned away.")]
story += tbl("Limitations", ["#", "Limitation", "Consequence and next step"], [
    ["1", "Accuracy on the prototype hardware is unmeasured", "Model trained on BITS-2's MPU-series device; the MPU-6050 and MAX30102 unit differs. Record labelled trials on the prototype and measure the domain gap"],
    ["2", "Small test set", "114 windows, 6 subjects; Running and Lying have 6 windows each. Treat percentages as indicative"],
    ["3", "Standing is not trained", "BITS-2 has no static standing activity. Collect it on the prototype"],
    ["4", "Tremor is validated only on synthetic signals", "Thresholds are starting values; verify with a real or deliberate 5 Hz tremor before any claim"],
    ["5", "Post-fall inactivity period is provisional", "1.5 s is a placeholder; BITS-2 trials are too short to measure it. Re-validate on continuous recordings"],
    ["6", "Recall-over-precision false positive", "A short onset burst was labelled Fall at 52%. Needs labelled transition-onset data, then full re-validation"],
    ["7", "SpO<sub>2</sub> is a simplified estimate", "Uses SpO<sub>2</sub> = 110 - 25R, not the clinical lookup-table algorithm; not a medical reading"],
    ["8", "Tutorials use synthetic data (except T13)", "Near-perfect text scores (T10 to T12) are a ceiling effect of templated notes, not a real-world claim"]], [0.8, 5.2, 10], bold_first=False)
story += [H2("10.3 Discussion"), P(
    "Three decisions matter more than the architecture. Splitting by subject made the evaluation honest, and a random window split would have let the same person's recordings appear on both sides. Finding the segmentation mismatch with a "
    "live test, not by inspection, kept training and inference on the same transform. And measuring that the acceleration rule corroborates only 54% of falls turned a design assumption into a data-backed deviation. Each of these cost accuracy "
    "on paper or added work, and each is what makes the headline number believable.")]
story.append(PageBreak())

# ---- 11 conclusion
story += [H1("11. Conclusion"), P(
    "SmartHealth AI shows that a very small network can classify activity and detect falls from a low-cost wearable's motion stream, and that the surrounding system (segmentation, decision engine, backend, dashboard, tremor module) "
    "can be built and tested end to end with a clear account of what each part does and does not claim. The deployed 1D CNN, with 11,813 parameters, reaches 85.1% accuracy and 89.6% fall recall on subjects it never saw, "
    "and does so faster and smaller than the LSTM it was compared with. The system's value does not depend on the percentage alone: every number is traceable to a run, every threshold to an experiment or a provisional flag, "
    "and every limitation is written down."),
    H2("11.1 Future Work"), B("Record labelled trials on the assembled prototype to measure the sensor domain gap, add the Standing class and train a real tremor class (or validate the spectral detector against recorded tremor)."),
    B("Collect continuous recordings to derive the post-fall inactivity period and to teach the model to separate movement-onset bursts from falls, which would remove the documented false positive."),
    B("Replace the simplified SpO<sub>2</sub> estimate with the reference algorithm and evaluate it against a reference oximeter."),
    B("Optional extensions already scoped out of the core build: BLE, a mobile app, notifications and on-device inference.")]
story.append(PageBreak())

# ---- references
story += [H1("12. References"), ]
refs = ["BITS-2 dataset: Inertial Measurement and Heart-Rate sensor-based dataset for Geriatric fall detection using custom built wrist-worn device. BITS Pilani K. K. Birla Goa Campus. Zenodo, doi:10.5281/zenodo.10013090.",
        "Kingma, D. P. and Ba, J. (2015). Adam: a method for stochastic optimization. International Conference on Learning Representations (arXiv:1412.6980).",
        "Ioffe, S. and Szegedy, C. (2015). Batch normalization: accelerating deep network training by reducing internal covariate shift. ICML.",
        "Hochreiter, S. and Schmidhuber, J. (1997). Long short-term memory. Neural Computation, 9(8), 1735-1780.",
        "Paszke, A. et al. (2019). PyTorch: an imperative style, high-performance deep learning library. NeurIPS.",
        "Pedregosa, F. et al. (2011). Scikit-learn: machine learning in Python. Journal of Machine Learning Research, 12, 2825-2830.",
        "Deuschl, G. et al. (1998). Consensus statement of the Movement Disorder Society on tremor. Movement Disorders, 13(Suppl 3), 2-23.",
        "InvenSense. MPU-6000 and MPU-6050 product specification, rev 3.4. Maxim Integrated. MAX30102 high-sensitivity pulse oximeter and heart-rate sensor, datasheet.",
        "Benjamini, Y. and Hochberg, Y. (1995). Controlling the false discovery rate. Journal of the Royal Statistical Society B, 57(1), 289-300.",
        "Robertson, S. and Zaragoza, H. (2009). The probabilistic relevance framework: BM25 and beyond. Foundations and Trends in Information Retrieval, 3(4), 333-389.",
        "Mihalcea, R. and Tarau, P. (2004). TextRank: bringing order into text. EMNLP.",
        "van der Maaten, L. and Hinton, G. (2008). Visualizing data using t-SNE. Journal of Machine Learning Research, 9, 2579-2605.",
        "Lowe, D. G. (2004). Distinctive image features from scale-invariant keypoints. International Journal of Computer Vision, 60(2), 91-110.",
        "Fischler, M. A. and Bolles, R. C. (1981). Random sample consensus. Communications of the ACM, 24(6), 381-395.",
        "Street, W. N., Wolberg, W. H. and Mangasarian, O. L. (1993). Nuclear feature extraction for breast tumor diagnosis (Wisconsin diagnostic breast cancer data, distributed with scikit-learn)."]
for i, r in enumerate(refs, 1): story.append(Paragraph(r, S(fontSize=9.5, leading=13, leftIndent=22, firstLineIndent=-22, spaceAfter=4), bulletText=None) if False else Paragraph(f"[{i}] {r}", S(fontSize=9.5, leading=13, leftIndent=24, firstLineIndent=-24, spaceAfter=4)))
story.append(PageBreak())

# ---- appendices
story += [H1("13. Appendices"), H2("Appendix A: Device payload (Wi-Fi path)"), P("The ESP32 build posts this JSON; the USB path produces the same structure from the serial lines in Table 5. imu fields are required and type-checked; vitals is optional."),
          P("<font face='Courier' size='8.5'>{ \"device_id\": \"wearable_01\", \"timestamp\": 1750000000,<br/>&nbsp;&nbsp;\"imu\": { \"ax\": 0.12, \"ay\": 0.45, \"az\": 0.98, \"gx\": 2.1, \"gy\": 1.3, \"gz\": 0.4 },<br/>&nbsp;&nbsp;\"vitals\": { \"heart_rate\": 78, \"spo2\": 97 } }</font>", S(fontSize=9, leading=13, leftIndent=14)),
          H2("Appendix B: Key configuration values (ml/config.py)")]
story += tbl("Central configuration", ["Key", "Value"], [
    ["IMU_SAMPLE_RATE", "50 Hz"], ["Model input", "150 timesteps x 6 channels (ax, ay, az, gx, gy, gz)"], ["Event onset", "|accel magnitude - 9.8| > 2.0 m/s²"],
    ["Event offset", "10 consecutive near-rest samples, hard cap 200 samples, minimum 4"], ["FALL_PROBABILITY_THRESHOLD", f"{TH['FALL_PROBABILITY_THRESHOLD']:.3f}"],
    ["ACCELERATION_THRESHOLD", f"{TH['ACCELERATION_THRESHOLD']:.2f} m/s²"], ["POST_FALL_INACTIVITY_SECONDS", "1.5 s (provisional)"], ["Tremor band / window / hop", "3 to 8 Hz / 3 s / 0.5 s"]], [6, 10], bold_first=True)
story += [H2("Appendix C: Reproducing the results"), P("<font face='Courier' size='8.5'>python -m venv venv &amp;&amp; source venv/bin/activate &amp;&amp; pip install -r requirements.txt<br/>python -m backend.app &nbsp;&nbsp;# http://localhost:5000<br/>python -m ml.training.train &nbsp;&nbsp;# retrain and write models/training_results.json<br/>python -m tests.e2e_demo &nbsp;&nbsp;# four end-to-end scenarios<br/>python -m tests.test_tremor &nbsp;&nbsp;# tremor detector checks<br/>python tutorials/run_all.py &nbsp;&nbsp;# tutorials T1 to T15<br/>python final/build/build_all.py &nbsp;&nbsp;# rebuild this report, poster and decks</font>", S(fontSize=9, leading=13, leftIndent=14)),
          H2("Appendix D: Repository layout"), P("<font face='Courier' size='8.5'>firmware/ (esp8266_ino, esp32) &nbsp; backend/ (routes, services, database) &nbsp; ml/ (datasets, preprocessing, segmentation, cnn, lstm, training, evaluation, inference)<br/>dashboard/ &nbsp; models/ &nbsp; data/ &nbsp; tests/ &nbsp; tutorials/ (unit1 to unit5, run_all.py) &nbsp; docs/ &nbsp; final/ (report, poster, decks)</font>", S(fontSize=9, leading=13, leftIndent=14))]

def build(fn):
    # pass 1 builds the TOC; the list of figures is a second TableOfContents fed by level-2 entries
    fl_toc = FigList(); fl_toc.levelStyles = [S(fontSize=9, leading=13), S(fontSize=9, leading=13), S(fontSize=8.5, leading=13)]
    fl_toc.dotsMinLevel = 0
    st = list(story)
    st.insert(FIGLIST_MARK, fl_toc)
    # level-2 entries go to the figure list only: give the main TOC its own handler
    d = Doc(fn)
    d.multiBuild(st)

if __name__ == "__main__":
    build(str(OUT / "SmartHealth_AI_Project_Report.pdf"))
    print("report built")
