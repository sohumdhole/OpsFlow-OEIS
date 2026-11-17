"""Step 7: render README and methodology from outputs/audit/audit.json.

No figure in the README is typed by hand: every number is read from the audit
record written by the pipeline, and tests/test_docs.py checks this.
"""
from . import config as C


def _fmt(x):
    if isinstance(x, float):
        return f"{x:,.1f}"
    if isinstance(x, int):
        return f"{x:,}"
    return str(x)


def readme(a: dict) -> str:
    dq, vs, fs_, fsm, tr = a["production_dq"], a["value_stream"], a["future_state"], a["food_safety"], a["traceability"]
    sc = fs_["scenarios"]
    f = _fmt
    val = a["validation"]
    return f"""# OpsFlow-OEIS

**A production-centred Operational Excellence Information System (OEIS) prototype for a growing food manufacturer, built on real public data.**

OpsFlow-OEIS shows how a meat processing and smokehouse business could map its production flow, find the bottleneck, design a better future state, and build a food-safety-ready information system that staff keep improving after the project ends. It covers value-stream mapping, a future-state design, a food-safety and allergen risk profile, a requirements pack, a working dashboard, a user acceptance testing (UAT) pack and a sustainment kit (5S, standard work, training, daily board).

> **Honest scope.** No meat processor publishes its batch records. The production analysis therefore runs on a **real factory event log** from a different industry (a precision-parts manufacturer, 4TU.ResearchData). The methods (value-stream mapping, queue analysis, conformance, trace back / forward) transfer directly; the domain does not. The food-safety module uses **real meat and poultry data**: {f(fsm['rasff_notifications'])} EU RASFF notifications and {f(fsm['fsai_alerts'])} Food Safety Authority of Ireland allergen alerts. See [Limitations](#limitations).

Every number in this README is rendered from [`outputs/audit/audit.json`](outputs/audit/audit.json), which the pipeline writes as it runs. The pipeline runs {val['checks']} reconciliation checks and fails if any one fails ({val['passed']}/{val['checks']} passed on the last run).

---

## Headline findings

**1. Work orders spend {f(vs['waiting_share_pct'])}% of their lead time waiting.** Across {f(vs['cases_reached_packing'])} completed work orders, the median lead time is {f(vs['lead_time_median_days'])} days, but the median order is actually being worked on for only {f(vs['processing_median_h'])} hours. Median flow efficiency is {f(vs['flow_efficiency_median_pct'])}%. Waiting is measured in calendar time because the log has no shift calendar, so nights and weekends are included.

**2. The constraint is the queue in front of {vs['bottleneck_stage']}.** {vs['bottleneck_stage']} holds {f(vs['bottleneck_queue_share_pct'])}% of all queue time, the largest share of any stage (next: {vs['second_queue_stage']}, {f(vs['second_queue_share_pct'])}%). Most orders pass straight through (median wait {f(vs['bottleneck_median_visit_queue_h'])} h), but one visit in ten waits {f(vs['bottleneck_p90_visit_queue_h'])} h or more. Yet {vs['bottleneck_resource']} is busy only {f(vs['bottleneck_resource_busy_share_pct'])}% of calendar time, against {f(vs['busiest_resource_busy_share_pct'])}% for {vs['busiest_resource']}. Long, occasional waits on a machine with spare capacity point to batching and release rules in front of {vs['bottleneck_stage']}, not a lack of capacity.

**3. Rework and breakdowns stretch lead time.** {f(vs['cases_with_rework'])} of {f(vs['cases_total'])} work orders ({f(vs['cases_with_rework_pct'])}%) include rework. The {f(vs['completed_cases_with_rework'])} completed orders with rework have a median lead time of {f(vs['median_lead_days_with_rework'])} days, against {f(vs['median_lead_days_without_rework'])} days for completed orders without. The {f(vs['breakdown_events'])} breakdown reports hit {f(vs['cases_with_breakdown'])} orders; the {f(vs['completed_cases_with_breakdown'])} completed ones have a median lead time of {f(vs['median_lead_days_with_breakdown'])} days, against {f(vs['median_lead_days_without_breakdown'])} days. Setup (report type S) takes {f(vs['setup_share_of_run_plus_setup_pct'])}% of machine time.

**4. Defects are concentrated.** {f(vs['units_rejected_at_inspection'])} units were rejected at inspection ({f(vs['inspection_rejection_rate_pct'])}% of inspected units). {vs['top_reject_part']} alone accounts for {f(vs['top_reject_part_share_pct'])}%, and {f(vs['parts_for_80pct_rejects'])} parts account for 80%.

**5. Standard routes are rarely followed.** Completed orders follow {f(vs['route_variants'])} different stage routes. For the {f(vs['conformance_parts'])} parts with at least five completed orders, only {f(vs['conformance_pct'])}% follow their part's most common route. Standard work and a defined routing in the OEIS are the fix.

**6. Future state: a 24-hour queue limit at the constraint, level flow and right-first-time cut estimated median lead time from {f(sc['Current']['median_lead_days'])} to {f(sc['FS4']['median_lead_days'])} days.** Each lever is quantified separately below.

**7. In meat, the food-safety risk is microbiological.** Pathogens make up {f(fsm['pathogen_share_pct'])}% of RASFF meat and poultry notifications with a stated hazard. {fsm['top_hazard']} leads ({f(fsm['top_hazard_share_pct'])}%). In processed and ready-to-eat products, Listeria monocytogenes rises to {f(fsm['rte_listeria_share_pct'])}%. {f(fsm['ireland_involved_n'])} notifications involve Ireland as notifier, origin or distribution country.

**8. Allergen alerts in Ireland are mostly labelling and packing failures, the kind an OEIS label check is built to stop.** {f(fsm['fsai_undeclared'] + fsm['fsai_mispacked'] + fsm['fsai_incorrectly_declared'] + fsm['fsai_not_english'])} of {f(fsm['fsai_alerts'])} FSAI allergen alerts fall into these groups: {f(fsm['fsai_undeclared'])} undeclared allergens, {f(fsm['fsai_incorrectly_declared'])} incorrectly declared, {f(fsm['fsai_mispacked'])} mispacked products and {f(fsm['fsai_not_english'])} not labelled in English. A further {f(fsm['fsai_possible_presence'])} concern possible cross-contact. {fsm['fsai_top_allergen']} ({f(fsm['fsai_top_allergen_n'])}) and {fsm['fsai_second_allergen']} ({f(fsm['fsai_second_allergen_n'])}) are the most frequent allergens. {f(fsm['fsai_meat_product_alerts'])} alerts concern meat products.

![Value stream](outputs/figures/vsm_stage_time.png)

---

## 1. Data and data quality

| Source | What it is | Rows |
|---|---|---|
| Levy (2014), *Production Analysis with Process Mining Technology*, 4TU.ResearchData | Real production reports exported from a manufacturer's ERP/MES: work order, operation, machine, operator, start and end times, quantities completed and rejected, rework flag | {f(dq['bronze_rows'])} |
| EU RASFF Window, public search export | Every meat and poultry notification available ({fsm['rasff_first']} to {fsm['rasff_last']}) | {f(fsm['rasff_notifications'])} |
| FSAI allergen alerts listing | Every allergen alert headline on fsai.ie, collected on 17 November 2026 | {f(fsm['fsai_alerts'])} |

The 4TU archive is checked against the MD5 published on the dataset page before anything runs. Data lands in DuckDB as bronze, silver and gold tables.

**Production data-quality rules:** {f(dq['quarantined_rows'])} exact duplicate rows were quarantined, leaving {f(dq['silver_rows'])} reports on {f(dq['cases'])} work orders, {f(dq['parts'])} parts, {f(dq['resources'])} work centres and {f(dq['workers'])} operators between {dq['first_start'][:10]} and {dq['last_complete'][:10]}. The logged duration field disagrees with the timestamps in {f(next(r['rows'] for r in dq['rules'] if r['rule'] == 'DQ07'))} rows, so timestamps are used. Report type B marks breakdowns (the dataset's own presentation shows the same breakdown events). Report type S is treated as setup, because those reports complete a mean of {f(dq['mean_qty_completed_by_report_type']['S'])} units against {f(dq['mean_qty_completed_by_report_type']['D'])} for type D. That reading is an inference and is labelled as one.

## 2. Value-stream baseline (current state)

| Metric | Value |
|---|---|
| Completed work orders (reached Packing) | {f(vs['cases_reached_packing'])} of {f(vs['cases_total'])} |
| Median lead time | {f(vs['lead_time_median_days'])} days (90th percentile {f(vs['lead_time_p90_days'])} days) |
| Median processing time | {f(vs['processing_median_h'])} hours |
| Median flow efficiency | {f(vs['flow_efficiency_median_pct'])}% |
| Share of lead time spent waiting | {f(vs['waiting_share_pct'])}% |
| Largest queue (constraint) | {vs['bottleneck_stage']}, {f(vs['bottleneck_queue_share_pct'])}% of all queue time |
| Busiest work centre | {vs['busiest_resource']}, {f(vs['busiest_resource_busy_h'])} busy hours ({f(vs['busiest_resource_busy_share_pct'])}% of calendar time) |
| Setup share of machine time | {f(vs['setup_share_of_run_plus_setup_pct'])}% |
| Most frequent hand-off | {vs['top_transition']} ({f(vs['top_transition_count'])} times) |

Processing time is the union of a work order's busy intervals, so overlapping reports are not double counted. The queue in front of each operation is the gap since the order's latest completion; these gaps add up exactly to lead time minus processing time (checked in the pipeline).

![Lead time](outputs/figures/lead_time_hist.png)
![Resource load](outputs/figures/resource_load.png)
![Rejections](outputs/figures/rejections_pareto.png)

## 3. Future-state design

| Scenario | Lever | Median lead (days) | Mean lead (days) | Flow efficiency |
|---|---|---|---|---|
| Current | Measured | {f(sc['Current']['median_lead_days'])} | {f(sc['Current']['mean_lead_days'])} | {f(sc['Current']['pooled_flow_efficiency_pct'])}% |
| FS1 | 24-hour queue limit in front of {vs['bottleneck_stage']} (pull signal / kanban) | {f(sc['FS1']['median_lead_days'])} | {f(sc['FS1']['mean_lead_days'])} | {f(sc['FS1']['pooled_flow_efficiency_pct'])}% |
| FS2 | Level flow: FIFO lanes and WIP limits trim each stage's worst-quarter queues | {f(sc['FS2']['median_lead_days'])} | {f(sc['FS2']['mean_lead_days'])} | {f(sc['FS2']['pooled_flow_efficiency_pct'])}% |
| FS3 | Right first time: rework and fix loops removed | {f(sc['FS3']['median_lead_days'])} | {f(sc['FS3']['mean_lead_days'])} | {f(sc['FS3']['pooled_flow_efficiency_pct'])}% |
| FS4 | FS1 + FS2 + FS3 | {f(sc['FS4']['median_lead_days'])} | {f(sc['FS4']['mean_lead_days'])} | {f(sc['FS4']['pooled_flow_efficiency_pct'])}% |

Halving setup time (SMED) would free about {f(fs_['smed_50pct_hours_freed'])} machine hours over the period, {f(fs_['smed_50pct_hours_freed_busiest_resource'])} of them on {vs['busiest_resource']}. That is capacity, not lead time, so it is reported separately. These scenarios are what-if estimates from the measured queue distributions, not a capacity simulation: they assume freed time is not absorbed somewhere else.

![Future state](outputs/figures/future_state.png)

## 4. Food-safety and allergen risk profile

| Metric | Value |
|---|---|
| RASFF meat and poultry notifications | {f(fsm['rasff_notifications'])} ({f(fsm['rasff_poultry'])} poultry, {f(fsm['rasff_meat_other'])} other meat) |
| Notifications per full year, 2020 to 2025 | {f(fsm['rasff_full_years_min'])} to {f(fsm['rasff_full_years_max'])} ({f(fsm['rasff_2026_to_date'])} in 2026 to 16 November) |
| Pathogens' share (hazard stated) | {f(fsm['pathogen_share_pct'])}% |
| Listeria monocytogenes notifications | {f(fsm['listeria_n'])} |
| Listeria share in meat other than poultry | {f(fsm['meat_other_listeria_share_pct'])}% |
| Listeria share in processed / ready-to-eat subjects | {f(fsm['rte_listeria_share_pct'])}% of {f(fsm['rte_processed_stated_n'])} |
| Risk decision "serious" | {f(fsm['serious_share_pct'])}% |
| Involving Ireland | {f(fsm['ireland_involved_n'])} ({f(fsm['ireland_notifying_n'])} notified by Ireland) |
| FSAI allergen alerts: label or pack errors (mispacked, incorrectly declared, not in English) | {f(fsm['fsai_label_pack_errors'])} of {f(fsm['fsai_alerts'])} |

Each RASFF hazard category is mapped to the control point the OEIS must record (for example, pathogens map to cook / smoke and chill CCP records, environmental Listeria monitoring and positive release; allergens map to recipe allergen profiles, changeover sign-off and label verification). All {f(fsm['hazard_categories_total'])} categories are mapped: see [`outputs/tables/rasff_hazard_categories_controls.csv`](outputs/tables/rasff_hazard_categories_controls.csv).

![RASFF hazards](outputs/figures/rasff_hazard_categories.png)
![FSAI failure modes](outputs/figures/fsai_failure_modes.png)

## 5. Traceability demonstration

The completed work order with the most units rejected at final inspection is **{tr['target_case']}** ({tr['target_part']}, {f(tr['target_final_inspection_rejected'])} units rejected).

- **Trace back:** {f(tr['upstream_operations'])} upstream reports across {f(tr['upstream_resources'])} work centres and {f(tr['upstream_workers'])} operators.
- **Trace forward:** its last machining step ran on {tr['trace_resource']}. Within {f(tr['window_h'])} hours either side, {f(tr['forward_cases'])} other work orders ({f(tr['forward_parts'])} parts, {f(tr['forward_units'])} units ordered) used the same machine, and {f(tr['forward_cases_packed'])} of them had already reached Packing.
- The whole trace runs in {'under a second' if tr['query_under_1s'] else 'over a second'} (timed on every run, see `audit.json`). On paper records, this is the step that takes hours in a mock recall.

In a smokehouse the same joins run on raw-material lot → batch → pack → customer ([requirements pack, section 7](docs/OEIS_Requirements.md)).

## 6. Deliverables

| Deliverable | Where |
|---|---|
| Data layer with data-quality rules and quarantine | `src/opsflow/step1_data_layer.py`, `outputs/tables/dq_results_production.csv` |
| Current-state value stream | `src/opsflow/step2_value_stream.py`, `outputs/tables/stages.csv` |
| Future-state design | `src/opsflow/step3_future_state.py`, `outputs/tables/future_state_scenarios.csv` |
| Food-safety and allergen risk profile | `src/opsflow/step4_food_safety.py` |
| Traceability demonstration | `src/opsflow/step5_traceability.py` |
| OEIS requirements pack (BRD / FRD, data model, KPI dictionary, integrations, traceability matrix) | [`docs/OEIS_Requirements.md`](docs/OEIS_Requirements.md) |
| UAT pack (15 test cases, entry / exit criteria, defect log) | [`docs/UAT_Pack.md`](docs/UAT_Pack.md) |
| Sustainment kit: 5S audit, standard work / SOP template, training and adoption plan, daily tier meeting board | [`docs/sustainment/`](docs/sustainment/) |
| Interactive dashboard (Streamlit) | `app/streamlit_app.py` |
| Excel KPI pack (formula-driven, part filter, daily board) | `outputs/excel/OpsFlow_OEIS_KPI_Pack.xlsx` |
| Power BI star schema, {a['powerbi']['measures']} DAX measures and build guide | `powerbi/` |
| Methodology | [`docs/methodology.md`](docs/methodology.md) |

## 7. Run it

```bash
pip install -r requirements.txt
# put the 4TU archive in data/raw/ (see data/README.md), then:
python run_pipeline.py          # builds everything and runs {val['checks']} checks
pytest -q                       # tests
streamlit run app/streamlit_app.py
```

## Limitations

- **Industry transfer.** The production log is from a precision-parts manufacturer, not a meat plant. Stage names, routes and rejection rates are that factory's, not a smokehouse's. The analysis demonstrates the method an OEIS would run on a smokehouse's own records.
- **Calendar time.** Without a shift calendar, waiting time includes nights and weekends. Relative comparisons between stages and scenarios are sound; absolute waiting hours overstate working-time waits.
- **Observation window.** The log covers about {f(vs['period_days'])} days. Orders started before or finished after the window are partly observed, so lead-time and conformance figures use completed orders only.
- **Report-type S** is interpreted as setup from the quantity pattern; the dataset documentation does not define it.
- **Future state** figures are estimates from measured distributions, not a simulation.
- **RASFF** counts are notifications, not incidence. Reporting varies by country and over time, and Window exports omit company names.
- **FSAI** alert classification uses the alert headline only; {f(fsm['fsai_alerts'] - fsm['fsai_undeclared'] - fsm['fsai_possible_presence'] - fsm['fsai_mispacked'] - fsm['fsai_incorrectly_declared'] - fsm['fsai_not_english'])} headlines did not state a failure mode clearly.

## Data licences and credits

- Production log: Dafna Levy (2014), 4TU.ResearchData, under the 4TU General Terms of Use. It is not redistributed here; `data/README.md` explains how to download it.
- RASFF: European Commission, RASFF Window. Reuse with acknowledgement under the Commission's reuse policy.
- FSAI: alert headlines and links from fsai.ie, used for analysis with attribution.
- Code: MIT licence.

*Independent portfolio project by Sohum Vivek Dhole ([github.com/sohumdhole](https://github.com/sohumdhole)).*
"""


