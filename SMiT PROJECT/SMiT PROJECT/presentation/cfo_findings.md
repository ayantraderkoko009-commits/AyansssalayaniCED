# CFO briefing: overtime is rising while recorded work is falling

All figures cover the synthetic April–September 2026 case data. The comparison uses punch-computed overtime after device correction, punch deduplication, and shift pairing, alongside approved request hours and payroll overtime units.

## Finding 1: The overtime bill rose as punch-computed overtime fell

Paid overtime increased from **5,525.5 hours in April to 6,418.5 in September** (+16.2%). Overtime earnings rose from **PKR 2.81 million to PKR 3.48 million** (+23.5%). Over the same months, punch-computed overtime fell from **7,829.5 to 5,963.5 hours** (-23.8%). This divergence means the cost increase is not explained by additional overtime visible in the corrected punch records alone. **Action:** require a monthly plant and department reconciliation of punch-computed, approved, and paid hours before payroll close.

Evidence: `analytics/q05.sql`; `analytics/results/q05_result.csv`.

## Finding 2: Stitching has the largest approval-to-punch gap

Across the six months, Stitching had **7,659 approved and paid overtime hours** against **4,830 punch-computed hours**. The gap is **2,829 hours**, with paid hours **58.6% above** computed overtime. **Action:** sample approved requests against corrected punch pairs and shift rosters, then review recurring requests, staffing levels, and approval practices in Stitching.

Evidence: `analytics/q05.sql` and `analytics/q06.sql`; department and month detail is in `analytics/results/q05_result.csv` and `q06_result.csv`.

## Finding 3: Five recurring exceptions warrant a payroll control

There are **5 department-months** where paid overtime exceeds punch-computed overtime by more than 15%; all are in Stitching, ranging from **18.2% in May to 141.3% in September**. Approved and paid overtime hours match exactly in the supplied data, so the gap appears before payroll calculation, between punch-derived work and approved requests. **Action:** add an exception report at payroll close, require an explanation and secondary approval above the 15% threshold, and monitor monthly exceptions until the gap narrows.

Evidence: `analytics/q06.sql`; exceptions are listed in `analytics/results/q06_result.csv`.

## Five-minute demo flow

1. **Problem and method (45 sec):** show how separate exports were reconciled from raw data into daily attendance and an analytics warehouse.
2. **Trust checks (60 sec):** explain the one-hour device correction on `DEV-SITE-01` (median first punch was 51.6 minutes later than expected; adjusted by -60 minutes), duplicate-punch handling, and unmapped-punch rejection.
3. **Trend (75 sec):** compare April with September in Q5: payroll cost rose while punch-computed overtime fell.
4. **Hotspot and action (75 sec):** show Stitching's 58.6% six-month gap and the five department-month exceptions, including September's 141.3% gap.
5. **Close (45 sec):** propose an exception gate and focused Stitching review; invite questions.

## Presenter caveat

These are synthetic case-study findings. Punch-computed overtime depends on roster assignment and paired biometric events; the adjustment and quality checks are documented in `device_clock_audit.csv` and the database `dq_results` table. Explain those assumptions during Q&A.
