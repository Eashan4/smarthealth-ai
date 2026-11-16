"""Synthetic clinical notes for T10-T12 (no real patient text is used; every note is generated from templates).

Each note comes with gold annotations produced *by construction*, so extraction (T11) and retrieval (T12) can be
scored exactly: entity spans (DRUG / CONDITION / SYMPTOM, with a negation flag), structured facts (dose, frequency,
blood pressure, heart rate) and the primary specialty/condition.

Realism knobs: ~35% of notes carry a comorbidity from another specialty, symptoms are shared across specialties
(dyspnoea, chest pain, fatigue...), and drugs follow real naming stems (-olol, -pril, -statin) so a model can learn
to recognise drug names it has never seen.
"""

import random

SPECIALTIES = {
    "cardiology": dict(
        conditions=["atrial fibrillation", "hypertension", "heart failure", "coronary artery disease", "myocardial infarction", "angina"],
        symptoms=["chest pain", "palpitations", "dyspnoea", "ankle swelling", "dizziness", "syncope"],
        drugs=["atenolol", "amlodipine", "metoprolol", "ramipril", "atorvastatin", "clopidogrel", "furosemide", "warfarin"]),
    "respiratory": dict(
        conditions=["asthma", "copd", "pneumonia", "bronchitis", "pulmonary embolism", "tuberculosis"],
        symptoms=["cough", "wheeze", "dyspnoea", "sputum production", "chest tightness", "fever"],
        drugs=["salbutamol", "budesonide", "montelukast", "tiotropium", "prednisolone", "azithromycin", "ipratropium", "theophylline"]),
    "neurology": dict(
        conditions=["epilepsy", "migraine", "parkinson disease", "stroke", "multiple sclerosis", "dementia"],
        symptoms=["headache", "seizure", "tremor", "numbness", "memory loss", "dizziness"],
        drugs=["levetiracetam", "sumatriptan", "carbamazepine", "gabapentin", "topiramate", "donepezil", "levodopa", "pramipexole"]),
    "gastroenterology": dict(
        conditions=["gastro-oesophageal reflux", "crohn disease", "ulcerative colitis", "cirrhosis", "peptic ulcer", "pancreatitis"],
        symptoms=["abdominal pain", "nausea", "vomiting", "diarrhoea", "heartburn", "weight loss"],
        drugs=["omeprazole", "pantoprazole", "ranitidine", "lactulose", "mesalamine", "ondansetron", "domperidone", "rifaximin"]),
    "orthopaedics": dict(
        conditions=["osteoarthritis", "rheumatoid arthritis", "osteoporosis", "hip fracture", "gout", "lumbar disc prolapse"],
        symptoms=["joint pain", "back pain", "stiffness", "swelling", "limping", "reduced mobility"],
        drugs=["ibuprofen", "diclofenac", "tramadol", "naproxen", "alendronate", "etoricoxib", "methotrexate", "allopurinol"]),
    "endocrinology": dict(
        conditions=["type 2 diabetes", "hypothyroidism", "hyperthyroidism", "obesity", "cushing syndrome", "pcos"],
        symptoms=["polyuria", "thirst", "fatigue", "weight gain", "heat intolerance", "blurred vision"],
        drugs=["metformin", "glimepiride", "levothyroxine", "sitagliptin", "pioglitazone", "carbimazole", "dapagliflozin", "liraglutide"]),
}
SHARED_SYMPTOMS = ["fatigue", "nausea", "fever", "dizziness", "dyspnoea", "chest pain", "headache"]
DOSES = {"mg": [5, 10, 20, 25, 40, 50, 100, 250, 500], "mcg": [25, 50, 100, 200]}
FREQS = ["once daily", "twice daily", "three times daily", "every 8 hours", "at night", "every morning"]
PLANS = ["Review in two weeks.", "Repeat bloods next visit.", "Advised lifestyle changes and follow-up in clinic.",
         "Referred for further investigation.", "Patient counselled on adherence.", "Admit for observation."]


class Note:
    def __init__(self, text, specialty, condition, entities, facts, condition_mentioned=True):
        self.text, self.specialty, self.condition, self.entities, self.facts = text, specialty, condition, entities, facts
        self.condition_mentioned = condition_mentioned


