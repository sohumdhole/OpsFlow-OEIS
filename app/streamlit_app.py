"""OpsFlow-OEIS dashboard: streamlit run app/streamlit_app.py

Reads the tables the pipeline writes to outputs/tables and powerbi/data.
The interactive trace tab also needs outputs/opsflow.duckdb, which is created
locally by `python run_pipeline.py` (the event-level production log is not
redistributed in this repository).
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs" / "tables"
BLUE, LIGHT, ACCENT, GREY = "#1F5FA6", "#9DB9DA", "#D9822B", "#8A8F98"

st.set_page_config(page_title="OpsFlow-OEIS", layout="wide")


@st.cache_data
def load():
    a = json.loads((ROOT / "outputs" / "audit" / "audit.json").read_text(encoding="utf-8"))
    d = {n: pd.read_csv(T / f"{n}.csv") for n in [
        "cases", "stages", "resources", "rejections_by_part", "daily", "future_state_scenarios",
        "rasff_hazard_categories_controls", "rasff_hazards", "rasff_by_year", "fsai_failure_modes",
        "fsai_allergens", "fsai_meat_product_alerts", "trace_back_example", "trace_forward_example",
        "directly_follows"]}
    d["daily"]["day"] = pd.to_datetime(d["daily"]["day"]).dt.date
    return a, d


a, d = load()
vs, fsm, tr = a["value_stream"], a["food_safety"], a["traceability"]

st.title("OpsFlow-OEIS")
st.caption("Production-centred Operational Excellence Information System prototype. Production data: real factory log "
           "(4TU, precision parts, 2012). Food safety: real EU RASFF meat and poultry notifications and FSAI allergen alerts.")

tabs = st.tabs(["Daily board", "Value stream", "Resources & quality", "Future state", "Food safety", "Traceability", "About"])

# ---------------- Daily board (SQDCP)
with tabs[0]:
    daily = d["daily"]
    day = st.select_slider("Shift date", options=list(daily["day"]), value=daily["day"].iloc[len(daily) // 2])
    row = daily[daily["day"] == day].iloc[0]
    prev = daily[daily["day"] < day].tail(7)
    c = st.columns(5)
    c[0].metric("Safety / food safety", "No data", help="Incident and CCP records are captured by the OEIS (FR-06); the source log has none.")
    c[1].metric("Quality: units rejected", int(row["rejected"]), delta=f"{int(row['rejected'] - prev['rejected'].mean()) if len(prev) else 0} vs 7-day avg", delta_color="inverse")
    c[2].metric("Delivery: orders packed", int(row["orders_packed"]))
    c[3].metric("Cost: breakdowns", int(row["breakdowns"]), delta_color="inverse")
    c[4].metric("Improvement: rework events", int(row["rework_events"]), delta_color="inverse")
    fig = px.bar(daily, x="day", y="good_units_final", title="Final-inspection good units per day",
                 color_discrete_sequence=[BLUE])
    fig.add_vline(x=str(day), line_color=ACCENT)
    st.plotly_chart(fig, width="stretch")
    st.info("Agenda and rules for the 15-minute stand-up are in docs/sustainment/04_Daily_Tier_Meeting_Board.md.")

# ---------------- Value stream
with tabs[1]:
    c = st.columns(4)
    c[0].metric("Median lead time", f"{vs['lead_time_median_days']} days")
    c[1].metric("Median processing time", f"{vs['processing_median_h']} h")
    c[2].metric("Median flow efficiency", f"{vs['flow_efficiency_median_pct']}%")
    c[3].metric("Constraint (largest queue)", vs["bottleneck_stage"], f"{vs['bottleneck_queue_share_pct']}% of queue time", delta_color="off")
    s = d["stages"].copy()
    s["processing_h"] = s["run_h"] + s["setup_h"]
    long = s.melt(id_vars="stage", value_vars=["processing_h", "queue_h"], var_name="type", value_name="hours")
    long["type"] = long["type"].map({"processing_h": "Processing (run + setup)", "queue_h": "Queue in front (calendar)"})
    fig = px.bar(long, y="stage", x="hours", color="type", orientation="h", barmode="stack",
                 color_discrete_sequence=[BLUE, LIGHT], title="Where work orders spend their time")
    fig.update_yaxes(categoryorder="array", categoryarray=list(s["stage"])[::-1])
    st.plotly_chart(fig, width="stretch")
    cases = d["cases"]
    comp = cases[cases["reached_packing"]]
    part = st.selectbox("Part", ["All"] + sorted(comp["part"].unique()))
    sub = comp if part == "All" else comp[comp["part"] == part]
    fig = px.histogram(sub, x=sub["lead_time_h"] / 24, nbins=30, color_discrete_sequence=[BLUE],
                       labels={"x": "Lead time, days"}, title=f"Lead time, completed orders ({len(sub)})")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(d["directly_follows"].head(15), width="stretch", hide_index=True)

# ---------------- Resources & quality
with tabs[2]:
    r = d["resources"].head(15)
    fig = px.bar(r, y="resource", x=["busy_h", "setup_h", "breakdown_h"], orientation="h", barmode="group",
                 color_discrete_sequence=[BLUE, LIGHT, ACCENT], title="Busy, setup and breakdown hours by work centre")
    fig.update_yaxes(categoryorder="total ascending")
    st.plotly_chart(fig, width="stretch")
    rp = d["rejections_by_part"].head(12)
    fig = px.bar(rp, x="part", y="rejected", color_discrete_sequence=[BLUE], title="Units rejected at inspection by part")
    st.plotly_chart(fig, width="stretch")
    c = st.columns(3)
    c[0].metric("Orders with rework", f"{vs['cases_with_rework']} ({vs['cases_with_rework_pct']}%)")
    c[1].metric("Median lead, rework vs none", f"{vs['median_lead_days_with_rework']} vs {vs['median_lead_days_without_rework']} days")
    c[2].metric("Setup share of machine time", f"{vs['setup_share_of_run_plus_setup_pct']}%")

# ---------------- Future state
with tabs[3]:
    fs = d["future_state_scenarios"]
    fig = px.bar(fs, x="scenario", y="mean_lead_days", text=fs["mean_lead_days"].round(1),
                 color="scenario", color_discrete_sequence=[GREY, LIGHT, LIGHT, LIGHT, BLUE],
                 title="Estimated mean lead time by scenario (days)")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(fs.round(1), width="stretch", hide_index=True)
    st.caption("What-if estimates from measured queue distributions, not a capacity simulation.")

# ---------------- Food safety
with tabs[4]:
    c = st.columns(4)
    c[0].metric("RASFF meat and poultry notifications", f"{fsm['rasff_notifications']:,}")
    c[1].metric("Pathogens' share", f"{fsm['pathogen_share_pct']}%")
    c[2].metric("Listeria share, processed / RTE", f"{fsm['rte_listeria_share_pct']}%")
    c[3].metric("Involving Ireland", fsm["ireland_involved_n"])
    by = d["rasff_by_year"].melt(id_vars="year", var_name="group", value_name="notifications")
    fig = px.bar(by, x="year", y="notifications", color="group", color_discrete_sequence=[BLUE, LIGHT],
                 title="Notifications per year (2026 to 16 November)")
    st.plotly_chart(fig, width="stretch")
    st.subheader("Hazard → OEIS control point")
    st.dataframe(d["rasff_hazard_categories_controls"][["hazard_category", "notifications", "oeis_control", "requirements"]],
                 width="stretch", hide_index=True)
    col1, col2 = st.columns(2)
    col1.plotly_chart(px.bar(d["fsai_failure_modes"], y="failure_mode", x="alerts", orientation="h",
                             color_discrete_sequence=[BLUE], title="FSAI allergen alerts by failure mode"), width="stretch")
    col2.plotly_chart(px.bar(d["fsai_allergens"], y="allergen", x="alerts", orientation="h",
                             color_discrete_sequence=[BLUE], title="FSAI allergen alerts by allergen"), width="stretch")
    st.dataframe(d["fsai_meat_product_alerts"], width="stretch", hide_index=True)

# ---------------- Traceability
with tabs[5]:
    st.markdown(f"**Worked example:** {tr['target_case']} ({tr['target_part']}) had {tr['target_final_inspection_rejected']} units "
                f"rejected at final inspection. Its last machining step ran on **{tr['trace_resource']}**.")
    st.write("Trace back: every upstream operation")
    st.dataframe(d["trace_back_example"], width="stretch", hide_index=True)
    st.write(f"Trace forward: other orders on the same machine within {tr['window_h']} h either side")
    st.dataframe(d["trace_forward_example"], width="stretch", hide_index=True)
    db = ROOT / "outputs" / "opsflow.duckdb"
    st.subheader("Run your own trace")
    if db.exists():
        import duckdb
        con = duckdb.connect(str(db), read_only=True)
        res = [x[0] for x in con.execute("SELECT DISTINCT resource FROM gold_events ORDER BY 1").fetchall()]
        rsel = st.selectbox("Machine / work centre", res, index=res.index(tr["trace_resource"]) if tr["trace_resource"] in res else 0)
        dsel = st.date_input("Suspect day", value=pd.to_datetime(tr["window_start"]).date())
        hrs = st.slider("Window either side (hours)", 0, 72, tr["window_h"])
        t0 = pd.Timestamp(dsel) - pd.Timedelta(hours=hrs)
        t1 = pd.Timestamp(dsel) + pd.Timedelta(days=1, hours=hrs)
        hit = con.execute("""SELECT e.case_id, e.part, COUNT(*) AS reports, MIN(e.start) AS first_on_machine,
                                    MAX(e.complete) AS last_on_machine, MAX(e.order_qty) AS order_qty,
                                    BOOL_OR(c.reached_packing) AS reached_packing
                             FROM gold_events e JOIN gold_cases c USING (case_id)
                             WHERE e.resource = ? AND e.start <= ? AND e.complete >= ?
                             GROUP BY 1, 2 ORDER BY first_on_machine""", [rsel, t1, t0]).df()
        st.write(f"{len(hit)} work orders exposed")
        st.dataframe(hit, width="stretch", hide_index=True)
        con.close()
    else:
        st.warning("Run `python run_pipeline.py` locally to enable interactive tracing (needs the 4TU archive in data/raw).")

# ---------------- About
with tabs[6]:
    st.markdown((ROOT / "README.md").read_text(encoding="utf-8").split("## 1. Data")[0])
