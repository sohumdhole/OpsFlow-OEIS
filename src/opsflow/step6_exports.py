"""Step 6: Excel KPI pack (formula-driven) and Power BI star-schema export."""
import duckdb
import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import config as C

HDR = PatternFill("solid", fgColor="1F5FA6")
WHITE = Font(color="FFFFFF", bold=True)


def _write(ws, df: pd.DataFrame):
    ws.append(list(df.columns))
    for c in ws[1]:
        c.fill, c.font = HDR, WHITE
    for row in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and pd.isna(v)) else (v.to_pydatetime() if hasattr(v, "to_pydatetime") else v) for v in row])
    for i, col in enumerate(df.columns, 1):
        ws.column_dimensions[get_column_letter(i)].width = max(12, min(45, len(str(col)) + 4))
    ws.freeze_panes = "A2"


def excel_pack(audit: dict):
    con = duckdb.connect(str(C.DB), read_only=True)
    cases = con.execute("""SELECT case_id, part, order_qty, first_start, last_complete, lead_time_h, processing_h,
                           waiting_h, flow_efficiency, qty_rejected, has_rework, has_breakdown
                           FROM gold_cases WHERE reached_packing ORDER BY case_num""").df()
    stages = con.execute("SELECT stage, events, run_h, setup_h, breakdown_h, queue_h, queue_share, median_visit_queue_h, p90_visit_queue_h, qty_rejected FROM gold_stages").df()
    daily = con.execute("SELECT * FROM gold_daily ORDER BY day").df()
    fs = con.execute("SELECT scenario, description, median_lead_days, mean_lead_days, p90_lead_days, pooled_flow_efficiency_pct FROM gold_future_state").df()
    haz = con.execute("SELECT hazard_category, notifications, share_pct, oeis_control, requirements FROM gold_rasff_hazard_categories").df()
    con.close()
    cases["has_rework"] = cases["has_rework"].map({True: "Y", False: "N"})
    cases["has_breakdown"] = cases["has_breakdown"].map({True: "Y", False: "N"})
    daily["day"] = pd.to_datetime(daily["day"]).dt.date

    wb = Workbook()
    ws = wb.active
    ws.title = "KPI"
    for name, df in [("Cases", cases), ("Stages", stages), ("Daily", daily), ("FutureState", fs), ("FoodSafety", haz)]:
        _write(wb.create_sheet(name), df)
    n = len(cases) + 1
    parts = sorted(cases["part"].unique())
    lists = wb.create_sheet("Lists")
    lists.append(["part"])
    lists.append(["(All parts)"])
    for p in parts:
        lists.append([p])

    ws["A1"] = "OpsFlow-OEIS KPI pack (completed work orders, real 4TU production log)"
    ws["A1"].font = Font(bold=True, size=14, color="1F5FA6")
    ws["A3"], ws["B3"] = "Part filter", "(All parts)"
    ws["B3"].fill = PatternFill("solid", fgColor="FFF2CC")
    dv = DataValidation(type="list", formula1=f"=Lists!$A$2:$A${len(parts) + 2}", allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B3")
    crit = 'IF($B$3="(All parts)","*",$B$3)'
    rng = lambda col: f"Cases!${col}$2:${col}${n}"  # noqa: E731
    kpis = [
        ("Completed work orders", f"=COUNTIFS({rng('B')},{crit})", "0"),
        ("Mean lead time, days", f"=AVERAGEIFS({rng('F')},{rng('B')},{crit})/24", "0.0"),
        ("Mean processing time, hours", f"=AVERAGEIFS({rng('G')},{rng('B')},{crit})", "0.0"),
        ("Pooled flow efficiency", f"=SUMIFS({rng('G')},{rng('B')},{crit})/SUMIFS({rng('F')},{rng('B')},{crit})", "0.0%"),
        ("Units rejected", f"=SUMIFS({rng('J')},{rng('B')},{crit})", "0"),
        ("Orders with rework", f"=COUNTIFS({rng('B')},{crit},{rng('K')},\"Y\")", "0"),
        ("Share of orders with rework", "=B10/B5", "0.0%"),
        ("Orders hit by a breakdown", f"=COUNTIFS({rng('B')},{crit},{rng('L')},\"Y\")", "0"),
    ]
    ws["A4"] = "KPI"
    ws["B4"] = "Value"
    ws["A4"].font = ws["B4"].font = Font(bold=True)
    for i, (label, f, fmt) in enumerate(kpis, start=5):
        ws.cell(i, 1, label)
        c = ws.cell(i, 2, f)
        c.number_format = fmt
    ws.conditional_formatting.add("B8", CellIsRule(operator="lessThan", formula=["0.15"], fill=PatternFill("solid", fgColor="F4CCCC")))

    ws["D4"] = "Daily board date"
    ws["D4"].font = Font(bold=True)
    ws["E4"] = daily["day"].iloc[len(daily) // 2]
    ws["E4"].number_format = "yyyy-mm-dd"
    ws["E4"].fill = PatternFill("solid", fgColor="FFF2CC")
    dn = len(daily) + 1
    for i, (label, col) in enumerate([("Final-inspection good units", "C"), ("Units rejected", "D"),
                                      ("Breakdowns", "E"), ("Rework events", "F"), ("Orders packed", "G")], start=5):
        ws.cell(i, 4, label)
        ws.cell(i, 5, f'=IFERROR(INDEX(Daily!${col}$2:${col}${dn},MATCH($E$4,Daily!$A$2:$A${dn},0)),"no reports")')
    ws["A15"] = "Bottleneck (largest queue share)"
    sn = len(stages) + 1
    ws["B15"] = f"=INDEX(Stages!$A$2:$A${sn},MATCH(MAX(Stages!$G$2:$G${sn}),Stages!$G$2:$G${sn},0))"
    ws["A16"] = "Its share of all queue time"
    ws["B16"] = f"=MAX(Stages!$G$2:$G${sn})"
    ws["B16"].number_format = "0.0%"
    ws["A18"] = "Lead time is calendar time (no shift calendar in the source data). Change the yellow cells."
    ws["A18"].alignment = Alignment(wrap_text=False)
    ws["A18"].font = Font(italic=True, color="666666")
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["D"].width = 28
    ws.column_dimensions["E"].width = 14
    out = C.EXCEL / "OpsFlow_OEIS_KPI_Pack.xlsx"
    wb.save(out)
    audit["excel"] = {"file": "outputs/excel/OpsFlow_OEIS_KPI_Pack.xlsx", "sheets": wb.sheetnames,
                      "completed_orders": int(len(cases)), "formula_kpis": len(kpis) + 7}
    return out


DAX = r"""// OpsFlow-OEIS DAX measures. Table names match the CSVs in powerbi/data.
// Production (fact_task = one row per production report; fact_case = one row per work order)
Work Orders = DISTINCTCOUNT ( fact_task[case_id] )
Completed Work Orders = CALCULATE ( COUNTROWS ( fact_case ), fact_case[reached_packing] = TRUE () )
Mean Lead Time (days) = CALCULATE ( AVERAGE ( fact_case[lead_time_h] ), fact_case[reached_packing] = TRUE () ) / 24
Median Lead Time (days) = CALCULATE ( MEDIAN ( fact_case[lead_time_h] ), fact_case[reached_packing] = TRUE () ) / 24
Flow Efficiency = DIVIDE ( SUM ( fact_case[processing_h] ), SUM ( fact_case[lead_time_h] ) )
Run Hours = SUMX ( FILTER ( fact_task, fact_task[report_type] = "D" ), fact_task[duration_min] ) / 60
Setup Hours = SUMX ( FILTER ( fact_task, fact_task[report_type] = "S" ), fact_task[duration_min] ) / 60
Breakdown Hours = SUMX ( FILTER ( fact_task, fact_task[report_type] = "B" ), fact_task[duration_min] ) / 60
Setup Share = DIVIDE ( [Setup Hours], [Run Hours] + [Setup Hours] )
Queue Hours = SUM ( fact_task[wait_before_min] ) / 60
Queue Share = DIVIDE ( [Queue Hours], CALCULATE ( [Queue Hours], ALL ( dim_stage ) ) )
Units Completed = SUM ( fact_task[qty_completed] )
Units Rejected = SUM ( fact_task[qty_rejected] )
Rejection Rate (inspection) =
    VAR insp = FILTER ( fact_task, fact_task[stage] IN { "In-process QC", "Final inspection" } )
    RETURN DIVIDE ( SUMX ( insp, fact_task[qty_rejected] ), SUMX ( insp, fact_task[qty_completed] + fact_task[qty_rejected] ) )
Orders With Rework = CALCULATE ( COUNTROWS ( fact_case ), fact_case[has_rework] = TRUE () )
Rework Rate = DIVIDE ( [Orders With Rework], COUNTROWS ( fact_case ) )
Breakdown Events = CALCULATE ( COUNTROWS ( fact_task ), fact_task[report_type] = "B" )

// Food safety (fact_rasff, fact_fsai)
RASFF Notifications = COUNTROWS ( fact_rasff )
RASFF Serious Share = DIVIDE ( CALCULATE ( COUNTROWS ( fact_rasff ), fact_rasff[risk_decision] = "serious" ), [RASFF Notifications] )
RASFF Ireland Involved = CALCULATE ( COUNTROWS ( fact_rasff ), fact_rasff[ireland_involved] = TRUE () )
FSAI Allergen Alerts = COUNTROWS ( fact_fsai )
FSAI Label or Pack Errors = CALCULATE ( COUNTROWS ( fact_fsai ), fact_fsai[failure_mode] IN { "Mispacked product", "Incorrectly declared", "Not labelled in English" } )
"""

GUIDE = """# Power BI build guide

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
"""


def powerbi_export(audit: dict):
    d = C.POWERBI / "data"
    d.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(C.DB), read_only=True)
    q = {
        "fact_task": "SELECT row_id, case_id, activity, stage, resource, worker_id, part, report_type, start, complete, CAST(complete AS DATE) AS day, duration_min, wait_before_min, order_qty, qty_completed, qty_rejected, qty_mrb, rework_flag FROM gold_events",
        "fact_case": "SELECT case_id, part, order_qty, first_start, last_complete, lead_time_h, processing_h, waiting_h, flow_efficiency, route, qty_rejected, has_rework, has_breakdown, reached_packing, conforms FROM gold_cases",
        "dim_part": "SELECT part, COUNT(*) AS work_orders FROM gold_cases GROUP BY part",
        "dim_resource": "SELECT resource, stage, busy_h, busy_share_of_calendar FROM gold_resources",
        "dim_worker": "SELECT DISTINCT worker_id FROM gold_events",
        "fact_future_state": "SELECT * FROM gold_future_state",
        "fact_rasff": "SELECT reference, meat_group, subject, CAST(notified_at AS DATE) AS date, year, notifying_country, classification, risk_decision, hazard, hazard_category, ireland_involved, rte_or_processed FROM gold_rasff",
        "fact_fsai": "SELECT * FROM silver_fsai_allergen_alerts",
        "dim_hazard_control": "SELECT hazard_category, oeis_control, requirements FROM gold_rasff_hazard_categories",
    }
    counts = {}
    for name, sql in q.items():
        df = con.execute(sql).df()
        df.to_csv(d / f"{name}.csv", index=False)
        counts[name] = int(len(df))
    from .step1_data_layer import STAGE_ORDER
    pd.DataFrame({"stage": STAGE_ORDER, "stage_order": range(1, len(STAGE_ORDER) + 1)}).to_csv(d / "dim_stage.csv", index=False)
    days = pd.date_range(con.execute("SELECT MIN(start) FROM gold_events").fetchone()[0].date(),
                         con.execute("SELECT MAX(complete) FROM gold_events").fetchone()[0].date())
    pd.DataFrame({"date": days.date, "week": days.isocalendar().week.values, "month": days.month_name()}).to_csv(d / "dim_date.csv", index=False)
    con.close()
    (C.POWERBI / "measures.dax").write_text(DAX, encoding="utf-8")
    (C.POWERBI / "Build_Guide.md").write_text(GUIDE, encoding="utf-8")
    audit["powerbi"] = {"tables": counts, "measures": sum(1 for line in DAX.splitlines() if " = " in line and not line.startswith("//"))}
