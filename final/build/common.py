import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "final" / "assets"
OUT = ROOT / "final"
TEAM = [("MIMAN NAG", "RA2311027010190"), ("EASHAN JAIN", "RA2311027010198")]
COURSE = "21CSE428T HEALTHCARE ANALYTICS"
TITLE = "SmartHealth AI"
SUBTITLE = "A Low-Cost Wearable for Activity, Fall, Tremor and Vital-Sign Monitoring with Deep Learning"
NAVY, TEAL, CORAL, GOLD = "#0B2A4A", "#0E8C8C", "#E4572E", "#F2A93B"
R = json.load(open(ROOT / "models" / "training_results.json"))
TH = json.load(open(ROOT / "models" / "threshold_experiment.json"))
TUT = ROOT / "tutorials"
def tj(unit, name):
    return json.load(open(TUT / unit / "outputs" / name))
T7 = tj("unit3_staffing_planning", "t7_results.json"); T8 = tj("unit3_staffing_planning", "t8_results.json"); T9 = tj("unit3_staffing_planning", "t9_results.json")
T10 = tj("unit4_clinical_text", "t10_results.json"); T11 = tj("unit4_clinical_text", "t11_results.json"); T12 = tj("unit4_clinical_text", "t12_results.json")
T13 = tj("unit5_dimensionality_behavioral", "t13_results.json"); T14 = tj("unit5_dimensionality_behavioral", "t14_results.json"); T15 = tj("unit5_dimensionality_behavioral", "t15_results.json")
