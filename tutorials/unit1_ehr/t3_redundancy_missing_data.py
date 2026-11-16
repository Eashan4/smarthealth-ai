"""T3: Preprocessing EHR -- redundant data removal, missing data handling.

Takes T2's standardized/cleaned data (which still has duplicate rows and
missing values -- T2 only standardized formats, it didn't touch redundancy
or missingness) and:
  - detects & removes exact duplicate records (redundant re-submitted
    encounters)
  - reports missingness before/after (bar chart + a heatmap-style plot)
  - handles missing data with two different strategies:
      1. listwise deletion for lab values missing alongside other lab
         values (rows too incomplete to safely impute)
      2. median imputation for numeric vitals, mode imputation for
         categorical gender, and KNNImputer for the two correlated lab
         columns (glucose, creatinine)

Run: python t3_redundancy_missing_data.py  (after t2_standardization_cleaning.py)
Output: outputs/t3_final_ehr.csv, outputs/t3_missingness_before_after.png,
        outputs/t3_missingness_heatmap.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer

DATA_PATH = Path(__file__).parent / "outputs" / "t2_cleaned_ehr.csv"
OUT_DIR = Path(__file__).parent / "outputs"

NUMERIC_VITALS = ["heart_rate", "systolic_bp", "diastolic_bp", "temperature", "spo2"]
LAB_COLS = ["lab_glucose", "lab_creatinine"]


def remove_duplicates(df):
    n_before = len(df)
    n_dupes = df.duplicated().sum()
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"Redundant records: removed {n_dupes} exact duplicate rows "
          f"({n_before} -> {len(df)} rows)")
    return df


def missingness_report(df, label):
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    print(f"\nMissingness ({label}):")
    if missing.empty:
        print("  none")
    else:
        for col, n in missing.items():
            print(f"  {col:20s} {n:4d} ({n / len(df) * 100:.1f}%)")
    return missing


def listwise_delete_incomplete_labs(df):
    """Drop rows where BOTH lab values are missing -- too little information
    to impute reliably, so listwise deletion is the safer strategy here."""
    n_before = len(df)
    both_missing = df[LAB_COLS].isnull().all(axis=1)
    df = df[~both_missing].reset_index(drop=True)
    print(f"Listwise deletion: removed {both_missing.sum()} rows with both lab values "
          f"missing ({n_before} -> {len(df)} rows)")
    return df


def impute_categorical_mode(df, col):
    mode_val = df[col].mode(dropna=True)[0]
    n_missing = df[col].isnull().sum()
    df[col] = df[col].fillna(mode_val)
    print(f"Mode imputation: filled {n_missing} missing {col} values with '{mode_val}'")
    return df


def impute_vitals_median(df):
    for col in NUMERIC_VITALS:
        n_missing = df[col].isnull().sum()
        if n_missing:
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            print(f"Median imputation: filled {n_missing} missing {col} values with {median_val:.1f}")
    return df


def impute_labs_knn(df, n_neighbors=5):
    """KNNImputer for the two correlated lab columns -- glucose and
    creatinine are more informatively imputed from each other's nearest
    neighbors than with a blind column mean."""
    n_missing = df[LAB_COLS].isnull().sum().sum()
    imputer = KNNImputer(n_neighbors=n_neighbors)
    # sklearn's nan-aware distance computation emits benign floating-point
    # warnings (over/invalid) on masked matmuls -- harmless here, silenced
    # so the tutorial output stays readable.
    with np.errstate(invalid="ignore", over="ignore", divide="ignore"):
        df[LAB_COLS] = imputer.fit_transform(df[LAB_COLS])
    print(f"KNN imputation (k={n_neighbors}): filled {n_missing} missing lab values "
          f"across {LAB_COLS}")
    return df


def plot_before_after(before, after, n_rows_before, n_rows_after):
    fig, ax = plt.subplots(figsize=(9, 5))
    cols = sorted(set(before.index) | set(after.index))
    before_pct = [before.get(c, 0) / n_rows_before * 100 for c in cols]
    after_pct = [after.get(c, 0) / n_rows_after * 100 for c in cols]
    x = np.arange(len(cols))
    width = 0.35
    ax.bar(x - width / 2, before_pct, width, label="Before", color="indianred")
    ax.bar(x + width / 2, after_pct, width, label="After", color="seagreen")
    ax.set_xticks(x)
    ax.set_xticklabels(cols, rotation=45, ha="right")
    ax.set_ylabel("Missing (%)")
    ax.set_title("Missingness Before vs. After Cleaning")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "t3_missingness_before_after.png", dpi=120)
    plt.close(fig)


def plot_missingness_heatmap(df, filename):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.imshow(df.isnull().values.T, aspect="auto", cmap="Reds", interpolation="nearest")
    ax.set_yticks(range(len(df.columns)))
    ax.set_yticklabels(df.columns)
    ax.set_xlabel("Row index")
    ax.set_title("Missing Value Heatmap (red = missing)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / filename, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    df = pd.read_csv(DATA_PATH)
    # Drop T2's illustrative z-score columns -- T3 works on the core clinical
    # fields; z-scores computed pre-imputation would be stale after this
    # script fills the underlying vitals.
    df = df.drop(columns=[f"{c}_zscore" for c in NUMERIC_VITALS])
    print(f"Loaded {len(df)} rows from T2 output\n")

    print("=" * 60)
    print("REDUNDANT DATA REMOVAL")
    print("=" * 60)
    df = remove_duplicates(df)

    missing_before = missingness_report(df, "before imputation")
    plot_missingness_heatmap(df, "t3_missingness_heatmap.png")
    n_rows_before = len(df)

    print("\n" + "=" * 60)
    print("MISSING DATA HANDLING")
    print("=" * 60)
    df = listwise_delete_incomplete_labs(df)
    df = impute_categorical_mode(df, "gender")
    df = impute_categorical_mode(df, "diagnosis_code")
    df = impute_vitals_median(df)
    df = impute_labs_knn(df)

    missing_after = missingness_report(df, "after imputation")
    plot_before_after(missing_before, missing_after, n_rows_before, len(df))

    out_path = OUT_DIR / "t3_final_ehr.csv"
    df.to_csv(out_path, index=False)
    print(f"\nWrote final cleaned data to {out_path}")

    # Self-check
    assert df.duplicated().sum() == 0, "duplicate rows remain after cleaning"
    assert df.isnull().sum().sum() == 0, "missing values remain after imputation"
    assert len(df) < n_rows_before + 1, "row count should not increase"
    print("Self-check passed: no duplicate rows, zero missingness in final dataset.")