def _build(parts):
    """parts: list of str or (str, type, negated). Returns text and entity spans."""
    text, ents = "", []
    for p in parts:
        if isinstance(p, tuple):
            s, typ, neg = p
            ents.append((len(text), len(text) + len(s), typ, neg))
            text += s
        else:
            text += p
    return text, ents


def generate_notes(n, seed=0, drug_pool=None):
    """drug_pool: optional {specialty: [drugs]} restricting which drugs may appear (used to hold drugs out)."""
    rng = random.Random(seed)
    names = list(SPECIALTIES)
    notes = []
    for _ in range(n):
        sp = rng.choice(names)
        spec = SPECIALTIES[sp]
        pool = (drug_pool or {}).get(sp, spec["drugs"])
        cond = rng.choice(spec["conditions"])
        syms = rng.sample(spec["symptoms"], 2)
        if rng.random() < 0.45:                                   # symptoms shared with other specialties
            syms[1] = rng.choice(SHARED_SYMPTOMS)
        if rng.random() < 0.25:
            syms[0] = rng.choice(SHARED_SYMPTOMS)
        syms = list(dict.fromkeys(syms))
        neg = rng.choice([s for s in SHARED_SYMPTOMS + spec["symptoms"] if s not in syms])
        drug = rng.choice(pool) if rng.random() < 0.78 else rng.choice(
            [d for x in names if x != sp for d in (drug_pool or {}).get(x, SPECIALTIES[x]["drugs"])])   # off-specialty prescribing
        unit = rng.choice(list(DOSES))
        dose = f"{rng.choice(DOSES[unit])} {unit}"
        freq = rng.choice(FREQS)
        sys_, dia, hr = rng.randint(100, 175), rng.randint(60, 105), rng.randint(55, 120)
        bp_txt = f"{sys_}/{dia}" if rng.random() < 0.85 else f"{sys_} over {dia}"
        age, sex = rng.randint(22, 89), rng.choice(["male", "female"])
        dur = f"{rng.randint(2, 14)} {rng.choice(['days', 'weeks', 'months'])}"
        parts = [f"{age}-year-old {sex} presents with ", (syms[0], "SYMPTOM", False), " and ", (syms[-1], "SYMPTOM", False),
                 f" for {dur}. "]
        shown = rng.random() > 0.25                               # 25% of notes never name the main diagnosis
        parts += ["Known case of ", (cond, "CONDITION", False), ". "] if shown else ["Chronic illness, on regular follow-up. "]
        facts = {"dose": dose, "freq": freq, "bp": (sys_, dia), "hr": hr}
        parts += ["Denies ", (neg, "SYMPTOM", True), ". "]
        for _ in range(rng.choice([0, 0, 1, 1, 2])):               # comorbidities from other specialties
            osp = rng.choice([x for x in names if x != sp])
            parts += ["Also history of ", (rng.choice(SPECIALTIES[osp]["conditions"]), "CONDITION", False), ". "]
        parts += [rng.choice([f"BP {bp_txt}, HR {hr}. ", f"On examination BP {bp_txt} mmHg and pulse {hr}. "]),
                  rng.choice(["Started on ", "Prescribed ", "Continue "]), (drug, "DRUG", False), f" {dose} {freq}. "]
        if rng.random() < 0.3:
            parts += ["Also takes ", (rng.choice(pool), "DRUG", False), f" {rng.choice(DOSES['mg'])} mg once daily. "]
        parts += [rng.choice(PLANS)]
        text, ents = _build(parts)
        notes.append(Note(text, sp, cond, ents, facts, shown))
    return notes


def known_unseen_drugs(seed=1):
    """Hold out 3 of each specialty's 8 drugs: training notes never contain them, test notes do."""
    rng = random.Random(seed)
    unseen = {sp: rng.sample(v["drugs"], 3) for sp, v in SPECIALTIES.items()}
    known = {sp: [d for d in v["drugs"] if d not in unseen[sp]] for sp, v in SPECIALTIES.items()}
    return known, unseen
