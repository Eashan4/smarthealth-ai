# Unit 1: An Introduction to Healthcare Data Analytics — Tutorials

Coursework for **21CSE428T Healthcare Analytics**, Unit 1. This folder is
separate from the main SmartHealth AI project (ESP32 + ML fall/activity
detection using wearable IMU sensor data). SmartHealth AI does not use EHR
data anywhere, so there was no real EHR dataset to pull from — the dataset
here is **synthetic, generated for this tutorial only**, not real patient
data. It uses real ICD-10 diagnosis codes so the coding-system material is
accurate, but every patient, vital, and lab value is fabricated.

## Syllabus mapping

| Script | Tutorial code | Syllabus topic |
|---|---|---|
| `generate_data.py` | (setup) | produces the messy synthetic dataset the tutorials below clean |
| `t1_understanding_ehr.py` | **T1** | Understanding EHR — structure, components, coding systems |
| `t2_standardization_cleaning.py` | **T2** | Preprocessing EHR — standardization, data cleaning |
| `t3_redundancy_missing_data.py` | **T3** | Preprocessing EHR — redundant data removal, missing data handling |

## What each script does

**`generate_data.py`** — builds `data/synthetic_ehr.csv` (~410 rows) with
numpy/pandas, fixed seed (42) for reproducibility. Patient demographics,
admission dates, ICD-10 diagnosis codes (I10 hypertension, E11.9 type 2
diabetes, J45.909 asthma, etc.), vitals, and two lab values. Deliberately
messy: exact duplicate rows, missing values (NaN) scattered across 8
columns, 8 different raw spellings of gender, 3 mixed date formats, and a
chunk of temperatures mistakenly recorded in Fahrenheit — realistic problems
for T2/T3 to fix.

**`t1_understanding_ehr.py`** — loads the raw data and explores it as an
EHR extract: schema/dtypes, an ICD-10 code → description/category lookup
(coding systems), a diagnosis distribution chart, and a quantified look at
the barriers to using EHR data (missingness per field, duplicate count,
inconsistent gender labels). Saves `outputs/t1_diagnosis_distribution.png`
and `outputs/t1_missingness.png`.

**`t2_standardization_cleaning.py`** — standardizes gender to {M, F},
parses the 3 mixed date formats into one ISO format, detects and converts
mislabeled Fahrenheit temperatures back to Celsius, validates vitals against
physiologically plausible ranges (flagging impossible values as NaN), and
z-score normalizes vitals with scikit-learn's `StandardScaler`. Prints
before/after counts for every fix. Writes `outputs/t2_cleaned_ehr.csv`.

**`t3_redundancy_missing_data.py`** — removes exact duplicate rows
(redundant records), then handles remaining missingness with two different
strategies: listwise deletion for rows missing both lab values (too little
signal to impute), and imputation everywhere else — mode for categoricals
(gender, diagnosis_code), median for vitals, and `KNNImputer` for the two
correlated lab columns (glucose, creatinine). Reports missingness
before/after as a bar chart (`t3_missingness_before_after.png`) and a
heatmap-style plot (`t3_missingness_heatmap.png`). Writes the final,
fully-clean `outputs/t3_final_ehr.csv`.

Every script ends with `assert`-based self-checks confirming the expected
transformation actually happened (e.g., T3 asserts zero duplicates and zero
missing values in the final output).

## How to run

From the repo root:

```bash
source venv/bin/activate
cd tutorials/unit1_ehr
python generate_data.py
python t1_understanding_ehr.py
python t2_standardization_cleaning.py
python t3_redundancy_missing_data.py
```

Or in one line:

```bash
source ../../venv/bin/activate && python generate_data.py && python t1_understanding_ehr.py && python t2_standardization_cleaning.py && python t3_redundancy_missing_data.py
```

No new dependencies — only numpy, pandas, scikit-learn, and matplotlib,
already in the project's `venv`.

## Outputs

All generated files (`data/synthetic_ehr.csv`, everything in `outputs/`)
are reproducible from the scripts and are not meant to be hand-edited.
