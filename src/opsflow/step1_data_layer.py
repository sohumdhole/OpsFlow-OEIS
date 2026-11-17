"""Step 1: data layer.

Loads the three real sources, verifies provenance, applies data-quality rules
with a quarantine table, and writes bronze / silver / gold tables to DuckDB.
"""
import hashlib
import io
import re
import zipfile

import duckdb
import pandas as pd

from . import config as C
from .fsai import classify as classify_fsai


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def stage_of(activity: str) -> str:
    """Map a raw activity name to a process stage (value-stream box)."""
    a = activity.lower()
    if "setup" in a or "change version" in a:
        return "Setup / changeover"
    if "rework" in a:
        return "Rework"
    if a.startswith("fix"):
        return "Fix / repair"
    if "final inspection" in a:
        return "Final inspection"
    if "q.c." in a:
        return "In-process QC"
    if "packing" in a:
        return "Packing"
    if "turn" in a or "milling" in a:
        return "Turning & milling"
    if "grinding" in a:
        return "Grinding"
    if "lapping" in a:
        return "Lapping"
    if "laser" in a:
        return "Laser marking"
    if "wire cut" in a:
        return "Wire cutting"
    if "deburr" in a:
        return "Deburring"
    if "stress relief" in a:
        return "Stress relief"
    return "Other"


STAGE_ORDER = [
    "Setup / changeover", "Turning & milling", "Wire cutting", "Grinding", "Lapping",
    "Stress relief", "Deburring", "Laser marking", "In-process QC", "Rework",
    "Fix / repair", "Final inspection", "Packing", "Other",
]


def load_production(audit: dict) -> pd.DataFrame:
    raw = C.PRODUCTION_ZIP.read_bytes()
    md5 = hashlib.md5(raw).hexdigest()
    if md5 != C.PRODUCTION_ZIP_MD5:
        raise ValueError(f"4TU zip MD5 {md5} does not match published {C.PRODUCTION_ZIP_MD5}")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        csv_bytes = z.read(C.PRODUCTION_CSV_IN_ZIP)
    audit["provenance"]["production"] = {
        "source": "Levy, D. (2014). Production Analysis with Process Mining Technology. 4TU.ResearchData. https://doi.org/10.4121/uuid:68726926-5ac5-4fab-b873-ee76ea412399",
        "zip_md5": md5, "zip_md5_matches_published": True,
        "csv_sha256": _sha256(csv_bytes),
    }
    df = pd.read_csv(io.BytesIO(csv_bytes), dtype=str)
    df.columns = [re.sub(r"\s+", " ", c).strip() for c in df.columns]
    return df


