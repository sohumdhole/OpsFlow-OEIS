# User Acceptance Testing (UAT) Pack

Test scripts for the OEIS requirements in `docs/OEIS_Requirements.md`. Each case is written so an operator, team leader or quality user can run it in the training environment without help. A case passes only if every expected result is met; any failure is logged with severity and re-tested after the fix.

## Entry criteria
- Requirements pack signed off; configuration complete in the test environment.
- Test data loaded: products with allergen profiles, equipment, users per role, at least one open production order.
- Testers trained on the quick guides.

## Exit criteria
- All **Must** cases pass; no open Severity 1 or 2 defects.
- Should / Could failures have an agreed workaround and owner.
- Business owner (Operations) and Quality sign off.

## Severity
| Level | Meaning |
|---|---|
| 1 | Food safety, traceability or data loss risk; blocks go-live |
| 2 | Core task cannot be completed; blocks go-live |
| 3 | Task possible with a workaround |
| 4 | Cosmetic |

## Test cases

| ID | Req | Role | Steps | Expected result | Pri |
|---|---|---|---|---|---|
| UAT-01 | FR-01, FR-03 | Operator | Scan order, start task at workstation, finish it | Start / finish times recorded by system; operator and workstation captured; task visible to team leader | M |
| UAT-02 | FR-02 | Operator | Enter input 100.0 kg, output 92.5 kg, scrap 1.0 kg | Yield 92.5% calculated and stored; values cannot be saved if output exceeds input | M |
| UAT-03 | FR-19 | Operator | Try to finish a task before it is started; try a lot number that does not exist | Both rejected with a clear message; nothing saved | M |
| UAT-04 | FR-21 | Super-user | Run the weekly data-quality check | Exceptions list shows missing finishes, negative durations and orphan lots with an owner | S |
| UAT-05 | FR-06 | Quality | Record a failed CCP value with no corrective action, then try to release the batch | Release blocked until a corrective action is recorded and approved | M |
| UAT-06 | FR-07 | Team leader | Schedule an allergen-containing product before an allergen-free one on the same line | Warning raised; changeover step added to the plan | M |
| UAT-07 | FR-08, FR-09 | Operator | Start next product without changeover sign-off; scan a label from a different batch | Start blocked without sign-off; label mismatch blocks packing and is logged | M |
| UAT-08 | FR-10 | Quality | Place batch on hold, attempt dispatch, then release | Dispatch blocked while on hold; release records reason and approver | M |
| UAT-09 | FR-11, FR-12 | Quality | Run trace for one raw-material lot and for one machine plus time window | Report lists every batch, pack and customer affected, within the site's target time | M |
| UAT-10 | FR-14 | Ops manager | Compare dashboard yield for one day with a manual calculation from batch records | Values match exactly | M |
| UAT-11 | FR-15 | Team leader | Open daily board at shift start | SQDCP page shows previous shift data, refreshed before the meeting | M |
| UAT-12 | FR-16 | Ops manager | Open value-stream view for last week | Processing time, waiting time and WIP shown per step; totals reconcile to batch lead times | S |
| UAT-13 | FR-17 | Team leader | Enter a 5S audit and an improvement idea | Score trend and idea log update | S |
| UAT-14 | FR-18 | Ops manager | Review non-conforming route list | Batches that skip or repeat steps listed with the deviation | C |
| UAT-15 | FR-20 | Super-user | Edit a saved weight, then view audit trail | Old value, new value, user and time recorded | M |

## Defect log
| ID | UAT case | Severity | Description | Owner | Status | Re-test date |
|---|---|---|---|---|---|---|
| | | | | | | |

## Sign-off
| Role | Name | Decision | Date |
|---|---|---|---|
| Operations owner | | | |
| Quality | | | |
| Project manager | | | |
