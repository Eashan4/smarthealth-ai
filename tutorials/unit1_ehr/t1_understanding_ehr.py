"""T1: Understanding EHR -- structure, components, coding systems.

Loads the synthetic EHR dataset and explores it the way you'd explore a real
EHR extract: schema/dtypes, what coding system is in use (ICD-10), a
breakdown of diagnoses, summary stats on vitals/labs, and -- just as
important -- the practical barriers: missingness and formatting
inconsistency. Ties to syllabus topics: Components of EHR, Coding Systems,
Benefits of EHR, Barriers to Adopting EHR, Challenges of Using EHR Data.

Run: python t1_understanding_ehr.py  (after generate_data.py)
Output: outputs/t1_diagnosis_distribution.png, outputs/t1_missingness.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

DATA_PATH = Path(__file__).parent / "data" / "synthetic_ehr.csv"
OUT_DIR = Path(__file__).parent / "outputs"

# ICD-10 is the coding system used throughout this dataset (component of EHR:
# structured diagnosis coding). Real-world codes -> human-readable category.
ICD10_LOOKUP = {
    "I10": ("Essential hypertension", "Circulatory"),
    "E11.9": ("Type 2 diabetes mellitus", "Endocrine"),
    "J45.909": ("Asthma, uncomplicated", "Respiratory"),
    "N18.3": ("Chronic kidney disease, stage 3", "Genitourinary"),
    "I50.9": ("Heart failure, unspecified", "Circulatory"),
    "J18.9": ("Pneumonia, unspecified organism", "Respiratory"),
    "K21.9": ("GERD without esophagitis", "Digestive"),
    "F32.9": ("Major depressive disorder, single episode", "Mental health"),
    "I21.9": ("Acute myocardial infarction", "Circulatory"),
    "M54.5": ("Low back pain", "Musculoskeletal"),
}


def explore_structure(df):
    print("=" * 60)
    print("SCHEMA / COMPONENTS OF THE EHR RECORD")
    print("=" * 60)
    print(df.dtypes)
    print(f"\n{len(df)} encounter records, {df.shape[1]} fields")
    print("\nColumns map to standard EHR components:")
    print("  patient_id, age, gender      -> patient demographics")
    print("  admission_date, length_of_stay -> encounter/administrative")
    print("  diagnosis_code               -> coded clinical data (ICD-10)")
    print("  heart_rate/bp/temp/spo2      -> vitals")
    print("  lab_glucose, lab_creatinine  -> lab results")


def explore_coding_system(df):
    print("\n" + "=" * 60)
    print("CODING SYSTEM: ICD-10 diagnosis breakdown")
    print("=" * 60)
    counts = df["diagnosis_code"].value_counts(dropna=True)
    for code, n in counts.items():
        desc, category = ICD10_LOOKUP.get(code, ("Unknown code", "Unknown"))
        print(f"  {code:10s} {desc:45s} [{category:15s}] n={n}")

    category_counts = df["diagnosis_code"].map(
        lambda c: ICD10_LOOKUP.get(c, ("Unknown", "Unknown"))[1] if pd.notna(c) else "Missing"
    ).value_counts()

    OUT_DIR.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    counts.plot(kind="bar", ax=ax, color="steelblue")
    ax.set_title("ICD-10 Diagnosis Code Distribution")
    ax.set_xlabel("ICD-10 code")
    ax.set_ylabel("Encounter count")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "t1_diagnosis_distribution.png", dpi=120)
    plt.close(fig)

    return category_counts


def explore_barriers(df):
    print("\n" + "=" * 60)
    print("BARRIERS / CHALLENGES: missingness & inconsistency")
    print("=" * 60)
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(1)
    for col in df.columns:
        if missing[col] > 0:
            print(f"  {col:16s} {missing[col]:4d} missing ({missing_pct[col]}%)")

    dup_count = df.duplicated().sum()
    print(f"\n  {dup_count} fully duplicate rows (data re-entry / redundant records)")

    gender_variants = df["gender"].dropna().unique()
    print(f"  gender field has {len(gender_variants)} inconsistent raw values: {sorted(gender_variants)}")

    fig, ax = plt.subplots(figsize=(8, 5))
    missing[missing > 0].sort_values(ascending=False).plot(kind="bar", ax=ax, color="indianred")
    ax.set_title("Missing Values per Field (EHR data quality barrier)")
    ax.set_ylabel("Missing count")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "t1_missingness.png", dpi=120)
    plt.close(fig)

    return missing


def summary_stats(df):
    print("\n" + "=" * 60)
    print("SUMMARY STATS: vitals & labs")
    print("=" * 60)
    numeric_cols = ["age", "heart_rate", "systolic_bp", "diastolic_bp",
                     "temperature", "spo2", "lab_glucose", "lab_creatinine",
                     "length_of_stay"]
    print(df[numeric_cols].apply(pd.to_numeric, errors="coerce").describe().round(2))


if __name__ == "__main__":
    df = pd.read_csv(DATA_PATH)

    explore_structure(df)
    category_counts = explore_coding_system(df)
    missing = explore_barriers(df)
    summary_stats(df)

    print("\nSaved plots to", OUT_DIR)

    # Self-check
    assert set(ICD10_LOOKUP) >= set(df["diagnosis_code"].dropna().unique()), \
        "found a diagnosis code with no ICD-10 lookup entry"
    assert missing.sum() > 0, "expected missingness to demonstrate EHR barriers"
    assert (OUT_DIR / "t1_diagnosis_distribution.png").exists()
    assert (OUT_DIR / "t1_missingness.png").exists()
    print("Self-check passed: coding system mapped, barriers quantified, plots saved.")
