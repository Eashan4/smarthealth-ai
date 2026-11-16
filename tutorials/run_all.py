"""Run tutorials T1-T15 in order, save each one's printed output to logs/tN.txt, and report PASS/FAIL.

Every script ends with assert-based self-checks, so exit code 0 means the tutorial's own checks passed.
Usage (from anywhere):  python tutorials/run_all.py           # all
                        python tutorials/run_all.py 7 8 9     # only T7-T9
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
LOGS = ROOT / "logs"
STEPS = [  # (label, folder, script)
    ("setup", "unit1_ehr", "generate_data.py"),
    ("T1", "unit1_ehr", "t1_understanding_ehr.py"),
    ("T2", "unit1_ehr", "t2_standardization_cleaning.py"),
    ("T3", "unit1_ehr", "t3_redundancy_missing_data.py"),
    ("T4", "unit2_biomedical_imaging", "t4_enhancement_restoration_segmentation_compression.py"),
    ("T5", "unit2_biomedical_imaging", "t5_sift_ransac_cnn.py"),
    ("T6", "unit2_biomedical_imaging", "t6_visualization.py"),
    ("T7", "unit3_staffing_planning", "t7_staffing_forecast.py"),
    ("T8", "unit3_staffing_planning", "t8_strategic_planning_descriptive.py"),
    ("T9", "unit3_staffing_planning", "t9_strategic_planning_predictive.py"),
    ("T10", "unit4_clinical_text", "t10_text_classification_clustering.py"),
    ("T11", "unit4_clinical_text", "t11_information_extraction_ner.py"),
    ("T12", "unit4_clinical_text", "t12_ranking_disambiguation.py"),
    ("T13", "unit5_dimensionality_behavioral", "t13_dimensionality_reduction.py"),
    ("T14", "unit5_dimensionality_behavioral", "t14_behavioral_factors_part1.py"),
    ("T15", "unit5_dimensionality_behavioral", "t15_behavioral_factors_part2.py"),
]

if __name__ == "__main__":
    wanted = {f"T{a}" for a in sys.argv[1:]}
    LOGS.mkdir(exist_ok=True)
    failed = []
    for label, folder, script in STEPS:
        if wanted and label not in wanted:
            continue
        t0 = time.time()
        r = subprocess.run([sys.executable, script], cwd=ROOT / folder, capture_output=True, text=True)
        (LOGS / f"{label.lower()}.txt").write_text(r.stdout + (("\n--- stderr ---\n" + r.stderr) if r.returncode else ""))
        ok = r.returncode == 0
        failed += [] if ok else [label]
        print(f"{label:6s} {'PASS' if ok else 'FAIL'}  {time.time() - t0:5.1f}s  {folder}/{script}")
    print("\nAll tutorials passed." if not failed else f"\nFAILED: {', '.join(failed)}")
    sys.exit(1 if failed else 0)
