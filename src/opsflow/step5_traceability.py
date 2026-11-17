"""Step 5: traceability demonstration on the real production log.

Trace back: for the completed work order with the most units rejected at final
inspection, list every upstream operation with its machine, operator and time.
Trace forward: from that order's last machining operation, find every other
work order that ran on the same machine within +/- 24 hours (the exposure
window a quality team would check first), and whether it had reached Packing.

In a smokehouse the same joins run on raw-material lot -> batch -> pack -> customer
(see docs/OEIS_Requirements.md, section 7). Here the real data provides the
batch -> machine / operator / time-window part of that path.
"""
import time

import duckdb
import pandas as pd

from . import config as C

WINDOW_H = 24
MACHINING = {"Turning & milling", "Grinding", "Lapping", "Wire cutting"}


def trace_back(ev: pd.DataFrame, case_id: str) -> pd.DataFrame:
    g = ev[ev["case_id"] == case_id].sort_values(["start", "complete", "row_id"])
    return g[["case_id", "part", "activity", "stage", "resource", "worker_id", "report_type", "start", "complete",
              "qty_completed", "qty_rejected"]]


def trace_forward(ev: pd.DataFrame, resource: str, t0, t1, exclude_case=None) -> pd.DataFrame:
    hit = ev[(ev["resource"] == resource) & (ev["start"] <= t1) & (ev["complete"] >= t0)]
    if exclude_case is not None:
        hit = hit[hit["case_id"] != exclude_case]
    packed = ev[ev["stage"] == "Packing"].groupby("case_id")["complete"].min()
    out = (hit.groupby(["case_id", "part"]).agg(events_on_resource=("row_id", "size"),
                                                 first_on_resource=("start", "min"),
                                                 last_on_resource=("complete", "max"),
                                                 order_qty=("order_qty", "max"))
           .reset_index())
    out["packed_at"] = out["case_id"].map(packed)
    out["reached_packing"] = out["packed_at"].notna()
    return out.sort_values("first_on_resource")


def run(ev: pd.DataFrame, cases: pd.DataFrame, audit: dict):
    fi = ev[ev["stage"] == "Final inspection"].groupby("case_id")["qty_rejected"].sum()
    comp = set(cases.loc[cases["reached_packing"], "case_id"])
    fi = fi[fi.index.isin(comp)]
    target = fi.sort_values(ascending=False, kind="stable").index[0]

    t_start = time.perf_counter()
    back = trace_back(ev, target)
    mach = back[back["stage"].isin(MACHINING) & (back["report_type"] == "D")]
    last = mach.iloc[-1]
    t0 = last["start"] - pd.Timedelta(hours=WINDOW_H)
    t1 = last["complete"] + pd.Timedelta(hours=WINDOW_H)
    fwd = trace_forward(ev, last["resource"], t0, t1, exclude_case=target)
    elapsed_ms = (time.perf_counter() - t_start) * 1000

    back.to_csv(C.TABLES / "trace_back_example.csv", index=False)
    fwd.to_csv(C.TABLES / "trace_forward_example.csv", index=False)
    con = duckdb.connect(str(C.DB))
    for name, frame in {"gold_trace_back_example": back, "gold_trace_forward_example": fwd}.items():
        con.register("tmp", frame)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp")
        con.unregister("tmp")
    con.close()

    audit["traceability"] = {
        "target_case": target, "target_part": back["part"].iloc[0],
        "target_final_inspection_rejected": int(fi.loc[target]),
        "upstream_operations": int(len(back)),
        "upstream_resources": int(back["resource"].nunique()),
        "upstream_workers": int(back["worker_id"].nunique()),
        "trace_resource": last["resource"], "trace_worker": last["worker_id"],
        "window_h": WINDOW_H, "window_start": str(t0), "window_end": str(t1),
        "forward_cases": int(len(fwd)), "forward_parts": int(fwd["part"].nunique()) if len(fwd) else 0,
        "forward_cases_packed": int(fwd["reached_packing"].sum()) if len(fwd) else 0,
        "forward_units": int(fwd["order_qty"].sum()) if len(fwd) else 0,
        "query_ms": round(elapsed_ms, 1),
        "query_under_1s": bool(elapsed_ms < 1000),
    }
    return back, fwd
