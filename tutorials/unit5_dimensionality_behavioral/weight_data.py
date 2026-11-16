"""Synthetic adult weight / behaviour dataset for T14-T15 (2,111 people; NOT real data).

The columns follow the well-known 'eating habits and physical condition' obesity study (FAVC, FCVC, NCP, CAEC, SMOKE,
CH2O, SCC, FAF, TUE, CALC, MTRANS, family history ...) so the analysis transfers to the real file unchanged. Real data
could not be downloaded in this environment, so BMI is generated from a stated model with known effect sizes, which
lets the tutorials check that the analysis recovers what was put in:

  BMI = 14.5 + age effect (rises to 35 then flat) + male + family history + high-calorie food + vegetables + meals + snacking (non-monotone)
        + alcohol + transport + water + calorie monitoring + physical activity + screen time
        + three interactions (high-calorie food x inactive, screen time x inactive, family history x high-calorie food) + noise
Every effect is multiplied by EFFECT_SCALE so the behavioural signal is clearly visible above the noise.
"""

import numpy as np
import pandas as pd

CAEC = ["no", "Sometimes", "Frequently", "Always"]
CALC = ["no", "Sometimes", "Frequently", "Always"]
MTRANS = ["Public_Transportation", "Automobile", "Walking", "Motorbike", "Bike"]
CLASSES = ["Underweight", "Normal", "Overweight_I", "Overweight_II", "Obesity_I", "Obesity_II", "Obesity_III"]
CUTS = [18.5, 25.0, 27.5, 30.0, 35.0, 40.0]

EFFECT_SCALE, NOISE_SD = 1.8, 3.0
TRUE_EFFECTS = {   # BMI units, before EFFECT_SCALE
    "family_history": 2.0, "FAVC": 2.0, "FCVC (per level)": -0.8, "NCP>3 (per meal)": 0.5, "CAEC Sometimes": 2.5, "CAEC Frequently": 0.5,
    "CAEC Always": 0.5, "CALC Frequently": 1.5, "CALC Always": 2.0, "MTRANS Automobile": 1.0, "MTRANS Walking": -2.0,
    "MTRANS Bike": -1.5, "CH2O (per level)": -0.4, "SCC": -1.0, "FAF (per level)": -1.0, "TUE (per level)": 0.6,
    "SMOKE": -0.5, "FAVC x FAF=0": 3.0, "TUE=2 x FAF<=1": 2.0, "family_history x FAVC": 1.5,
    "age (per year, 25 to 35 then flat)": 0.3, "male": 0.8}


def make_weight_data(n=2111, seed=42):
    rng = np.random.default_rng(seed)
    age = np.clip(rng.lognormal(3.15, 0.28, n), 14, 61).round()
    male = rng.random(n) < 0.5
    height = np.where(male, rng.normal(1.76, 0.07, n), rng.normal(1.65, 0.065, n)).round(2)
    d = pd.DataFrame({
        "Gender": np.where(male, "Male", "Female"), "Age": age, "Height": height,
        "family_history": (rng.random(n) < 0.82).astype(int),
        "FAVC": (rng.random(n) < 0.88).astype(int),
        "FCVC": rng.choice([1, 2, 3], n, p=[0.1, 0.5, 0.4]),
        "NCP": rng.choice([1, 2, 3, 4], n, p=[0.1, 0.18, 0.62, 0.10]),
        "CAEC": rng.choice(CAEC, n, p=[0.03, 0.80, 0.14, 0.03]),
        "SMOKE": (rng.random(n) < 0.02).astype(int),
        "CH2O": rng.choice([1, 2, 3], n, p=[0.25, 0.5, 0.25]),
        "SCC": (rng.random(n) < 0.05).astype(int),
        "FAF": rng.choice([0, 1, 2, 3], n, p=[0.30, 0.35, 0.25, 0.10]),
        "TUE": rng.choice([0, 1, 2], n, p=[0.35, 0.40, 0.25]),
        "CALC": rng.choice(CALC, n, p=[0.30, 0.66, 0.035, 0.005]),
        "MTRANS": rng.choice(MTRANS, n, p=[0.75, 0.21, 0.03, 0.005, 0.005]),
    })
    t = TRUE_EFFECTS
    S = EFFECT_SCALE
    effects = (t["family_history"] * d.family_history
               + t["FAVC"] * d.FAVC + t["FCVC (per level)"] * (d.FCVC - 2) + t["NCP>3 (per meal)"] * (d.NCP - 3).clip(lower=0)
               + d.CAEC.map({"no": 0, "Sometimes": t["CAEC Sometimes"], "Frequently": t["CAEC Frequently"], "Always": t["CAEC Always"]})
               + d.CALC.map({"no": 0, "Sometimes": 0.5, "Frequently": t["CALC Frequently"], "Always": t["CALC Always"]})
               + d.MTRANS.map({"Public_Transportation": 0, "Motorbike": 0, "Automobile": t["MTRANS Automobile"], "Walking": t["MTRANS Walking"], "Bike": t["MTRANS Bike"]})
               + t["CH2O (per level)"] * (d.CH2O - 2) + t["SCC"] * d.SCC + t["FAF (per level)"] * (d.FAF - 1) + t["TUE (per level)"] * (d.TUE - 1)
               + t["SMOKE"] * d.SMOKE + t["FAVC x FAF=0"] * ((d.FAVC == 1) & (d.FAF == 0)) + t["male"] * male
               + t["TUE=2 x FAF<=1"] * ((d.TUE == 2) & (d.FAF <= 1)) + t["family_history x FAVC"] * (d.family_history * d.FAVC)
               + t["age (per year, 25 to 35 then flat)"] * (np.minimum(d.Age, 35) - 25))
    bmi = 14.5 + S * effects + rng.normal(0, NOISE_SD, n)
    bmi = np.clip(bmi, 14, 52)
    d["Weight"] = (bmi * d.Height ** 2).round(1)
    d["BMI"] = (d.Weight / d.Height ** 2).round(2)
    d["Class"] = pd.Categorical([CLASSES[i] for i in np.searchsorted(CUTS, d.BMI, side="right")], categories=CLASSES, ordered=True)
    return d
