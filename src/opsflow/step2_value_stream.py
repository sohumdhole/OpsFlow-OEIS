"""Step 2: current-state value stream on the real production log.

Per work order (case): lead time, processing time (union of busy intervals),
waiting time, flow efficiency. Per stage: run time, setup time (report type S),
queue time in front of the stage, visits, rejections. Per resource: busy share
of the observed calendar. Plus rework, breakdowns, variants and conformance.

Note: the log has no shift calendar, so waiting time is calendar time and
includes nights and weekends. This is stated wherever the figures are used.
"""
import duckdb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config as C
from .step1_data_layer import STAGE_ORDER

H = 60.0  # minutes per hour


def _union_minutes(starts, ends) -> float:
    iv = sorted(zip(starts, ends))
    total, cur_s, cur_e = 0.0, None, None
    for s, e in iv:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += (cur_e - cur_s).total_seconds() / 60
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += (cur_e - cur_s).total_seconds() / 60
    return total


def event_waits(ev: pd.DataFrame) -> pd.DataFrame:
    """Queue time in front of each event: gap since the case's latest completion so far."""
    out = []
    for _, g in ev.sort_values(["case_num", "start", "complete", "row_id"]).groupby("case_num", sort=False):
        latest = None
        for idx, row in g.iterrows():
            wait = 0.0 if latest is None else max(0.0, (row["start"] - latest).total_seconds() / 60)
            out.append((idx, wait))
            latest = row["complete"] if latest is None else max(latest, row["complete"])
    w = pd.Series(dict(out))
    ev = ev.copy()
    ev["wait_before_min"] = w
    return ev


def collapse(seq):
    out = []
    for s in seq:
        if not out or out[-1] != s:
            out.append(s)
    return out


