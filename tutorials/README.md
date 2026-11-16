# Healthcare Analytics tutorials T1 – T15 (21CSE428T)

All fifteen tutorials in one folder, grouped by syllabus unit. Every script is self-contained, fixed-seed, prints its
results, writes figures to its unit's `outputs/` folder, and ends with `assert`-based self-checks.

| Unit | Folder | Tutorials | Data |
|---|---|---|---|
| 1 | `unit1_ehr/` | T1 Understanding EHR, T2 Standardization & cleaning, T3 Redundancy & missing data | synthetic EHR (410 rows) |
| 2 | `unit2_biomedical_imaging/` | T4 Enhancement / restoration / segmentation / compression, T5 SIFT, RANSAC, CNN, T6 Visualization | scikit-image microscopy sample |
| 3 | `unit3_staffing_planning/` | T7 Patient prediction for staffing, T8 Strategic planning I (descriptive), T9 Strategic planning II (predictive + prescriptive) | synthetic hospital data |
| 4 | `unit4_clinical_text/` | T10 Classification & clustering, T11 Information extraction & NER, T12 Ranking & word-sense disambiguation | synthetic clinical notes with gold annotations |
| 5 | `unit5_dimensionality_behavioral/` | T13 Dimensionality reduction, T14 Behavioural factors & weight I, T15 Behavioural factors & weight II | real Wisconsin breast-cancer data (T13), synthetic behaviour data (T14-T15) |

## Run everything

```bash
source venv/bin/activate                     # project venv: numpy, pandas, scikit-learn, scipy, matplotlib, torch
pip install -r tutorials/unit2_biomedical_imaging/requirements.txt   # scikit-image, once
python tutorials/run_all.py                  # T1-T15, writes tutorials/logs/tN.txt, prints PASS/FAIL
python tutorials/run_all.py 7 8 9            # only some tutorials
```

About 2 minutes in total (T7 is the slow one, about a minute). No network access is needed.

## What each tutorial found (real numbers from `logs/`)

| | Technique | Headline result |
|---|---|---|
| T1 | EHR structure, ICD-10 coding, data barriers | 410 records, 13 fields, up to 15% missing per field, 8 spellings of "gender" |
| T2 | Standardization, validation, z-scores | 42 Fahrenheit readings converted, 27 impossible SpO2 values flagged |
| T3 | De-duplication, deletion + imputation | 30 duplicates removed; missingness 15% to 0% |
| T4 | CLAHE, denoising, Otsu, JPEG | PSNR 20.1 to 25.3 dB after denoising; JPEG 5.2 KB (q10) to 23.8 KB (q90) |
| T5 | SIFT, RANSAC, small CNN | rotation 12.0 deg recovered as 11.9 deg (13/14 inliers); toy CNN only 56.7% on 30 held-out patches (reported as is) |
| T6 | Side-by-side, histogram, overlay | visual checks of T4/T5 results |
| T7 | Forecast + roster | 7-day-ahead MAE 24.5 vs 37.4 seasonal-naive; forecast roster + buffer cost 1991 vs 3631 flat |
| T8 | Service-line scorecard | 91.3% occupancy of 420 beds; orthopaedics earns the most per bed-day, pulmonology the least |
| T9 | Projection + linear programme | base case needs 515 beds in 2027 vs 420 licensed; LP mix adds 1.6 M margin over equal cuts; a bed-day is worth about 1,397 |
| T10 | TF-IDF + NB/LR/SVM, k-means | 98.0% test accuracy; clustering ARI 0.00 on all words, 0.89 once boilerplate is removed |
| T11 | Regex, dictionary, learned tagger, negation | regex v2 fixes "150 over 90" (0.845 to 1.0); dictionary and lexicon-fed tagger find 0% of unseen drugs, tagger without lexicon 100% |
| T12 | BM25 vs TF-IDF, TextRank, WSD | BM25 P@10 0.85 vs 0.76; context WSD 0.99 vs 0.50 most-frequent-sense |
| T13 | PCA, LDA, t-SNE, Isomap | 7 components keep 90% variance, 10 keep 95%; 10 PCs match all 30 features (98.1%) |
| T14 | Hypothesis tests, effect sizes, BH correction | physical activity explains most BMI variance (eta-squared 0.28); 9 of 13 factors significant after correction |
| T15 | OLS vs forests/boosting, importance, phenotypes | Height+Weight leaks the label (97.8%) vs 49.3% from behaviour alone; boosting R2 0.81 vs OLS 0.77 |

## Honest notes about the data

- **T1-T3, T7-T12, T14-T15 use synthetic data.** No real patient data is in this repository. Generators are fixed-seed and
  documented in each unit (`generate_data.py`, `hospital_data.py`, `notes_data.py`, `weight_data.py`).
- **Perfect or near-perfect scores in T10-T12 are a ceiling effect of templated text**, not a real-world claim.
- **T14-T15** generate BMI from a stated model with known effect sizes, so the analysis can be checked against what was
  planted (small planted effects such as smoking and water intake are, correctly, not detected).
- T13 is the only tutorial on a real dataset (`sklearn.datasets.load_breast_cancer`).
