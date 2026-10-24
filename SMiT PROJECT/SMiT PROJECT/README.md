# Indus Weave HR pipeline

This is a reproducible SQLite implementation of the PeopleOps case study. It reads the source exports from a directory, preserves a raw copy in the database, builds cleaned staging tables and query-ready warehouse tables, writes ten result CSVs, and records data-quality checks.

## Run it

Requires Python 3.10+ and `pandas`. Install project dependencies with `python -m pip install -r requirements.txt`.

```powershell
python run_pipeline.py --input-dir "C:\path\to\the\provided\files"
```

The default input directory is `C:\Users\Lenovo\Downloads`. Each run rebuilds the database and analysis result files. The database is built as a temporary file and replaces the previous database only after a successful build; raw input files are read only. Main outputs are `indus_weave_hr.sqlite`, `load_reconciliation.csv`, `device_clock_audit.csv`, `analytics/q01.sql` through `q10.sql`, and `analytics/results/q01_result.csv` through `q10_result.csv`.

The SQLite database is a generated output and is excluded from Git because it is larger than GitHub's regular per-file upload limit. Clone the repository and run the pipeline to create it locally. The source exports must be present in the input folder; they are not included in the repository.

## Code layout

- `run_pipeline.py` reads command-line options and coordinates the build.
- `pipeline/attendance.py` cleans biometric punches, expands approved leave, and builds daily attendance.
- `pipeline/storage.py` saves staging and warehouse tables and their key constraints.
- `pipeline/analytics.py` creates the ten case-study result CSVs and companion SQL files.
- `pipeline/quality.py` writes data-quality checks and reconciliation/audit files.

Keep the `pipeline` folder beside `run_pipeline.py`; the main script imports these modules when it runs.

## Data flow

1. `raw_*` tables contain source fields as text. CSV source columns are not parsed or renamed; loader metadata is appended. JSON records are preserved as serialized payloads.
2. `staging_*` tables contain standardized employee and department data, repaired employment-history ranges, mapped and deduplicated punches, rejected unmapped punches, flattened leave requests and approvals, approved leave days, and daily attendance.
3. `warehouse_*` tables contain employee SCD2 records, department, shift and date dimensions, daily attendance, leave days, approved overtime, payroll lines, and a monthly employee mart used for the business questions.
4. Every run writes row-count reconciliation and DQ outcomes to `dq_results`.

## Key decisions

- The latest `updated_at` employee record wins. Employment history determines department, grade and salary over time; `valid_to` is derived from the next record's start date.
- Device mapping uses the composite `device_id` + `device_user_id`. Unmapped punches are retained in `staging_rejected_punches` with a rejection reason.
- Clock offsets are estimated by device from first daily punches against rostered shift starts. See `device_clock_audit.csv`; adjusted timestamps are stored in `staging_punches_clean`.
- Punches within two minutes for the same employee are collapsed. A night-shift event is assigned to the shift's start date. Attendance status follows the dictionary's priority order.
- Leave days require Manager and HR approval and no cancellation. Sundays and applicable holidays are excluded from leave-day rows.
- Monthly department attribution uses the department on the month end, or last working day when the employee separated during the month. Headcount separately follows the dictionary's month-end employment rule.
- Approved overtime comes from approved requests. Paid overtime hours come from payroll `OVERTIME` line units. Payroll cost sums `EARNING` lines.

## Read the results

Start with `analytics/results/q05_result.csv` (punch-computed vs approved vs paid overtime), `q06_result.csv` (paid overtime more than 15% above computed), `q07_result.csv` (paid employees with no attendance), and `q08_result.csv` (pay after separation). Each query also has a companion SQL file. `presentation/cfo_findings.md` summarizes the strongest patterns and actions.

The CFO note is a data-driven draft, not a claim about real company performance; all records are synthetic. The case asks teams to explain the code in the demo, so review the transformations and SQL before presenting.