def run(ev: pd.DataFrame, audit: dict):
    ev = event_waits(ev)

    # ---- case level
    rows = []
    for (cid, cnum), g in ev.groupby(["case_id", "case_num"]):
        lead = (g["complete"].max() - g["start"].min()).total_seconds() / 60
        proc = _union_minutes(g["start"], g["complete"])
        ordered = list(g.sort_values(["start", "complete", "row_id"])["stage"])
        stages = collapse(ordered)
        first_seen = []
        for x in ordered:
            if x not in first_seen:
                first_seen.append(x)
        good = g.loc[g["stage"].isin(["Final inspection"]), "qty_completed"].sum()
        rows.append({
            "case_id": cid, "case_num": cnum, "part": g["part"].iloc[0], "order_qty": int(g["order_qty"].max()),
            "first_start": g["start"].min(), "last_complete": g["complete"].max(),
            "lead_time_h": lead / H, "processing_h": proc / H, "waiting_h": (lead - proc) / H,
            "flow_efficiency": proc / lead if lead > 0 else np.nan,
            "events": len(g), "stages_visited": len(set(stages)), "route": " > ".join(first_seen),
            "route_full": " > ".join(stages),
            "qty_rejected": int(g["qty_rejected"].sum()), "qty_mrb": int(g["qty_mrb"].sum()),
            "qty_final_inspected_good": int(good),
            "has_rework": bool(g["rework_flag"].any() or (g["stage"] == "Rework").any()),
            "has_breakdown": bool((g["report_type"] == "B").any()),
            "reached_packing": bool((g["stage"] == "Packing").any()),
            "loops": len(stages) - len(set(stages)),
        })
    cases = pd.DataFrame(rows).sort_values("case_num").reset_index(drop=True)
    # sanity: sum of queue gaps equals lead minus processing (calendar)
    wait_check = ev.groupby("case_id")["wait_before_min"].sum() / H
    merged = cases.set_index("case_id")["waiting_h"].reindex(wait_check.index)
    max_gap_err = float((merged - wait_check).abs().max())

    # ---- stage level
    ev["run_min"] = np.where(ev["report_type"] == "D", ev["duration_min"], 0.0)
    ev["setup_min"] = np.where(ev["report_type"] == "S", ev["duration_min"], 0.0)
    ev["breakdown_min"] = np.where(ev["report_type"] == "B", ev["duration_min"], 0.0)
    st = ev.groupby("stage").agg(
        events=("row_id", "size"), cases=("case_id", "nunique"),
        run_h=("run_min", lambda s: s.sum() / H), setup_h=("setup_min", lambda s: s.sum() / H),
        breakdown_h=("breakdown_min", lambda s: s.sum() / H),
        queue_h=("wait_before_min", lambda s: s.sum() / H),
        median_queue_h=("wait_before_min", lambda s: s.median() / H),
        qty_completed=("qty_completed", "sum"), qty_rejected=("qty_rejected", "sum"),
    )
    st["queue_share"] = st["queue_h"] / st["queue_h"].sum()
    st["rejection_rate"] = st["qty_rejected"] / (st["qty_completed"] + st["qty_rejected"]).replace(0, np.nan)
    st["setup_share_of_busy"] = st["setup_h"] / (st["run_h"] + st["setup_h"] + st["breakdown_h"]).replace(0, np.nan)
    st = st.reindex([s for s in STAGE_ORDER if s in st.index])
    # queue per visit (case-stage), using first event in each consecutive visit
    ev_sorted = ev.sort_values(["case_num", "start", "complete", "row_id"])
    ev_sorted["visit"] = (ev_sorted["stage"] != ev_sorted.groupby("case_num")["stage"].shift()).cumsum()
    visits = ev_sorted.groupby("visit").agg(case_id=("case_id", "first"), stage=("stage", "first"),
                                             queue_h=("wait_before_min", lambda s: s.iloc[0] / H))
    vq = visits.groupby("stage")["queue_h"].agg(["count", "median", "mean", lambda s: s.quantile(0.9)])
    vq.columns = ["visits", "median_visit_queue_h", "mean_visit_queue_h", "p90_visit_queue_h"]
    st = st.join(vq)
    bottleneck = st["queue_h"].idxmax()

    # ---- resource level
    span_h = (ev["complete"].max() - ev["start"].min()).total_seconds() / 3600
    res = []
    for r, g in ev.groupby("resource"):
        busy = _union_minutes(g["start"], g["complete"]) / H
        res.append({"resource": r, "stage": g["stage"].mode().iloc[0], "events": len(g),
                    "busy_h": busy, "busy_share_of_calendar": busy / span_h,
                    "breakdown_events": int((g["report_type"] == "B").sum()),
                    "breakdown_h": g.loc[g["report_type"] == "B", "duration_min"].sum() / H,
                    "setup_h": g.loc[g["report_type"] == "S", "duration_min"].sum() / H,
                    "qty_rejected": int(g["qty_rejected"].sum())})
    resources = pd.DataFrame(res).sort_values("busy_h", ascending=False).reset_index(drop=True)

    # ---- quality: rejections by part and by stage, rework comparison
    inspect = ev[ev["stage"].isin(["In-process QC", "Final inspection"])]
    rej_part = inspect.groupby("part").agg(inspected=("qty_completed", "sum"), rejected=("qty_rejected", "sum"))
    rej_part["rejection_rate"] = rej_part["rejected"] / (rej_part["inspected"] + rej_part["rejected"]).replace(0, np.nan)
    rej_part = rej_part.sort_values("rejected", ascending=False)
    total_rej = int(ev["qty_rejected"].sum())
    rej_part["cum_share"] = rej_part["rejected"].cumsum() / max(total_rej_insp := int(rej_part["rejected"].sum()), 1)

    rw = cases.groupby("has_rework")["lead_time_h"].median()
    bd = cases.groupby("has_breakdown")["lead_time_h"].median()

    # ---- variants and conformance (stage-level route per part)
    done = cases[cases["reached_packing"]]
    dom = (done.groupby(["part", "route"]).size().rename("n").reset_index()
           .sort_values(["part", "n"], ascending=[True, False]).drop_duplicates("part"))
    dom = dom.rename(columns={"route": "dominant_route", "n": "dominant_n"})
    part_n = done.groupby("part").size().rename("part_cases")
    dom = dom.merge(part_n, on="part")
    cases = cases.merge(dom[["part", "dominant_route", "part_cases"]], on="part", how="left")
    eligible = cases["reached_packing"] & (cases["part_cases"] >= 5)
    cases["conforms"] = np.where(eligible, cases["route"] == cases["dominant_route"], np.nan)
    conf_rate = float(cases.loc[eligible, "conforms"].mean())
    n_variants = int(cases["route"].nunique())

    # directly-follows at stage level
    dfg = []
    for _, g in ev_sorted.groupby("case_num"):
        s = collapse(list(g["stage"]))
        dfg += list(zip(s[:-1], s[1:]))
    dfg = pd.Series(dfg).value_counts().rename_axis("transition").reset_index(name="count")
    dfg[["from_stage", "to_stage"]] = pd.DataFrame(dfg["transition"].tolist(), index=dfg.index)
    dfg = dfg.drop(columns="transition")

    # ---- daily production for daily board
    ev["day"] = ev["complete"].dt.normalize()
    daily = ev.groupby("day").agg(
        events=("row_id", "size"), good_units_final=("qty_completed", lambda s: s[ev.loc[s.index, "stage"] == "Final inspection"].sum()),
        rejected=("qty_rejected", "sum"), breakdowns=("report_type", lambda s: (s == "B").sum()),
        rework_events=("stage", lambda s: (s == "Rework").sum()),
        orders_packed=("stage", lambda s: (s == "Packing").sum()),
    ).reset_index()

    # ---- persist
    con = duckdb.connect(str(C.DB))
    for name, frame in {"gold_events": ev.drop(columns=["day"]), "gold_cases": cases, "gold_stages": st.reset_index(),
                        "gold_resources": resources, "gold_rejections_by_part": rej_part.reset_index(),
                        "gold_dfg": dfg, "gold_daily": daily}.items():
        con.register("tmp", frame)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp")
        con.unregister("tmp")
    con.close()
    cases.to_csv(C.TABLES / "cases.csv", index=False)
    st.reset_index().to_csv(C.TABLES / "stages.csv", index=False)
    resources.to_csv(C.TABLES / "resources.csv", index=False)
    rej_part.reset_index().to_csv(C.TABLES / "rejections_by_part.csv", index=False)
    dfg.to_csv(C.TABLES / "directly_follows.csv", index=False)
    daily.to_csv(C.TABLES / "daily.csv", index=False)

    bn = st.loc[bottleneck]
    comp = cases[cases["reached_packing"]]
    rw = comp.groupby("has_rework")["lead_time_h"].median()
    bd = comp.groupby("has_breakdown")["lead_time_h"].median()
    top_res = resources.iloc[0]
    audit["value_stream"] = {
        "period_days": round(span_h / 24, 1),
        "lead_time_median_h": round(float(comp["lead_time_h"].median()), 1),
        "lead_time_median_days": round(float(comp["lead_time_h"].median()) / 24, 1),
        "lead_time_p90_days": round(float(comp["lead_time_h"].quantile(0.9)) / 24, 1),
        "processing_median_h": round(float(comp["processing_h"].median()), 1),
        "flow_efficiency_median_pct": round(float(comp["flow_efficiency"].median()) * 100, 1),
        "flow_efficiency_pooled_pct": round(float(comp["processing_h"].sum() / comp["lead_time_h"].sum()) * 100, 1),
        "waiting_share_pct": round(float(comp["waiting_h"].sum() / comp["lead_time_h"].sum()) * 100, 1),
        "wait_reconciliation_max_abs_error_h": round(max_gap_err, 6),
        "bottleneck_stage": bottleneck,
        "bottleneck_queue_share_pct": round(float(bn["queue_share"]) * 100, 1),
        "bottleneck_queue_h": round(float(bn["queue_h"]), 0),
        "bottleneck_median_visit_queue_h": round(float(bn["median_visit_queue_h"]), 1),
        "bottleneck_p90_visit_queue_h": round(float(bn["p90_visit_queue_h"]), 1),
        "bottleneck_resource": resources.loc[resources["stage"] == bottleneck].iloc[0]["resource"],
        "bottleneck_resource_busy_share_pct": round(float(resources.loc[resources["stage"] == bottleneck].iloc[0]["busy_share_of_calendar"]) * 100, 1),
        "second_queue_stage": st["queue_h"].drop(bottleneck).idxmax(),
        "second_queue_share_pct": round(float(st["queue_share"].drop(bottleneck).max()) * 100, 1),
        "busiest_resource": top_res["resource"], "busiest_resource_busy_h": round(float(top_res["busy_h"]), 0),
        "busiest_resource_busy_share_pct": round(float(top_res["busy_share_of_calendar"]) * 100, 1),
        "setup_h_total": round(float(st["setup_h"].sum()), 0),
        "run_h_total": round(float(st["run_h"].sum()), 0),
        "setup_share_of_run_plus_setup_pct": round(float(st["setup_h"].sum() / (st["setup_h"].sum() + st["run_h"].sum())) * 100, 1),
        "breakdown_events": int((ev["report_type"] == "B").sum()),
        "breakdown_h": round(float(st["breakdown_h"].sum()), 1),
        "cases_with_breakdown": int(cases["has_breakdown"].sum()),
        "median_lead_days_with_breakdown": round(float(bd.get(True, np.nan)) / 24, 1),
        "median_lead_days_without_breakdown": round(float(bd.get(False, np.nan)) / 24, 1),
        "cases_with_rework": int(cases["has_rework"].sum()),
        "cases_with_rework_pct": round(float(cases["has_rework"].mean()) * 100, 1),
        "median_lead_days_with_rework": round(float(rw.get(True, np.nan)) / 24, 1),
        "median_lead_days_without_rework": round(float(rw.get(False, np.nan)) / 24, 1),
        "units_rejected_total": total_rej, "units_rejected_at_inspection": total_rej_insp,
        "units_mrb_total": int(ev["qty_mrb"].sum()),
        "inspection_rejection_rate_pct": round(float(rej_part["rejected"].sum() / (rej_part["inspected"].sum() + rej_part["rejected"].sum())) * 100, 2),
        "top_reject_part": rej_part.index[0], "top_reject_part_units": int(rej_part["rejected"].iloc[0]),
        "top_reject_part_share_pct": round(float(rej_part["rejected"].iloc[0] / max(total_rej_insp, 1)) * 100, 1),
        "parts_for_80pct_rejects": int((rej_part["cum_share"] < 0.8).sum() + 1),
        "route_variants": n_variants,
        "conformance_pct": round(conf_rate * 100, 1),
        "conformance_eligible_cases": int(eligible.sum()),
        "conformance_parts": int((part_n >= 5).sum()),
        "cases_with_loops": int((cases["loops"] > 0).sum()),
        "cases_reached_packing": int(cases["reached_packing"].sum()),
        "cases_total": int(len(cases)),
        "completed_cases_with_rework": int(comp["has_rework"].sum()),
        "completed_cases_with_breakdown": int(comp["has_breakdown"].sum()),
        "top_transition": f"{dfg.iloc[0]['from_stage']} > {dfg.iloc[0]['to_stage']}",
        "top_transition_count": int(dfg.iloc[0]["count"]),
    }

    _figures(comp, st, resources, rej_part)
    return ev, cases, st, resources


