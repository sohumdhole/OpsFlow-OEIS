"""Independent recomputation of headline metrics from the silver layer."""
import pandas as pd

from opsflow.fsai import classify
from opsflow.step1_data_layer import stage_of
from opsflow.step2_value_stream import _union_minutes


def test_union_minutes_handles_overlap():
    t = pd.Timestamp
    s = [t("2012-01-01 08:00"), t("2012-01-01 09:00"), t("2012-01-01 12:00")]
    e = [t("2012-01-01 10:00"), t("2012-01-01 11:00"), t("2012-01-01 13:00")]
    assert _union_minutes(s, e) == 240


def test_lead_time_recomputed(con):
    sql = """SELECT c.case_id, c.lead_time_h,
                    date_diff('second', MIN(e.start), MAX(e.complete)) / 3600.0 AS recomputed
             FROM gold_cases c JOIN silver_production e USING (case_id) GROUP BY 1, 2"""
    df = con.execute(sql).df()
    assert (df["lead_time_h"] - df["recomputed"]).abs().max() < 1e-6


def test_median_lead_matches_audit(con, audit):
    med = con.execute("SELECT MEDIAN(lead_time_h) / 24 FROM gold_cases WHERE reached_packing").fetchone()[0]
    assert round(med, 1) == audit["value_stream"]["lead_time_median_days"]


def test_bottleneck_is_max_queue(con, audit):
    top = con.execute("SELECT stage FROM gold_stages ORDER BY queue_h DESC LIMIT 1").fetchone()[0]
    assert top == audit["value_stream"]["bottleneck_stage"]


def test_rejections_total(con, audit):
    assert con.execute("SELECT SUM(qty_rejected) FROM silver_production").fetchone()[0] == audit["value_stream"]["units_rejected_total"]


def test_rasff_pathogen_share(con, audit):
    n, p = con.execute("""SELECT COUNT(*), SUM(CASE WHEN hazard_category = 'pathogenic micro-organisms' THEN 1 ELSE 0 END)
                          FROM silver_rasff WHERE hazard_category <> 'not stated'""").fetchone()
    assert round(p / n * 100, 1) == audit["food_safety"]["pathogen_share_pct"]


def test_stage_mapping_examples():
    assert stage_of("Turning & Milling - Machine 4") == "Turning & milling"
    assert stage_of("Final Inspection Q.C.") == "Final inspection"
    assert stage_of("Turning & Milling Q.C.") == "In-process QC"
    assert stage_of("Grinding Rework - Machine 12") == "Rework"
    assert stage_of("SETUP     Turning & Milling - Machine 5") == "Setup / changeover"


def test_fsai_classifier():
    df = classify(pd.DataFrame({"title": [
        "Undeclared egg and milk in a batch of mispacked Chicken Sliders",
        "Possible presence of peanuts in chocolate",
        "Incorrectly declared wheat in fried onions",
        "Undeclared Barley in a Batch of Smoky BBQ Irish Pork Ribs",
    ]}))
    assert list(df["failure_mode"]) == ["Mispacked product", "Possible presence / cross-contact", "Incorrectly declared", "Undeclared allergen"]
    assert df.loc[0, "Eggs"] and df.loc[0, "Milk"] and not df.loc[1, "Tree nuts"] and df.loc[1, "Peanuts"]
    assert list(df["meat_product"]) == [True, False, False, True]