def clean_production(bronze: pd.DataFrame, audit: dict):
    df = bronze.copy()
    df.insert(0, "row_id", range(1, len(df) + 1))
    df["start"] = pd.to_datetime(df["Start Timestamp"], format="%Y/%m/%d %H:%M:%S.%f", errors="coerce")
    df["complete"] = pd.to_datetime(df["Complete Timestamp"], format="%Y/%m/%d %H:%M:%S.%f", errors="coerce")
    for c in ["Work Order Qty", "Qty Completed", "Qty Rejected", "Qty for MRB"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["duration_min"] = (df["complete"] - df["start"]).dt.total_seconds() / 60

    span_ok = df["Span"].fillna("").str.match(r"^\d+:\d\d$")
    span_min = pd.Series(pd.NA, index=df.index, dtype="Float64")
    parts = df.loc[span_ok, "Span"].str.split(":", expand=True).astype(int)
    span_min.loc[span_ok] = parts[0] * 60 + parts[1]

    rules = []  # (rule_id, description, severity, mask)  severity: QUARANTINE or FLAG
    rules.append(("DQ01", "Start or complete timestamp missing / unparseable", "QUARANTINE",
                  df["start"].isna() | df["complete"].isna()))
    rules.append(("DQ02", "Complete timestamp earlier than start", "QUARANTINE", df["duration_min"] < 0))
    dup = df.drop(columns=["row_id"]).duplicated(keep="first")
    rules.append(("DQ03", "Exact duplicate of an earlier report row", "QUARANTINE", dup))
    rules.append(("DQ04", "Quantity field missing or negative", "QUARANTINE",
                  df[["Work Order Qty", "Qty Completed", "Qty Rejected", "Qty for MRB"]].isna().any(axis=1)
                  | (df[["Work Order Qty", "Qty Completed", "Qty Rejected", "Qty for MRB"]] < 0).any(axis=1)))
    rules.append(("DQ05", "Worker ID missing", "QUARANTINE", df["Worker ID"].isna()))
    rules.append(("DQ06", "Span field malformed (not HHH:MM)", "FLAG", ~span_ok))
    rules.append(("DQ07", "Span field disagrees with timestamps by more than 1 minute (timestamps used)", "FLAG",
                  span_ok & ((span_min - df["duration_min"]).abs() > 1).fillna(False)))
    rules.append(("DQ08", "Zero-duration report", "FLAG", df["duration_min"] == 0))
    rules.append(("DQ09", "Rejected quantity exceeds work order quantity", "FLAG",
                  df["Qty Rejected"] > df["Work Order Qty"]))

    results, q_mask = [], pd.Series(False, index=df.index)
    for rid, desc, sev, m in rules:
        m = m.fillna(False).astype(bool)
        results.append({"rule": rid, "description": desc, "severity": sev, "rows": int(m.sum())})
        if sev == "QUARANTINE":
            q_mask |= m
    quarantine = df[q_mask].copy()
    quarantine["reasons"] = [
        ";".join(r for r, _, s, m in rules if s == "QUARANTINE" and bool(m.fillna(False).iloc[i]))
        for i in range(len(df)) if q_mask.iloc[i]
    ]
    silver = df[~q_mask].copy()
    silver["stage"] = silver["Activity"].map(stage_of)
    silver["report_type"] = silver["Report Type"]
    silver["rework_flag"] = silver["Rework"].eq("Y")
    silver = silver.rename(columns={
        "Case ID": "case_id", "Activity": "activity", "Resource": "resource", "Part Desc.": "part",
        "Worker ID": "worker_id", "Work Order Qty": "order_qty", "Qty Completed": "qty_completed",
        "Qty Rejected": "qty_rejected", "Qty for MRB": "qty_mrb",
    })
    silver["case_num"] = silver["case_id"].str.extract(r"(\d+)").astype(int)
    keep = ["row_id", "case_id", "case_num", "activity", "stage", "resource", "worker_id", "part", "report_type",
            "start", "complete", "duration_min", "order_qty", "qty_completed", "qty_rejected", "qty_mrb", "rework_flag"]
    silver = silver[keep].sort_values(["case_num", "start", "complete", "row_id"]).reset_index(drop=True)

    audit["production_dq"] = {
        "bronze_rows": int(len(df)), "silver_rows": int(len(silver)), "quarantined_rows": int(q_mask.sum()),
        "rules": results, "cases": int(silver["case_id"].nunique()),
        "parts": int(silver["part"].nunique()), "activities": int(silver["activity"].nunique()),
        "resources": int(silver["resource"].nunique()), "workers": int(silver["worker_id"].nunique()),
        "stages": int(silver["stage"].nunique()),
        "first_start": str(silver["start"].min()), "last_complete": str(silver["complete"].max()),
        "report_type_counts": {k: int(v) for k, v in silver["report_type"].value_counts().items()},
        "mean_qty_completed_by_report_type": {k: round(float(v), 2) for k, v in silver.groupby("report_type")["qty_completed"].mean().items()},
    }
    return silver, quarantine, pd.DataFrame(results)


def load_rasff(audit: dict) -> pd.DataFrame:
    raw = C.RASFF_CSV.read_bytes()
    df = pd.read_csv(io.BytesIO(raw), escapechar="\\", dtype=str)
    audit["provenance"]["rasff"] = {
        "source": "European Commission, RASFF Window public search (https://webgate.ec.europa.eu/rasff-window/screen/search), product categories 'meat and meat products (other than poultry)' and 'poultry meat and poultry meat products', CSV export",
        "exported": "2026-11-17", "csv_sha256": _sha256(raw), "rows": int(len(df)),
    }
    return df


def clean_rasff(df: pd.DataFrame, audit: dict) -> pd.DataFrame:
    r = df.copy()
    r["notified_at"] = pd.to_datetime(r["date"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
    r["year"] = r["notified_at"].dt.year
    # findings can hold several hazards: "<hazard> - {<hazard category>}, ..."
    pairs = r["findings"].fillna("").apply(lambda s: re.findall(r"(.*?)\s+-\s+\{(.*?)\}\s*,?", s))
    r["hazard_category"] = pairs.apply(lambda p: p[0][1].strip() if p else "not stated")
    r["hazard"] = pairs.apply(lambda p: re.sub(r"\s+", " ", p[0][0]).strip(" ,") if p else "not stated")
    r["hazard_count"] = pairs.apply(len)
    r["ireland_involved"] = (
        r["notifying_country"].fillna("").str.contains("Ireland")
        | r["origin"].fillna("").str.contains("Ireland")
        | r["distribution"].fillna("").str.contains("Ireland")
    )
    r["meat_group"] = r["category"].map({
        "meat and meat products (other than poultry)": "Meat (other than poultry)",
        "poultry meat and poultry meat products": "Poultry meat",
    }).fillna(r["category"])
    subj = r["subject"].fillna("").str.lower()
    r["rte_or_processed"] = subj.str.contains(
        r"ready[- ]to[- ]eat|\brte\b|smoked|cooked|\bham\b|sausage|salami|chorizo|bacon|pâté|pate\b|kebab|frankfurter|\bdeli\b|cured|dried meat|jerky|pastrami|salted|marinated")
    audit["rasff_dq"] = {
        "rows": int(len(r)), "unparsed_dates": int(r["notified_at"].isna().sum()),
        "missing_findings": int(r["findings"].isna().sum()),
        "multi_hazard_rows": int((r["hazard_count"] > 1).sum()),
        "first": str(r["notified_at"].min().date()), "last": str(r["notified_at"].max().date()),
    }
    cols = ["reference", "meat_group", "type", "subject", "notified_at", "year", "notifying_country", "origin",
            "distribution", "classification", "risk_decision", "hazard", "hazard_category", "hazard_count",
            "ireland_involved", "rte_or_processed"]
    return r[cols]


def load_fsai(audit: dict) -> pd.DataFrame:
    raw = C.FSAI_CSV.read_bytes()
    df = pd.read_csv(io.BytesIO(raw))
    audit["provenance"]["fsai"] = {
        "source": "Food Safety Authority of Ireland, allergen alerts listing (https://www.fsai.ie/news-alerts/allergens), all listing pages, collected 2026-11-17; first and last pages checked against the live site",
        "csv_sha256": _sha256(raw), "rows": int(len(df)), "pages": int(df["page"].max()),
    }
    return classify_fsai(df)


def run(audit: dict):
    audit.setdefault("provenance", {})
    prod_bronze = load_production(audit)
    prod_silver, prod_quarantine, dq = clean_production(prod_bronze, audit)
    rasff_bronze = load_rasff(audit)
    rasff = clean_rasff(rasff_bronze, audit)
    fsai = load_fsai(audit)

    con = duckdb.connect(str(C.DB))
    for name, frame in {
        "bronze_production": prod_bronze, "silver_production": prod_silver,
        "quarantine_production": prod_quarantine, "dq_results_production": dq,
        "bronze_rasff": rasff_bronze, "silver_rasff": rasff, "silver_fsai_allergen_alerts": fsai,
    }.items():
        con.register("tmp", frame)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp")
        con.unregister("tmp")
    con.close()
    dq.to_csv(C.TABLES / "dq_results_production.csv", index=False)
    prod_quarantine.to_csv(C.TABLES / "quarantine_production.csv", index=False)
    return prod_silver, rasff, fsai
