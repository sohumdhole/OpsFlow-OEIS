"""Step 4: food-safety and allergen risk profile for a meat / smokehouse OEIS.

Sources: EU RASFF notifications for meat and poultry (real export) and FSAI
allergen alerts (real listing). Output: hazard Pareto, trends, the processed /
ready-to-eat subset, Ireland-related notifications, allergen failure modes,
and a mapping from each hazard group to the control point the OEIS must record.
"""
import duckdb
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config as C
from .fsai import ALLERGENS

CONTROL_MAP = [
    # hazard category, OEIS control point / record, requirement IDs
    ("pathogenic micro-organisms", "Cook / smoke core-temperature CCP, chill CCP, environmental Listeria monitoring, positive release on micro results", "FR-06, FR-10, FR-11"),
    ("residues of veterinary medicinal products", "Approved-supplier list and certificate check at goods-in, lot captured", "FR-11, FR-22"),
    ("pesticide residues", "Approved-supplier list and certificate check for spices and ingredients", "FR-11, FR-22"),
    ("metals", "Supplier certificates at goods-in, lot captured for trace", "FR-11"),
    ("non-pathogenic micro-organisms", "Hygiene and chill-chain records, shelf-life verification", "FR-06"),
    ("allergens", "Recipe allergen profile, changeover sign-off, label verification at pack", "FR-07, FR-08, FR-09"),
    ("environmental pollutants", "Supplier approval and certificates", "FR-22"),
    ("organoleptic aspects", "Goods-in and pre-dispatch quality checks with hold / release", "FR-10"),
    ("foreign bodies", "Metal detection checks recorded per batch, hold on failure", "FR-06, FR-10"),
    ("foreign bodies / physical danger", "Metal detection checks recorded per batch, hold on failure", "FR-06, FR-10"),
    ("food additives and flavourings", "Recipe master data (nitrite and other additive limits), weigh-up records", "FR-02, FR-22"),
    ("composition", "Recipe master data and label verification", "FR-09, FR-22"),
    ("adulteration / fraud", "Supplier approval, lot genealogy, mass balance", "FR-11, FR-12"),
    ("fraud investigation", "Supplier approval, lot genealogy, mass balance", "FR-11, FR-12"),
    ("microbial contaminants (other)", "Hygiene, chill-chain and shelf-life records; positive release", "FR-06, FR-10"),
    ("feed additives", "Approved-supplier list and certificate check at goods-in", "FR-11, FR-22"),
    ("chemical contamination (other)", "Supplier certificates; chemical storage and cleaning records", "FR-11, FR-22"),
    ("parasitic infestation", "Goods-in inspection with hold / release", "FR-10"),
    ("faulty labelling or claims", "Label verification at pack against recipe master data", "FR-09, FR-22"),
    ("organoleptic non-compliance", "Goods-in and pre-dispatch quality checks with hold / release", "FR-10"),
    ("packaging defective / incorrect", "Pack and label checks with hold / release", "FR-09, FR-10"),
    ("mycotoxins", "Supplier certificates for spices and ingredients", "FR-22"),
    ("natural toxins (other)", "Supplier certificates for ingredients", "FR-22"),
    ("radiation", "Supplier certificates at goods-in", "FR-22"),
    ("not determined (other)", "Hold pending investigation by Quality, with release record", "FR-10"),
    ("outbreak/poisoning investigation", "Lot genealogy and rapid trace back / forward", "FR-11, FR-12"),
]


def _group_hazard(h: str) -> str:
    hl = h.lower()
    if hl.startswith("salmonella"):
        return "Salmonella (all serotypes)"
    if "listeria" in hl:
        return "Listeria monocytogenes"
    if "escherichia coli" in hl or hl.startswith("e. coli") or "stec" in hl or "shiga" in hl:
        return "E. coli (incl. STEC)"
    if "campylobacter" in hl:
        return "Campylobacter"
    if h == "not stated":
        return "Not stated"
    return h[:1].upper() + h[1:]


