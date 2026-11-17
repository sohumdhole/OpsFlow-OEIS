"""Step 3: future-state design, quantified on the measured data.

Each scenario changes measured queue / processing times of completed work
orders and recomputes lead time as processing time + remaining queue time.
These are what-if estimates from the observed distributions. They are not a
capacity simulation: they assume the freed time is not re-absorbed elsewhere.
"""
import duckdb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config as C

BOTTLENECK_CAP_H = 24.0  # WIP / queue limit in front of the constraint: one day
PERCENTILE_CAP = 0.75    # level flow: no queue longer than the stage's 75th percentile


def _lead(case_proc_h: pd.Series, waits: pd.DataFrame) -> pd.Series:
    return case_proc_h + waits.groupby("case_id")["w_h"].sum().reindex(case_proc_h.index).fillna(0)


def run(ev: pd.DataFrame, cases: pd.DataFrame, st: pd.DataFrame, audit: dict):
    comp = cases[cases["reached_packing"]].set_index("case_id")
    e = ev[ev["case_id"].isin(comp.index)].copy()
    e["w_h"] = e["wait_before_min"] / 60
    proc = comp["processing_h"]
    base = _lead(proc, e)
    assert np.allclose(base.values, comp["lead_time_h"].values, atol=1e-6)
    bottleneck = audit["value_stream"]["bottleneck_stage"]

    scen = {}
    # FS1: queue limit in front of the constraint (pull / kanban)
    w1 = e.copy()
    m = w1["stage"] == bottleneck
    w1.loc[m, "w_h"] = w1.loc[m, "w_h"].clip(upper=BOTTLENECK_CAP_H)
    scen["FS1"] = ("Queue limit of 24 h in front of " + bottleneck + " (pull signal / kanban)", _lead(proc, w1))

    # FS2: level flow - FIFO and WIP limits trim every stage's worst-quarter queues
    w2 = e.copy()
    caps = w2.groupby("stage")["w_h"].quantile(PERCENTILE_CAP)
    w2["w_h"] = np.minimum(w2["w_h"], w2["stage"].map(caps))
    scen["FS2"] = ("Level flow: every stage queue capped at its own 75th percentile (FIFO lanes, WIP limits)", _lead(proc, w2))

    # FS3: right first time - remove rework / fix visits (their processing and the queue in front)
    rw_mask = e["stage"].isin(["Rework", "Fix / repair"])
    w3 = e.copy()
    w3.loc[rw_mask, "w_h"] = 0.0
    rw_proc = e[rw_mask].groupby("case_id")["duration_min"].sum().div(60).reindex(proc.index).fillna(0)
    proc3 = (proc - rw_proc).clip(lower=0)
    scen["FS3"] = ("Right first time: rework and fix loops removed (root-cause fixes, standard work)", _lead(proc3, w3))

    # Combined
    w4 = w2.copy()
    m4 = w4["stage"] == bottleneck
    w4.loc[m4, "w_h"] = w4.loc[m4, "w_h"].clip(upper=BOTTLENECK_CAP_H)
    w4.loc[rw_mask, "w_h"] = 0.0
    scen["FS4"] = ("Combined FS1 + FS2 + FS3", _lead(proc3, w4))

    rows = [{"scenario": "Current", "description": "Measured current state (completed work orders)",
             "median_lead_days": base.median() / 24, "mean_lead_days": base.mean() / 24,
             "p90_lead_days": base.quantile(0.9) / 24,
             "pooled_flow_efficiency_pct": proc.sum() / base.sum() * 100}]
    for k, (d, lt) in scen.items():
        p = proc3 if k in ("FS3", "FS4") else proc
        rows.append({"scenario": k, "description": d, "median_lead_days": lt.median() / 24,
                     "mean_lead_days": lt.mean() / 24, "p90_lead_days": lt.quantile(0.9) / 24,
                     "pooled_flow_efficiency_pct": p.sum() / lt.sum() * 100})
    fs = pd.DataFrame(rows)
    fs["median_change_pct"] = (fs["median_lead_days"] / fs.loc[0, "median_lead_days"] - 1) * 100
    fs["mean_change_pct"] = (fs["mean_lead_days"] / fs.loc[0, "mean_lead_days"] - 1) * 100

    # Capacity lever: setup reduction (SMED) frees machine hours, it does not shorten queues directly
    setup_h = float(st["setup_h"].sum())
    busiest = audit["value_stream"]["busiest_resource"]
    busiest_setup = float(ev.loc[(ev["resource"] == busiest) & (ev["report_type"] == "S"), "duration_min"].sum() / 60)

    fs.to_csv(C.TABLES / "future_state_scenarios.csv", index=False)
    con = duckdb.connect(str(C.DB))
    con.register("tmp", fs)
    con.execute("CREATE OR REPLACE TABLE gold_future_state AS SELECT * FROM tmp")
    con.unregister("tmp")
    con.close()

    audit["future_state"] = {
        "bottleneck_cap_h": BOTTLENECK_CAP_H, "percentile_cap": PERCENTILE_CAP,
        "scenarios": {r["scenario"]: {"median_lead_days": round(r["median_lead_days"], 1),
                                      "mean_lead_days": round(r["mean_lead_days"], 1),
                                      "p90_lead_days": round(r["p90_lead_days"], 1),
                                      "pooled_flow_efficiency_pct": round(r["pooled_flow_efficiency_pct"], 1),
                                      "median_change_pct": round(r["median_change_pct"], 1),
                                      "mean_change_pct": round(r["mean_change_pct"], 1)} for r in rows_out(fs)},
        "smed_50pct_hours_freed": round(setup_h * 0.5, 0),
        "smed_50pct_hours_freed_busiest_resource": round(busiest_setup * 0.5, 0),
    }

    fig, ax = plt.subplots(figsize=(8, 4))
    labels = ["Current", "FS1", "FS2", "FS3", "FS4"]
    vals = fs.set_index("scenario").loc[labels, "mean_lead_days"]
    ax.bar(labels, vals, color=[C.GREY, C.LIGHT, C.LIGHT, C.LIGHT, C.BLUE])
    for i, v in enumerate(vals):
        ax.text(i, v + 0.3, f"{v:.1f}", ha="center")
    ax.set_ylabel("Mean lead time, days")
    ax.set_title("Future state: estimated mean lead time by scenario", loc="left")
    fig.tight_layout()
    fig.savefig(C.FIGS / "future_state.png", dpi=150)
    plt.close(fig)
    return fs


def rows_out(fs):
    return fs.to_dict("records")
