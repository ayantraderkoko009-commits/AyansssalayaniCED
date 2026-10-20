"""
Supermarket Sales Data Cleaning Assignment
==========================================

Purpose:
    Clean the raw supermarket sales CSV and export a cleaned CSV plus a report.

How to run:
    1. Put this Python file and the original CSV in the same folder.
    2. Install dependencies:
           python -m pip install pandas numpy
    3. Run:
           python clean_supermarket_sales.py

Input:
    supermarket_sales_case_study (1).csv
Output:
    supermarket_sales_cleaned.csv
    cleaning_report.txt

Important data decisions:
    - Exact duplicate rows are removed.
    - Rows with Quantity <= 0 are removed because they are not valid sales quantities
      for this sales-analysis assignment.
    - Invoice ID is treated as a unique transaction key. If a non-identical repeated
      Invoice ID remains, the first valid row is retained and later repeats are removed.
    - Missing Customer type is labelled "Unknown"; this does not guess the real value.
    - Missing Date and Rating are kept blank because their correct values cannot be
      inferred reliably. The report lists these remaining missing values.
    - Numeric/date/time values are parsed and standardized. Invalid parses become blank
      and are reported rather than silently fabricated.
"""

from pathlib import Path
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# 1. Set input and output paths.
#    Path(__file__).parent means files can sit together in a local folder or
#    GitHub repository without needing a hard-coded computer-specific path.
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "supermarket_sales_case_study (1).csv"
OUTPUT_FILE = BASE_DIR / "supermarket_sales_cleaned.csv"
REPORT_FILE = BASE_DIR / "cleaning_report.txt"

# ---------------------------------------------------------------------------
# 2. Load the raw CSV and record the starting row/column counts.
#    keep_default_na=True lets pandas recognize common missing-value markers.
# ---------------------------------------------------------------------------
if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Could not find {INPUT_FILE.name}. Put the original CSV in the same "
        "folder as this script, or update INPUT_FILE in the script."
    )

df = pd.read_csv(INPUT_FILE, keep_default_na=True)
original_rows, original_columns = df.shape

# ---------------------------------------------------------------------------
# 3. Standardize column names and text values.
#    - Remove extra spaces around column names.
#    - Strip leading/trailing spaces from text cells.
#    - Convert cells containing only spaces to missing values.
# ---------------------------------------------------------------------------
df.columns = df.columns.astype(str).str.strip()

for column in df.select_dtypes(include=["object"]).columns:
    df[column] = df[column].map(
        lambda value: value.strip() if isinstance(value, str) else value
    )
    df[column] = df[column].replace("", np.nan)

# ---------------------------------------------------------------------------
# 4. Remove fully identical duplicate rows.
#    These rows add no new information.
# ---------------------------------------------------------------------------
before_exact_dedup = len(df)
df = df.drop_duplicates()
exact_duplicates_removed = before_exact_dedup - len(df)

# ---------------------------------------------------------------------------
# 5. Convert numeric columns to numeric types.
#    Any unparseable values become NaN and will be included in the report.
# ---------------------------------------------------------------------------
numeric_columns = [
    "Unit price",
    "Quantity",
    "Tax 5%",
    "Total",
    "cogs",
    "gross margin percentage",
    "gross income",
    "Rating",
]
for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

