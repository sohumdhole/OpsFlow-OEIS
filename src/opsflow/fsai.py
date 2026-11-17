"""Parse and classify FSAI allergen alert headlines (real, public listing)."""
import re
import pandas as pd

# EU Regulation 1169/2011 Annex II: the 14 regulated allergens
ALLERGENS = {
    "Cereals containing gluten": r"\b(?:gluten|wheat|barley|oats?|rye|spelt)\b",
    "Crustaceans": r"\b(?:crustaceans?|prawns?|shrimps?|crab|lobster)\b",
    "Eggs": r"\beggs?\b",
    "Fish": r"\bfish\b",
    "Peanuts": r"\bpeanuts?\b",
    "Soya": r"\bsoy(?:a|beans?)?\b",
    "Milk": r"\b(?:milk|dairy|lactose)\b",
    "Tree nuts": r"\b(?:nuts?|almonds?|hazelnuts?|walnuts?|cashews?|pecans?|brazil|pistachios?|macadamia)\b",
    "Celery": r"\b(?:celeriac|celery)\b",
    "Mustard": r"\bmustard\b",
    "Sesame": r"\bsesame\b",
    "Sulphites": r"\b(?:sulphites?|sulfites?|sulphur dioxide)\b",
    "Lupin": r"\blupin\b",
    "Molluscs": r"\b(?:molluscs?|mussels?|squid|oysters?)\b",
}
FAILURE_MODES = [  # first match wins, ordered from most to least specific
    ("Mispacked product", r"mis-?pack"),
    ("Not labelled in English", r"not labelled in english"),
    ("Incorrectly declared", r"incorrectly declared|incorrect(?:ly)? label"),
    ("Possible presence / cross-contact", r"possible presence|may contain|cross.?contam"),
    ("Undeclared allergen", r"undeclared|not declared|missing allergen|^presence of|unlabelled"),
]
MEAT = r"\b(?:chicken|beef|pork|ham|bacon|sausages?|salami|chorizo|turkey|lamb|duck|burgers?|meat|jerky|kebab|meatballs?|pepperoni|frankfurters?|hot dogs?|mince|gyros|doner)\b"


def classify(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    t = out["title"].str.lower()
    # "peanut" is not a tree nut: blank peanut mentions before matching tree nuts
    t_nuts = t.str.replace(r"peanuts?", " ", regex=True)
    for name, pat in ALLERGENS.items():
        src = t_nuts if name == "Tree nuts" else t
        out[name] = src.str.contains(pat, regex=True)
    out["allergen_count"] = out[list(ALLERGENS)].sum(axis=1)
    out["generic_allergens"] = t.str.contains(r"\ballergens?\b") & (out["allergen_count"] == 0)
    fm = pd.Series("Other / unspecified", index=out.index)
    for label, pat in reversed(FAILURE_MODES):
        fm = fm.mask(t.str.contains(pat, regex=True), label)
    out["failure_mode"] = fm
    out["meat_product"] = t.str.contains(MEAT, regex=True) & ~t.str.contains(r"flavour|\bbuns?\b", regex=True)
    out["is_update"] = t.str.contains(r"\bupdate\b")
    return out