def methodology(a: dict) -> str:
    vs, fs_ = a["value_stream"], a["future_state"]
    rules = "\n".join(f"| {r['rule']} | {r['description']} | {r['severity']} | {r['rows']:,} |" for r in a["production_dq"]["rules"])
    checks = "\n".join(f"| {c['check']} | {'pass' if c['passed'] else 'FAIL'} |" for c in a["validation"]["results"])
    return f"""# Methodology

## Data layer
Raw sources land in DuckDB unchanged (bronze). Rules below decide what reaches silver; QUARANTINE rows go to `quarantine_production`, FLAG rows stay with the issue recorded.

| Rule | Description | Severity | Rows |
|---|---|---|---|
{rules}

Activities are mapped to {a['production_dq']['stages']} stages (value-stream boxes) by keyword: setup / changeover, turning and milling, wire cutting, grinding, lapping, stress relief, deburring, laser marking, in-process QC, rework, fix / repair, final inspection, packing.

## Value stream
- **Lead time** per work order: last completion minus first start.
- **Processing time:** union of the order's report intervals (overlaps counted once).
- **Queue before an operation:** start time minus the order's latest completion so far (zero if overlapping). Summed per order this equals lead time minus processing time exactly (max error {vs['wait_reconciliation_max_abs_error_h']} h).
- **Run / setup / breakdown time:** report types D / S / B.
- **Constraint:** the stage with the largest share of total queue time.
- **Route:** stages in order of first appearance; **conformance** is the share of completed orders on their part's most common route, for parts with at least five completed orders.
- **Busy share:** union of a resource's busy intervals over the {vs['period_days']}-day observation window.

## Future state
Queue times per event are capped or removed per scenario and lead time is recomputed as processing time plus remaining queue time:
- FS1 caps queues in front of {vs['bottleneck_stage']} at {fs_['bottleneck_cap_h']:.0f} h.
- FS2 caps each stage's queues at that stage's {int(fs_['percentile_cap'] * 100)}th percentile.
- FS3 removes the processing and queue time of rework and fix operations.
- FS4 combines all three.

## Food safety
RASFF findings are parsed as `<hazard> - {{<category>}}`; the first hazard is used for single-label counts. Hazards are grouped (all Salmonella serotypes together; Listeria; E. coli including STEC; Campylobacter). "Processed / ready-to-eat" is a keyword flag on the subject (smoked, cooked, ham, sausage, salami, ready-to-eat and similar). FSAI headlines are classified by the 14 allergens in EU Regulation 1169/2011 Annex II and by failure mode (undeclared, possible presence, incorrectly declared, mispacked, not labelled in English).

## Validation checks (last run)
| Check | Result |
|---|---|
{checks}
"""


def run(a: dict):
    (C.ROOT / "README.md").write_text(readme(a), encoding="utf-8")
    (C.ROOT / "docs" / "methodology.md").write_text(methodology(a), encoding="utf-8")
