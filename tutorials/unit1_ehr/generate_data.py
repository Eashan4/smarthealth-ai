"""Generate a synthetic, intentionally messy EHR dataset for Unit 1 tutorials.

This is NOT real patient data. SmartHealth AI's main project uses wearable
IMU sensor data (see ml/datasets/), not EHR records, so no real EHR dataset
exists anywhere in this repo. This script fabricates plausible patient
encounter records with real ICD-10 codes so T1/T2/T3 have something to
explore and clean. Fixed seed -> reproducible output.

Run: python generate_data.py
Output: data/synthetic_ehr.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_PATIENTS = 380       # unique encounter records
N_DUPLICATES = 30      # exact duplicate rows appended to simulate re-entry errors
OUT_PATH = Path(__file__).parent / "data" / "synthetic_ehr.csv"

# Real ICD-10 diagnosis codes, weighted toward common chronic conditions
ICD10_CODES = [
    "I10",      # essential hypertension
    "E11.9",    # type 2 diabetes mellitus without complications
    "J45.909",  # unspecified asthma, uncomplicated
    "N18.3",    # chronic kidney disease, stage 3
    "I50.9",    # heart failure, unspecified
    "J18.9",    # pneumonia, unspecified organism
    "K21.9",    # GERD without esophagitis
    "F32.9",    # major depressive disorder, single episode, unspecified
    "I21.9",    # acute myocardial infarction, unspecified
    "M54.5",    # low back pain
]
ICD10_WEIGHTS = [0.20, 0.18, 0.10, 0.08, 0.08, 0.09, 0.09, 0.08, 0.05, 0.05]

# Deliberately inconsistent gender labels -- a classic real-world EHR mess
GENDER_VARIANTS = ["Male", "M", "male", "MALE", "Female", "F", "female", "FEMALE"]

DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y"]


def _random_dates(rng, n):
    """Return admission dates as strings in a randomly mixed format per row."""
    start = pd.Timestamp("2023-01-01")
    offsets = rng.integers(0, 900, size=n)
    dates = [start + pd.Timedelta(days=int(o)) for o in offsets]
    fmts = rng.choice(DATE_FORMATS, size=n)
    return [d.strftime(f) for d, f in zip(dates, fmts)]


def generate(n_patients=N_PATIENTS, seed=SEED):
    rng = np.random.default_rng(seed)

    patient_id = [f"P{i:04d}" for i in range(1, n_patients + 1)]
    age = rng.normal(55, 18, n_patients).round().astype(int)
    age = np.clip(age, 1, 99)
    # inject a couple of impossible ages -- realistic data-entry errors
    bad_age_idx = rng.choice(n_patients, size=2, replace=False)
    age = age.astype(object)
    age[bad_age_idx[0]] = -5
    age[bad_age_idx[1]] = 137

    gender = rng.choice(GENDER_VARIANTS, size=n_patients)

    admission_date = _random_dates(rng, n_patients)

    diagnosis_code = rng.choice(ICD10_CODES, size=n_patients, p=ICD10_WEIGHTS).astype(object)

    heart_rate = rng.normal(78, 14, n_patients).round(1)
    systolic_bp = rng.normal(128, 18, n_patients).round().astype(object)
    diastolic_bp = rng.normal(80, 12, n_patients).round().astype(object)

    # temperature: mostly Celsius, but a chunk recorded in Fahrenheit by mistake
    # (a very real "inconsistent units" EHR problem) -- T2 detects & fixes this.
    temperature = rng.normal(37.0, 0.6, n_patients).round(1).astype(object)
    fahrenheit_idx = rng.choice(n_patients, size=int(n_patients * 0.12), replace=False)
    for i in fahrenheit_idx:
        temperature[i] = round(float(temperature[i]) * 9 / 5 + 32, 1)

    spo2 = rng.normal(97, 2.2, n_patients).round().astype(object)
    # a few physiologically impossible outliers (sensor/entry error)
    outlier_idx = rng.choice(n_patients, size=4, replace=False)
    for i in outlier_idx:
        spo2[i] = rng.choice([40, 150, 0])

    lab_glucose = rng.normal(105, 28, n_patients).round(1).astype(object)
    lab_creatinine = rng.normal(1.0, 0.35, n_patients).round(2).astype(object)
    length_of_stay = rng.poisson(4, n_patients) + 1

    df = pd.DataFrame({
        "patient_id": patient_id,
        "age": age,
        "gender": gender,
        "admission_date": admission_date,
        "diagnosis_code": diagnosis_code,
        "heart_rate": heart_rate,
        "systolic_bp": systolic_bp,
        "diastolic_bp": diastolic_bp,
        "temperature": temperature,
        "spo2": spo2,
        "lab_glucose": lab_glucose,
        "lab_creatinine": lab_creatinine,
        "length_of_stay": length_of_stay,
    })

    # Inject missing values (NaN) into several columns at varying rates --
    # this is the "missingness" T1 explores and T3 fixes.
    missing_rates = {
        "gender": 0.04,
        "diagnosis_code": 0.03,
        "systolic_bp": 0.10,
        "diastolic_bp": 0.10,
        "temperature": 0.08,
        "spo2": 0.06,
        "lab_glucose": 0.15,
        "lab_creatinine": 0.15,
    }
    for col, rate in missing_rates.items():
        mask_idx = rng.choice(n_patients, size=int(n_patients * rate), replace=False)
        df.loc[mask_idx, col] = np.nan

    # Append exact duplicate rows -- simulates duplicate re-submission of the
    # same encounter, a common source of redundant EHR data.
    dup_rows = df.sample(n=N_DUPLICATES, random_state=seed, replace=False)
    df = pd.concat([df, dup_rows], ignore_index=True)

    # Shuffle so duplicates aren't all at the tail
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    return df


if __name__ == "__main__":
    df = generate()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} rows to {OUT_PATH}")
    print(df.head())

    # Self-check: confirm the dataset is actually messy on purpose, since the
    # downstream cleaning tutorials (T2/T3) depend on that.
    reloaded = pd.read_csv(OUT_PATH)
    assert 300 <= len(reloaded) <= 550, "row count out of expected range"
    assert reloaded.duplicated().sum() > 0, "expected some duplicate rows"
    assert reloaded.isnull().sum().sum() > 0, "expected some missing values"
    assert reloaded["gender"].dropna().nunique() > 2, "expected inconsistent gender labels"
    print("Self-check passed: dataset has duplicates, missing values, and inconsistent formatting.")
