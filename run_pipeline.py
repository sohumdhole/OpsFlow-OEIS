"""Run the full OpsFlow-OEIS pipeline: python run_pipeline.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import duckdb  # noqa: E402
import numpy as np  # noqa: E402

from opsflow import config as C  # noqa: E402
from opsflow import (step1_data_layer, step2_value_stream, step3_future_state,  # noqa: E402
                     step4_food_safety, step5_traceability, step6_exports, step7_docs)


def validate(audit: dict) -> list:
    """Reconciliation checks. The run fails if any check fails."""
    con = duckdb.connect(str(C.DB), read_only=True)
    q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    dq, vs, fs = audit["production_dq"], audit["value_stream"], audit["food_safety"]
    checks = [
        ("Bronze rows = silver + quarantined", dq["bronze_rows"] == dq["silver_rows"] + dq["quarantined_rows"]),
        ("Production zip MD5 matches 4TU published value", audit["provenance"]["production"]["zip_md5_matches_published"]),
        ("Silver has no negative durations", q("SELECT COUNT(*) FROM silver_production WHERE duration_min < 0") == 0),
        ("Silver has no exact duplicates", q("SELECT COUNT(*) - COUNT(DISTINCT (case_id, activity, resource, start, complete, worker_id, qty_completed, qty_rejected, report_type)) FROM silver_production") == 0),
        ("Every case has a part", q("SELECT COUNT(*) FROM gold_cases WHERE part IS NULL") == 0),
        ("Queue gaps reconcile to lead minus processing time", vs["wait_reconciliation_max_abs_error_h"] < 1e-6),
        ("Lead time >= processing time for every case", q("SELECT COUNT(*) FROM gold_cases WHERE lead_time_h + 1e-9 < processing_h") == 0),
        ("Flow efficiency within 0..1", q("SELECT COUNT(*) FROM gold_cases WHERE flow_efficiency < 0 OR flow_efficiency > 1") == 0),
        ("Stage queue shares sum to 1", abs(q("SELECT SUM(queue_share) FROM gold_stages") - 1) < 1e-9),
        ("Stage events sum to silver rows", q("SELECT SUM(events) FROM gold_stages") == dq["silver_rows"]),
        ("Rejected units: events = cases", q("SELECT SUM(qty_rejected) FROM gold_events") == q("SELECT SUM(qty_rejected) FROM gold_cases")),
        ("Report types are only B / D / S", set(dq["report_type_counts"]) <= {"B", "D", "S"}),
        ("Future-state scenarios never lengthen lead time", all(v["mean_change_pct"] <= 1e-9 for v in audit["future_state"]["scenarios"].values())),
        ("Current scenario equals measured median lead", abs(audit["future_state"]["scenarios"]["Current"]["median_lead_days"] - vs["lead_time_median_days"]) < 0.051),
        ("RASFF rows = poultry + other meat", fs["rasff_notifications"] == fs["rasff_poultry"] + fs["rasff_meat_other"]),
        ("RASFF dates all parsed", audit["rasff_dq"]["unparsed_dates"] == 0),
        ("RASFF hazard-category table sums to stated rows", q("SELECT SUM(notifications) FROM gold_rasff_hazard_categories") == fs["rasff_with_stated_hazard"]),
        ("Every RASFF hazard category has an OEIS control", fs["hazard_categories_mapped"] == fs["hazard_categories_total"]),
        ("FSAI failure modes sum to alerts", q("SELECT SUM(alerts) FROM gold_fsai_failure_modes") == fs["fsai_alerts"]),
        ("FSAI listing has no duplicate URLs", q("SELECT COUNT(*) - COUNT(DISTINCT url) FROM silver_fsai_allergen_alerts") == 0),
        ("Trace-back target is a completed order", q(f"SELECT reached_packing FROM gold_cases WHERE case_id = '{audit['traceability']['target_case']}'")),
        ("Trace-forward cases all used the traced resource", q(f"SELECT COUNT(*) FROM gold_trace_forward_example f WHERE NOT EXISTS (SELECT 1 FROM gold_events e WHERE e.case_id = f.case_id AND e.resource = '{audit['traceability']['trace_resource']}')") == 0),
        ("Power BI fact_task rows = silver rows", audit["powerbi"]["tables"]["fact_task"] == dq["silver_rows"]),
    ]
    con.close()
    return [{"check": n, "passed": bool(p)} for n, p in checks]


def main():
    audit = {"project": "OpsFlow-OEIS", "provenance": {}}
    silver, rasff, fsai = step1_data_layer.run(audit)
    ev, cases, stages, resources = step2_value_stream.run(silver, audit)
    step3_future_state.run(ev, cases, stages, audit)
    step4_food_safety.run(rasff, fsai, audit)
    step5_traceability.run(ev, cases, audit)
    step6_exports.excel_pack(audit)
    step6_exports.powerbi_export(audit)
    results = validate(audit)
    audit["validation"] = {"checks": len(results), "passed": sum(r["passed"] for r in results), "results": results}
    C.AUDIT.write_text(json.dumps(audit, indent=2, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)), encoding="utf-8")
    step7_docs.run(audit)
    failed = [r["check"] for r in results if not r["passed"]]
    print(f"{audit['validation']['passed']}/{len(results)} checks passed")
    if failed:
        print("FAILED:", *failed, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
