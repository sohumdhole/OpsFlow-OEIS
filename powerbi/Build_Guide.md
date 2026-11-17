# Power BI build guide

The pipeline writes a star schema to `powerbi/data/`. Build the report in Power BI Desktop:

1. **Get data → Text/CSV** for every file in `powerbi/data/`. Set `start`, `complete`, `first_start`, `last_complete`, `notified_at` and `date` columns to Date/Time or Date.
2. **Model view, relationships (single direction, many-to-one):**
   - `fact_task[part]` → `dim_part[part]`; `fact_case[part]` → `dim_part[part]`
   - `fact_task[resource]` → `dim_resource[resource]`
   - `fact_task[stage]` → `dim_stage[stage]`
   - `fact_task[worker_id]` → `dim_worker[worker_id]`
   - `fact_task[case_id]` → `fact_case[case_id]`
   - `fact_task[day]` → `dim_date[date]`
3. **Measures:** create a table called `_Measures` and paste each line of `measures.dax` as a new measure.
4. **Pages** (same structure as the Streamlit app):
   - *Daily board (SQDCP):* date slicer on `dim_date`; cards for Units Completed, Units Rejected, Breakdown Events, Orders With Rework.
   - *Value stream:* stacked bar of Run Hours + Setup Hours and Queue Hours by `dim_stage[stage_order]`; card for Flow Efficiency and Median Lead Time (days).
   - *Resources:* bar of Run Hours, Setup Hours and Breakdown Hours by resource.
   - *Quality:* Pareto of Units Rejected by part; Rework Rate card.
   - *Future state:* table of `fact_future_state`.
   - *Food safety:* RASFF Notifications by `hazard_category` and `year`; FSAI alerts by `failure_mode`; table of hazard → OEIS control.
5. Sort `dim_stage[stage]` by `dim_stage[stage_order]`.