# ---------------------------------------------------------------------------
# 6. Standardize dates and times.
#    The source uses month/day/year dates. format='mixed' accepts rows that
#    may have slightly different date string formats; errors become NaT.
# ---------------------------------------------------------------------------
if "Date" in df.columns:
    df["Date"] = pd.to_datetime(
        df["Date"], format="mixed", errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    # strftime turns missing timestamps into NaN/blank values.

if "Time" in df.columns:
    parsed_time = pd.to_datetime(
        df["Time"], format="%H:%M", errors="coerce"
    )
    df["Time"] = parsed_time.dt.strftime("%H:%M")

# ---------------------------------------------------------------------------
# 7. Remove rows with invalid sales quantities.
#    Quantity must be numeric and greater than zero for this sales dataset.
# ---------------------------------------------------------------------------
if "Quantity" in df.columns:
    before_quantity_filter = len(df)
    df = df[df["Quantity"].notna() & (df["Quantity"] > 0)].copy()
    invalid_quantity_rows_removed = before_quantity_filter - len(df)
    # Convert Quantity to an integer type when all remaining values are whole numbers.
    if (df["Quantity"] % 1 == 0).all():
        df["Quantity"] = df["Quantity"].astype("int64")
else:
    invalid_quantity_rows_removed = 0

# ---------------------------------------------------------------------------
# 8. Remove remaining repeated transaction IDs.
#    Exact duplicates were already removed and invalid quantities filtered.
#    Invoice ID is treated as the unique transaction identifier. Keep the first
#    valid occurrence and report how many later repeated IDs were removed.
# ---------------------------------------------------------------------------
if "Invoice ID" in df.columns:
    before_id_dedup = len(df)
    df = df.drop_duplicates(subset=["Invoice ID"], keep="first").copy()
    repeated_invoice_rows_removed = before_id_dedup - len(df)
else:
    repeated_invoice_rows_removed = 0

# ---------------------------------------------------------------------------
# 9. Handle missing customer categories transparently.
#    Use "Unknown" rather than guessing a missing customer type.
#    Do NOT invent dates or ratings; leave those cells blank and report them.
# ---------------------------------------------------------------------------
if "Customer type" in df.columns:
    df["Customer type"] = df["Customer type"].fillna("Unknown")

# Replace infinite numeric values with missing values so calculations do not
# produce infinity. Missing numeric values remain blank in the CSV.
df.replace([np.inf, -np.inf], np.nan, inplace=True)

# ---------------------------------------------------------------------------
# 10. Sort records into a readable order.
#     Sorting by Date then Invoice ID makes the cleaned file easier to inspect.
#     Missing dates are placed last.
# ---------------------------------------------------------------------------
sort_columns = [col for col in ["Date", "Invoice ID"] if col in df.columns]
if sort_columns:
    df = df.sort_values(sort_columns, na_position="last", kind="stable")

# ---------------------------------------------------------------------------
# 11. Export the cleaned dataset.
#     index=False prevents pandas from adding an unnecessary index column.
# ---------------------------------------------------------------------------
df.to_csv(OUTPUT_FILE, index=False, date_format="%Y-%m-%d")

# ---------------------------------------------------------------------------
# 12. Create a reproducible cleaning report with row counts, missing values,
#     and numeric summaries for the assignment.
# ---------------------------------------------------------------------------
missing_counts = df.isna().sum()
remaining_missing = {
    str(column): int(count)
    for column, count in missing_counts.items()
    if count > 0
}

report_lines = [
    "SUPERMARKET SALES DATA CLEANING REPORT",
    "=" * 40,
    f"Input file: {INPUT_FILE.name}",
    f"Output file: {OUTPUT_FILE.name}",
    "",
    "ROW COUNTS",
    f"Original rows: {original_rows}",
    f"Exact duplicate rows removed: {exact_duplicates_removed}",
    f"Rows removed for missing/non-positive Quantity: {invalid_quantity_rows_removed}",
    f"Rows removed for repeated Invoice ID: {repeated_invoice_rows_removed}",
    f"Final cleaned rows: {len(df)}",
    f"Columns: {len(df.columns)}",
    "",
    "CLEANING ACTIONS",
    "1. Trimmed column names and text-cell whitespace.",
    "2. Converted empty text cells to missing values.",
    "3. Removed exact duplicate rows.",
    "4. Converted sales and rating columns to numeric types.",
    "5. Standardized Date as YYYY-MM-DD and Time as HH:MM.",
    "6. Removed rows where Quantity was missing or <= 0.",
    "7. Kept one valid row per Invoice ID.",
    '8. Replaced missing Customer type with "Unknown".',
    "9. Preserved missing Date/Rating values instead of guessing them.",
    "10. Sorted by Date and Invoice ID, then exported without an index column.",
    "",
    "REMAINING MISSING VALUES",
]
if remaining_missing:
    for column, count in remaining_missing.items():
        report_lines.append(f"{column}: {count}")
else:
    report_lines.append("None")

report_lines.extend(["", "NUMERIC SUMMARY"])
summary_columns = [
    col for col in ["Unit price", "Quantity", "Tax 5%", "Total", "cogs",
                    "gross income", "Rating"]
    if col in df.columns
]
if summary_columns:
    summary = df[summary_columns].describe().round(2)
    report_lines.append(summary.to_string())

report_lines.extend([
    "",
    "NOTES",
    "- Missing Date and Rating values are left blank because their true values cannot",
    "  be determined safely from the other columns.",
    "- Repeated Invoice IDs were treated as duplicate transactions; the first valid",
    "  row was retained. Review these rules with your instructor if a different policy",
    "  is required by the assignment.",
])

REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")

print("Data cleaning completed successfully.")
print(f"Original shape: ({original_rows}, {original_columns})")
print(f"Cleaned shape:  {df.shape}")
print(f"Exact duplicates removed: {exact_duplicates_removed}")
print(f"Invalid quantity rows removed: {invalid_quantity_rows_removed}")
print(f"Repeated Invoice ID rows removed: {repeated_invoice_rows_removed}")
print(f"Remaining missing values: {remaining_missing}")
print(f"Cleaned CSV saved to: {OUTPUT_FILE}")
print(f"Cleaning report saved to: {REPORT_FILE}")
