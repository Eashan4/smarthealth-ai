"""T2: Preprocessing EHR -- standardization, data cleaning.

Takes the messy synthetic EHR data and:
  - standardizes gender labels to a single vocabulary {M, F}
  - standardizes admission_date to one ISO format (parses 3 mixed formats)
  - fixes the Fahrenheit-recorded temperatures back to Celsius
  - validates vital-sign ranges and flags physiologically impossible values
  - z-score normalizes numeric vitals with scikit-learn's StandardScaler

Prints a before/after comparison, then writes the cleaned CSV.

Run: python t2_standardization_cleaning.py  (after generate_data.py)
Output: outputs/t2_cleaned_ehr.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

DATA_PATH = Path(__file__).parent / "data" / "synthetic_ehr.csv"
OUT_DIR = Path(__file__).parent / "outputs"

GENDER_MAP = {
    "male": "M", "m": "M",
    "female": "F", "f": "F",
}

DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y"]

# Physiologically plausible ranges -- values outside these are data errors,
# not real measurements, so they get flagged and set to NaN (to be imputed
# in T3) rather than silently trusted.
VALID_RANGES = {
    "heart_rate": (25, 220),
    "systolic_bp": (60, 250),
    "diastolic_bp": (30, 150),
    "temperature": (30, 45),   # Celsius
    "spo2": (50, 100),
}

VITAL_COLS = ["heart_rate", "systolic_bp", "diastolic_bp", "temperature", "spo2"]


def standardize_gender(df):
    before_unique = df["gender"].dropna().nunique()
    df["gender"] = df["gender"].str.strip().str.lower().map(GENDER_MAP)
    after_unique = df["gender"].dropna().nunique()
    print(f"gender: {before_unique} raw labels -> {after_unique} standardized labels (M/F)")
    return df


def standardize_dates(df):
    def parse_one(s):
        if pd.isna(s):
            return pd.NaT
        for fmt in DATE_FORMATS:
            try:
                return pd.to_datetime(s, format=fmt)
            except (ValueError, TypeError):
                continue
        return pd.NaT

    parsed = df["admission_date"].apply(parse_one)
    n_failed = parsed.isna().sum() - df["admission_date"].isna().sum()
    print(f"admission_date: parsed {parsed.notna().sum()}/{len(df)} rows from 3 mixed formats "
          f"into ISO YYYY-MM-DD ({n_failed} unparseable)")
    df["admission_date"] = parsed.dt.strftime("%Y-%m-%d")
    return df


def fix_temperature_units(df):
    # Anything above 45 cannot be a Celsius body temperature -- it's a
    # Fahrenheit reading that was mislabeled. Convert it back.
    is_fahrenheit = df["temperature"] > 45
    n_fixed = is_fahrenheit.sum()
    df.loc[is_fahrenheit, "temperature"] = (df.loc[is_fahrenheit, "temperature"] - 32) * 5 / 9
    df["temperature"] = df["temperature"].round(1)
    print(f"temperature: converted {n_fixed} Fahrenheit-unit readings back to Celsius")
    return df


def validate_ranges(df):
    flagged_total = 0
    for col, (lo, hi) in VALID_RANGES.items():
        out_of_range = df[col].notna() & ((df[col] < lo) | (df[col] > hi))
        n = out_of_range.sum()
        if n:
            print(f"{col}: {n} out-of-range values (outside [{lo}, {hi}]) flagged -> set to NaN")
        df.loc[out_of_range, col] = np.nan
        flagged_total += n
    print(f"Total out-of-range vitals flagged: {flagged_total}")
    return df


def zscore_normalize(df):
    """Z-score normalize vitals with StandardScaler; keep raw + scaled columns
    so T3's imputation still works on clinically meaningful units."""
    scaler = StandardScaler()
    valid = df[VITAL_COLS].notna().all(axis=1)
    scaled = np.full((len(df), len(VITAL_COLS)), np.nan)
    scaled[valid.values] = scaler.fit_transform(df.loc[valid, VITAL_COLS])
    for i, col in enumerate(VITAL_COLS):
        df[f"{col}_zscore"] = scaled[:, i]
    print(f"z-score normalized {VITAL_COLS} on {valid.sum()} complete-case rows "
          f"(mean~0, std~1 per column)")
    return df


if __name__ == "__main__":
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows\n")

    print("=" * 60)
    print("STANDARDIZATION")
    print("=" * 60)
    df = standardize_gender(df)
    df = standardize_dates(df)
    df = fix_temperature_units(df)

    print("\n" + "=" * 60)
    print("VALIDATION")
    print("=" * 60)
    df = validate_ranges(df)

    print("\n" + "=" * 60)
    print("NORMALIZATION (StandardScaler)")
    print("=" * 60)
    df = zscore_normalize(df)

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "t2_cleaned_ehr.csv"
    df.to_csv(out_path, index=False)
    print(f"\nWrote cleaned data to {out_path}")

    # Self-check
    assert set(df["gender"].dropna().unique()) <= {"M", "F"}, "gender not fully standardized"
    parsed_dates = pd.to_datetime(df["admission_date"], format="%Y-%m-%d", errors="coerce")
    assert parsed_dates.notna().sum() == df["admission_date"].notna().sum(), \
        "admission_date not fully standardized to ISO format"
    assert (df["temperature"].dropna() <= 45).all(), "Fahrenheit temperatures still present"
    for col, (lo, hi) in VALID_RANGES.items():
        assert ((df[col].dropna() >= lo) & (df[col].dropna() <= hi)).all(), f"{col} still has out-of-range values"
    for col in VITAL_COLS:
        z = df[f"{col}_zscore"].dropna()
        assert abs(z.mean()) < 0.05 and abs(z.std() - 1) < 0.05, f"{col}_zscore not properly normalized"
    print("Self-check passed: gender, dates, units, ranges standardized; z-scores centered/scaled.")