def _figures(comp, st, resources, rej_part):
    cases = comp
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    # 1. value stream: queue vs run+setup per stage
    s = st[st["events"] > 0].copy()
    fig, ax = plt.subplots(figsize=(9, 5))
    y = np.arange(len(s))
    ax.barh(y, s["run_h"] + s["setup_h"], color=C.BLUE, label="Processing (run + setup)")
    ax.barh(y, s["queue_h"], left=s["run_h"] + s["setup_h"], color=C.LIGHT, label="Queue in front of stage (calendar)")
    ax.set_yticks(y, s.index)
    ax.invert_yaxis()
    ax.set_xlabel("Hours, summed over all work orders")
    ax.set_title("Current-state value stream: where work orders spend their time", loc="left")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(C.FIGS / "vsm_stage_time.png", dpi=150)
    plt.close(fig)
    # 2. lead time distribution
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(cases["lead_time_h"] / 24, bins=30, color=C.BLUE)
    ax.axvline(cases["lead_time_h"].median() / 24, color=C.ACCENT, lw=2, label="Median")
    ax.set_xlabel("Lead time, days (first start to last completion)")
    ax.set_ylabel("Work orders")
    ax.set_title("Lead time per completed work order", loc="left")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(C.FIGS / "lead_time_hist.png", dpi=150)
    plt.close(fig)
    # 3. resource load
    r = resources.head(12)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(r["resource"], r["busy_h"], color=C.BLUE)
    ax.invert_yaxis()
    ax.set_xlabel("Busy hours in the period")
    ax.set_title("Resource load: busiest 12 work centres", loc="left")
    fig.tight_layout()
    fig.savefig(C.FIGS / "resource_load.png", dpi=150)
    plt.close(fig)
    # 4. rejection pareto by part
    rp = rej_part.head(10)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(rp.index, rp["rejected"], color=C.BLUE)
    ax2 = ax.twinx()
    ax2.plot(rp.index, rp["cum_share"] * 100, color=C.ACCENT, marker="o")
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("Cumulative share, %")
    ax2.spines["top"].set_visible(False)
    ax.set_ylabel("Units rejected at inspection")
    ax.set_title("Rejected units by part (Pareto)", loc="left")
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    fig.tight_layout()
    fig.savefig(C.FIGS / "rejections_pareto.png", dpi=150)
    plt.close(fig)
