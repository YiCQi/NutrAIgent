"""Deterministic target calculation. All defaults PROVISIONAL (see HANDOFF.md open questions)."""
from dataclasses import dataclass

# Physical activity level multipliers (FAO/WHO/UNU style PAL bands).
ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}
# Energy adjustment vs TDEE.
GOAL_ENERGY_ADJUST = {"fat_loss": -0.20, "maintenance": 0.0, "muscle_gain": 0.10}
# Protein g per kg body weight.
GOAL_PROTEIN_G_PER_KG = {"fat_loss": 1.8, "maintenance": 1.0, "muscle_gain": 1.8}

FAT_ENERGY_FRACTION = 0.30
SAT_FAT_MAX_ENERGY_FRACTION = 0.10
FIBRE_G = 30.0
SODIUM_MAX_MG = 2400.0
# Micronutrient reference intakes: UK RNI (DH 1991, adults 19-50). Provisional, like the rest.
CALCIUM_MG = 700.0
IRON_MG = {"male": 8.7, "female": 14.8}
VITAMIN_C_MG = 40.0
VITAMIN_B12_UG = 1.5
KCAL_PER_G = {"protein": 4, "carb": 4, "fat": 9}
# Further reference values. Sex-neutral daily values from Regulation (EU) No 1169/2011 Annex XIII (UK copy on
# legislation.gov.uk). They are labelling NRVs, not RNIs; used here as provisional daily targets.
NRV_TARGETS = {
    "vitamin_a_ug": 800.0, "vitamin_d_ug": 5.0, "vitamin_e_mg": 12.0, "vitamin_k_ug": 75.0,
    "folate_ug": 200.0, "potassium_mg": 2000.0, "magnesium_mg": 375.0, "phosphorus_mg": 700.0,
    "zinc_mg": 10.0, "selenium_ug": 55.0, "iodine_ug": 150.0,
}
# EFSA 2010 DRVs for fats (EFSA Journal 2010;8(3):1461): AI EPA+DHA 250 mg/day; ALA 0.5 E%; linoleic acid 4 E%.
EPA_DHA_AI_G = 0.25
ALA_E_PCT = 0.5
LINOLEIC_E_PCT = 4.0


@dataclass(frozen=True)
class Profile:
    age: int
    sex: str  # 'male' | 'female'
    height_cm: float
    weight_kg: float
    activity_level: str
    goal: str


def bmr_mifflin_st_jeor(p: Profile) -> float:
    base = 10 * p.weight_kg + 6.25 * p.height_cm - 5 * p.age
    return base + (5 if p.sex == "male" else -161)


def compute_targets(p: Profile) -> dict:
    """Return targets with a trace of every calculation step."""
    if p.activity_level not in ACTIVITY_FACTORS:
        raise ValueError(f"unknown activity_level: {p.activity_level}")
    if p.goal not in GOAL_ENERGY_ADJUST:
        raise ValueError(f"unknown goal: {p.goal}")
    bmr = bmr_mifflin_st_jeor(p)
    tdee = bmr * ACTIVITY_FACTORS[p.activity_level]
    energy = tdee * (1 + GOAL_ENERGY_ADJUST[p.goal])
    protein = GOAL_PROTEIN_G_PER_KG[p.goal] * p.weight_kg
    fat = energy * FAT_ENERGY_FRACTION / KCAL_PER_G["fat"]
    carb = (energy - protein * KCAL_PER_G["protein"] - fat * KCAL_PER_G["fat"]) / KCAL_PER_G["carb"]
    sat_fat_max = energy * SAT_FAT_MAX_ENERGY_FRACTION / KCAL_PER_G["fat"]

    def r(x):
        return round(x, 1)

    return {
        "targets": {
            # kind: 'target' = aim to reach, 'min' = minimum to reach (no upper limit), 'max' = limit not to exceed
            "energy_kcal": {"value": r(energy), "unit": "kcal", "kind": "target"},
            "protein_g": {"value": r(protein), "unit": "g", "kind": "target"},
            "fat_g": {"value": r(fat), "unit": "g", "kind": "target"},
            "carbohydrate_g": {"value": r(max(carb, 0)), "unit": "g", "kind": "target"},
            "fibre_g": {"value": FIBRE_G, "unit": "g", "kind": "target"},
            "sat_fat_g": {"value": r(sat_fat_max), "unit": "g", "kind": "max"},
            "sodium_mg": {"value": SODIUM_MAX_MG, "unit": "mg", "kind": "max"},
            "calcium_mg": {"value": CALCIUM_MG, "unit": "mg", "kind": "min"},
            "iron_mg": {"value": IRON_MG[p.sex], "unit": "mg", "kind": "min"},
            "vitamin_c_mg": {"value": VITAMIN_C_MG, "unit": "mg", "kind": "min"},
            "vitamin_b12_ug": {"value": VITAMIN_B12_UG, "unit": "ug", "kind": "min"},
            **{code: {"value": v, "unit": code.rsplit("_", 1)[1], "kind": "min"} for code, v in NRV_TARGETS.items()},
            "epa_dha_g": {"value": EPA_DHA_AI_G, "unit": "g", "kind": "min"},
            "ala_g": {"value": round(energy * ALA_E_PCT / 100 / KCAL_PER_G["fat"], 2), "unit": "g", "kind": "min"},
            "linoleic_g": {"value": round(energy * LINOLEIC_E_PCT / 100 / KCAL_PER_G["fat"], 2), "unit": "g", "kind": "min"},
        },
        "trace": {
            "bmr_kcal": r(bmr),
            "bmr_equation": "Mifflin-St Jeor (provisional)",
            "activity_factor": ACTIVITY_FACTORS[p.activity_level],
            "tdee_kcal": r(tdee),
            "goal_adjust": GOAL_ENERGY_ADJUST[p.goal],
            "protein_g_per_kg": GOAL_PROTEIN_G_PER_KG[p.goal],
            "fat_energy_fraction": FAT_ENERGY_FRACTION,
            "provisional": True,
        },
    }