def run(rasff: pd.DataFrame, fsai: pd.DataFrame, audit: dict):
    r = rasff.copy()
    r["hazard_group"] = r["hazard"].map(_group_hazard)
    stated = r[r["hazard_category"] != "not stated"]

    cat = stated["hazard_category"].value_counts().rename_axis("hazard_category").reset_index(name="notifications")
    cat["share_pct"] = cat["notifications"] / len(stated) * 100
    cat["cum_share_pct"] = cat["share_pct"].cumsum()
    cmap = pd.DataFrame(CONTROL_MAP, columns=["hazard_category", "oeis_control", "requirements"])
    cat = cat.merge(cmap, on="hazard_category", how="left")
    cat["oeis_control"] = cat["oeis_control"].fillna("Reviewed case by case by Quality")
    cat["requirements"] = cat["requirements"].fillna("FR-10")

    hz = stated["hazard_group"].value_counts().rename_axis("hazard").reset_index(name="notifications")
    by_year = r[(r["year"] >= 2020)].pivot_table(index="year", columns="meat_group", values="reference", aggfunc="count").fillna(0).astype(int)
    rte = r[r["rte_or_processed"]]
    rte_stated = rte[rte["hazard_category"] != "not stated"]
    rte_hz = rte_stated["hazard_group"].value_counts()
    ie = r[r["ireland_involved"]]
    ie_hz = ie[ie["hazard_category"] != "not stated"]["hazard_group"].value_counts()
    meat_only = r[r["meat_group"] == "Meat (other than poultry)"]
    meat_stated = meat_only[meat_only["hazard_category"] != "not stated"]
    meat_hz = meat_stated["hazard_group"].value_counts()
    serious = r["risk_decision"].eq("serious")

    # FSAI allergen alerts
    fm = fsai["failure_mode"].value_counts().rename_axis("failure_mode").reset_index(name="alerts")
    al = fsai[list(ALLERGENS)].sum().sort_values(ascending=False).rename_axis("allergen").reset_index(name="alerts")
    meat_alerts = fsai[fsai["meat_product"]]

    con = duckdb.connect(str(C.DB))
    for name, frame in {"gold_rasff_hazard_categories": cat, "gold_rasff_hazards": hz,
                        "gold_rasff_by_year": by_year.reset_index(), "gold_rasff": r,
                        "gold_fsai_failure_modes": fm, "gold_fsai_allergens": al}.items():
        con.register("tmp", frame)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp")
        con.unregister("tmp")
    con.close()
    cat.to_csv(C.TABLES / "rasff_hazard_categories_controls.csv", index=False)
    hz.to_csv(C.TABLES / "rasff_hazards.csv", index=False)
    by_year.to_csv(C.TABLES / "rasff_by_year.csv")
    fm.to_csv(C.TABLES / "fsai_failure_modes.csv", index=False)
    al.to_csv(C.TABLES / "fsai_allergens.csv", index=False)
    meat_alerts[["title", "url", "failure_mode"]].to_csv(C.TABLES / "fsai_meat_product_alerts.csv", index=False)

    years_full = by_year.loc[2020:2025].sum(axis=1)
    audit["food_safety"] = {
        "rasff_notifications": int(len(r)),
        "rasff_poultry": int((r["meat_group"] == "Poultry meat").sum()),
        "rasff_meat_other": int((r["meat_group"] == "Meat (other than poultry)").sum()),
        "rasff_with_stated_hazard": int(len(stated)),
        "rasff_first": audit["rasff_dq"]["first"], "rasff_last": audit["rasff_dq"]["last"],
        "rasff_since_2020": int((r["year"] >= 2020).sum()),
        "rasff_full_years_min": int(years_full.min()), "rasff_full_years_max": int(years_full.max()),
        "rasff_2026_to_date": int((r["year"] == 2026).sum()),
        "pathogen_share_pct": round(float(cat.loc[cat["hazard_category"] == "pathogenic micro-organisms", "share_pct"].iloc[0]), 1),
        "top_hazard": hz.iloc[0]["hazard"], "top_hazard_n": int(hz.iloc[0]["notifications"]),
        "top_hazard_share_pct": round(float(hz.iloc[0]["notifications"] / len(stated) * 100), 1),
        "listeria_n": int((stated["hazard_group"] == "Listeria monocytogenes").sum()),
        "serious_share_pct": round(float(serious.mean() * 100), 1),
        "meat_other_top_hazard": meat_hz.index[0], "meat_other_top_hazard_share_pct": round(float(meat_hz.iloc[0] / len(meat_stated) * 100), 1),
        "meat_other_listeria_share_pct": round(float(meat_hz.get("Listeria monocytogenes", 0) / len(meat_stated) * 100), 1),
        "rte_processed_n": int(len(rte)),
        "rte_processed_stated_n": int(len(rte_stated)),
        "rte_top_hazard": rte_hz.index[0], "rte_top_hazard_share_pct": round(float(rte_hz.iloc[0] / len(rte_stated) * 100), 1),
        "rte_listeria_share_pct": round(float(rte_hz.get("Listeria monocytogenes", 0) / len(rte_stated) * 100), 1),
        "ireland_involved_n": int(len(ie)),
        "ireland_notifying_n": int((r["notifying_country"] == "Ireland").sum()),
        "ireland_top_hazard": ie_hz.index[0] if len(ie_hz) else "n/a",
        "allergen_category_n": int((stated["hazard_category"] == "allergens").sum()),
        "hazard_categories_mapped": int(cat["oeis_control"].ne("Reviewed case by case by Quality").sum()),
        "hazard_categories_total": int(len(cat)),
        "notifications_with_mapped_control_pct": round(float(cat.loc[cat["oeis_control"].ne("Reviewed case by case by Quality"), "notifications"].sum() / len(stated) * 100), 1),
        "fsai_alerts": int(len(fsai)),
        "fsai_undeclared": int((fsai["failure_mode"] == "Undeclared allergen").sum()),
        "fsai_possible_presence": int((fsai["failure_mode"] == "Possible presence / cross-contact").sum()),
        "fsai_mispacked": int((fsai["failure_mode"] == "Mispacked product").sum()),
        "fsai_incorrectly_declared": int((fsai["failure_mode"] == "Incorrectly declared").sum()),
        "fsai_not_english": int((fsai["failure_mode"] == "Not labelled in English").sum()),
        "fsai_label_pack_errors": int(fsai["failure_mode"].isin(["Mispacked product", "Incorrectly declared", "Not labelled in English"]).sum()),
        "fsai_top_allergen": al.iloc[0]["allergen"], "fsai_top_allergen_n": int(al.iloc[0]["alerts"]),
        "fsai_second_allergen": al.iloc[1]["allergen"], "fsai_second_allergen_n": int(al.iloc[1]["alerts"]),
        "fsai_meat_product_alerts": int(len(meat_alerts)),
        "fsai_meat_mispacked": int((meat_alerts["failure_mode"] == "Mispacked product").sum()),
    }
    _figures(cat, by_year, fm)
    return cat


