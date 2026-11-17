# OEIS Training and Adoption Plan

The OEIS only works if people on the floor trust it and use it every shift. This plan sets out who needs to learn what, how competence is checked, and how the business keeps the system improving after the project ends. Sequencing is decided by the project team.

## 1. Audiences and learning outcomes

| Audience | Must be able to | Format | Competence check |
|---|---|---|---|
| Operators | Start and close a batch, record yields and checks, scan or key lot numbers, flag a problem | Short hands-on sessions at the workstation, one-page quick guides with screenshots | Observed completion of a full batch record without help |
| Team leaders | Run the daily board, review exceptions, complete 5S audits, approve batch records | Hands-on session plus coaching on the first live shifts | Leads a daily meeting using live OEIS data |
| Quality / technical | Run a mock recall (trace back and forward), review CCP and allergen records, export audit evidence | Workshop using the traceability views | Completes a mock recall within the target time set by the site |
| Management | Read KPI dashboards, set targets, review the improvement log | Briefing and dashboard walk-through | Uses the dashboard in the weekly operations review |
| System super-users | Maintain master data, user access, report changes, first-line support | Detailed configuration training with the vendor or developer | Makes a controlled master-data change end to end |

## 2. Materials
- One-page quick guides per role (screenshots, no jargon).
- Standard work sheets updated to include the OEIS steps (`02_Standard_Work_SOP_Template.md`).
- A sandbox / training environment with realistic test data, so mistakes during training never touch live records.
- FAQ and issue log, reviewed weekly during roll-out.

## 3. Roll-out approach
1. Pilot on one line or product family with volunteer champions.
2. Run paper and OEIS in parallel only for the agreed pilot window, comparing records daily.
3. Fix issues from the pilot, update quick guides, then extend to the next area.
4. Retire paper records for an area only after the UAT exit criteria (`docs/UAT_Pack.md`) and the pilot review are signed off.

## 4. Keeping it alive after the project
| Routine | Frequency | Owner | Output |
|---|---|---|---|
| Daily tier meeting at the board | Every shift | Team leader | Actions with owners |
| 5S audit | Weekly per area | Team leader | Score trend on the board |
| Data-quality review (missing or late records, exceptions) | Weekly | Super-user | Exception list closed |
| KPI and target review | Monthly | Operations manager | Updated targets, improvement ideas prioritised |
| Mock recall | At the frequency the site's certification scheme requires | Quality | Trace time and completeness recorded |
| Standard work review | When process changes, at least annually | Process owner | New SOP version |

## 5. Adoption measures
- Share of batches with a complete OEIS record by end of shift.
- Share of records entered at the time of the task (not back-filled).
- Number of improvement ideas logged and closed per month.
- User feedback score from short pulse surveys at the end of the pilot and roll-out.
