# Methodology

## Data layer
Raw sources land in DuckDB unchanged (bronze). Rules below decide what reaches silver; QUARANTINE rows go to `quarantine_production`, FLAG rows stay with the issue recorded.

| Rule | Description | Severity | Rows |
|---|---|---|---|
| DQ01 | Start or complete timestamp missing / unparseable | QUARANTINE | 0 |
| DQ02 | Complete timestamp earlier than start | QUARANTINE | 0 |
| DQ03 | Exact duplicate of an earlier report row | QUARANTINE | 22 |
| DQ04 | Quantity field missing or negative | QUARANTINE | 0 |
| DQ05 | Worker ID missing | QUARANTINE | 0 |
| DQ06 | Span field malformed (not HHH:MM) | FLAG | 1 |
| DQ07 | Span field disagrees with timestamps by more than 1 minute (timestamps used) | FLAG | 699 |
| DQ08 | Zero-duration report | FLAG | 9 |
| DQ09 | Rejected quantity exceeds work order quantity | FLAG | 0 |

Activities are mapped to 13 stages (value-stream boxes) by keyword: setup / changeover, turning and milling, wire cutting, grinding, lapping, stress relief, deburring, laser marking, in-process QC, rework, fix / repair, final inspection, packing.

## Value stream
- **Lead time** per work order: last completion minus first start.
- **Processing time:** union of the order's report intervals (overlaps counted once).
- **Queue before an operation:** start time minus the order's latest completion so far (zero if overlapping). Summed per order this equals lead time minus processing time exactly (max error 0.0 h).
- **Run / setup / breakdown time:** report types D / S / B.
- **Constraint:** the stage with the largest share of total queue time.
- **Route:** stages in order of first appearance; **conformance** is the share of completed orders on their part's most common route, for parts with at least five completed orders.
- **Busy share:** union of a resource's busy intervals over the 89.2-day observation window.

## Future state
Queue times per event are capped or removed per scenario and lead time is recomputed as processing time plus remaining queue time:
- FS1 caps queues in front of Lapping at 24 h.
- FS2 caps each stage's queues at that stage's 75th percentile.
- FS3 removes the processing and queue time of rework and fix operations.
- FS4 combines all three.

## Food safety
RASFF findings are parsed as `<hazard> - {<category>}`; the first hazard is used for single-label counts. Hazards are grouped (all Salmonella serotypes together; Listeria; E. coli including STEC; Campylobacter). "Processed / ready-to-eat" is a keyword flag on the subject (smoked, cooked, ham, sausage, salami, ready-to-eat and similar). FSAI headlines are classified by the 14 allergens in EU Regulation 1169/2011 Annex II and by failure mode (undeclared, possible presence, incorrectly declared, mispacked, not labelled in English).

## Validation checks (last run)
| Check | Result |
|---|---|
| Bronze rows = silver + quarantined | pass |
| Production zip MD5 matches 4TU published value | pass |
| Silver has no negative durations | pass |
| Silver has no exact duplicates | pass |
| Every case has a part | pass |
| Queue gaps reconcile to lead minus processing time | pass |
| Lead time >= processing time for every case | pass |
| Flow efficiency within 0..1 | pass |
| Stage queue shares sum to 1 | pass |
| Stage events sum to silver rows | pass |
| Rejected units: events = cases | pass |
| Report types are only B / D / S | pass |
| Future-state scenarios never lengthen lead time | pass |
| Current scenario equals measured median lead | pass |
| RASFF rows = poultry + other meat | pass |
| RASFF dates all parsed | pass |
| RASFF hazard-category table sums to stated rows | pass |
| Every RASFF hazard category has an OEIS control | pass |
| FSAI failure modes sum to alerts | pass |
| FSAI listing has no duplicate URLs | pass |
| Trace-back target is a completed order | pass |
| Trace-forward cases all used the traced resource | pass |
| Power BI fact_task rows = silver rows | pass |