def _figures(cat, by_year, fm):
    c = cat.head(8).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(c["hazard_category"], c["notifications"], color=C.BLUE)
    ax.set_xlabel("RASFF notifications (meat and poultry, hazard stated)")
    ax.set_title("What goes wrong in meat: RASFF hazard categories", loc="left")
    fig.tight_layout()
    fig.savefig(C.FIGS / "rasff_hazard_categories.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    cols = list(by_year.columns)
    bottom = None
    for col, colr in zip(cols, [C.BLUE, C.LIGHT, C.GREY]):
        ax.bar(by_year.index.astype(str), by_year[col], bottom=bottom, color=colr, label=col)
        bottom = by_year[col] if bottom is None else bottom + by_year[col]
    ax.set_ylabel("Notifications")
    ax.set_title("RASFF meat and poultry notifications per year (2026 to 16 Nov)", loc="left")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(C.FIGS / "rasff_by_year.png", dpi=150)
    plt.close(fig)

    f = fm.iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(f["failure_mode"], f["alerts"], color=C.BLUE)
    ax.set_xlabel("FSAI allergen alerts")
    ax.set_title("How allergen alerts happen in Ireland (FSAI)", loc="left")
    fig.tight_layout()
    fig.savefig(C.FIGS / "fsai_failure_modes.png", dpi=150)
    plt.close(fig)
