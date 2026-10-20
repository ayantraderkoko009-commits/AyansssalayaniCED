"""
BrewBuzz Raw Orders - Data Cleaning Assignment
==============================================

Purpose:
    Clean the raw BrewBuzz orders CSV, sort the records, and export a cleaned CSV
    and a text report documenting each step.

How to run:
    1. Keep this script and brewbuzz_raw_orders.csv in the same folder.
    2. Install dependencies:
           python -m pip install pandas numpy
    3. Run:
           python clean_brewbuzz_orders.py

Outputs:
    brewbuzz_orders_cleaned.csv
    brewbuzz_cleaning_report.txt

Cleaning decisions:
    - Trim whitespace and standardize column names.
    - Remove exact duplicate rows.
    - Convert the text quantity "two" to 2.
    - Convert numeric fields to numeric types; invalid values become missing.
    - Impute invalid/missing unit prices using the median valid price for the same
      product, then category median as a fallback. This is documented in the report.
    - Remove rows with missing/invalid order date or quantity <= 0.
    - Normalize discount based on the promotion code: BOGO=50%, FREEPASTRY=100%,
      and no promotion=0%. These rules match the categories present in the raw file.
    - Recalculate order_total from quantity * unit_price * (1 - discount_percent/100)
      so totals are consistent with the cleaned quantity, price, and discount.
    - Keep missing customer emails blank rather than inventing personal information.
    - Remove repeated order_id values after exact duplicates, retaining the first row.
    - Sort by order_date, store_name, and order_id.
"""

from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "brewbuzz_raw_orders.csv"
OUTPUT_FILE = BASE_DIR / "brewbuzz_orders_cleaned.csv"
REPORT_FILE = BASE_DIR / "brewbuzz_cleaning_report.txt"

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Cannot find {INPUT_FILE.name}. Put it in the same folder as this script."
    )

# 1. Load the original CSV and remember its starting size.
df = pd.read_csv(INPUT_FILE, keep_default_na=True)
original_rows, original_columns = df.shape

# 2. Standardize column names and trim whitespace from text cells.
df.columns = (
    df.columns.astype(str)
    .str.strip()
    .str.lower()
    .str.replace(r"\s+", "_", regex=True)
)
for column in df.select_dtypes(include=["object"]).columns:
    df[column] = df[column].map(
        lambda value: value.strip() if isinstance(value, str) else value
    )
    df[column] = df[column].replace("", np.nan)

# 3. Remove rows that are exact copies of another row.
before = len(df)
df = df.drop_duplicates().copy()
exact_duplicates_removed = before - len(df)

# 4. Normalize common text variants and correct the known word-form quantity.
if "quantity" in df.columns:
    df["quantity"] = df["quantity"].replace(
        {"two": "2", "Two": "2", "TWO": "2"}
    )

# 5. Parse dates and numeric fields safely. Invalid strings become NaN.
if "order_date" in df.columns:
    df["order_date"] = pd.to_datetime(
        df["order_date"], errors="coerce"
    )

numeric_columns = [
    "order_id", "customer_id", "quantity", "unit_price",
    "discount_percent", "order_total"
]
for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

# 6. Standardize category and payment-method labels for consistent grouping.
for column in ["store_name", "product_name", "category", "payment_method", "promo_code"]:
    if column in df.columns:
        df[column] = df[column].astype("string").str.strip()
        df[column] = df[column].replace("", pd.NA)

# 7. Normalize promo codes and discount percentages using the observed business rules.
if "promo_code" in df.columns:
    df["promo_code"] = df["promo_code"].str.upper()
    df["discount_percent"] = np.select(
        [
            df["promo_code"].eq("BOGO").fillna(False),
            df["promo_code"].eq("FREEPASTRY").fillna(False),
        ],
        [50.0, 100.0],
        default=0.0,
    )

# 8. Flag invalid prices. Negative and unparseable prices cannot be valid sale prices.
#    Replace them with missing values, then impute from the same product's valid median.
if "unit_price" in df.columns:
    invalid_price_mask = df["unit_price"].isna() | (df["unit_price"] <= 0)
    invalid_price_rows = int(invalid_price_mask.sum())
    df.loc[df["unit_price"] <= 0, "unit_price"] = np.nan

    product_medians = df.groupby("product_name", dropna=False)["unit_price"].transform("median")
    product_impute_mask = df["unit_price"].isna() & product_medians.notna()
    product_price_imputations = int(product_impute_mask.sum())
    df.loc[product_impute_mask, "unit_price"] = product_medians[product_impute_mask]

    category_medians = df.groupby("category", dropna=False)["unit_price"].transform("median")
    category_impute_mask = df["unit_price"].isna() & category_medians.notna()
    category_price_imputations = int(category_impute_mask.sum())
    df.loc[category_impute_mask, "unit_price"] = category_medians[category_impute_mask]
else:
    invalid_price_rows = product_price_imputations = category_price_imputations = 0

# 9. Remove rows that cannot be used reliably: invalid/missing date, missing quantity,
#    quantity <= 0, missing ID, or a price that could not be imputed.
before = len(df)
valid_mask = (
    df["order_date"].notna()
    & df["order_id"].notna()
    & df["quantity"].notna()
    & (df["quantity"] > 0)
    & df["unit_price"].notna()
    & (df["unit_price"] > 0)
)
df = df.loc[valid_mask].copy()
invalid_core_rows_removed = before - len(df)

# 10. Remove repeated order IDs, keeping the first remaining valid record.
before = len(df)
df = df.drop_duplicates(subset=["order_id"], keep="first").copy()
repeated_order_ids_removed = before - len(df)

# 11. Make quantities whole numbers where appropriate.
if (df["quantity"] % 1 == 0).all():
    df["quantity"] = df["quantity"].astype("int64")

# 12. Recalculate order totals so they agree with the cleaned price, quantity and discount.
#     The raw order_total contained missing and inconsistent values.
df["order_total"] = (
    df["quantity"] * df["unit_price"] * (1 - df["discount_percent"] / 100)
).round(2)

# 13. Format dates consistently and sort records for easier review.
df["order_date"] = df["order_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
df = df.sort_values(
    ["order_date", "store_name", "order_id"],
    ascending=[True, True, True],
    na_position="last",
    kind="stable",
).reset_index(drop=True)

# 14. Export without a pandas index column.
df.to_csv(OUTPUT_FILE, index=False)

# 15. Generate an audit report documenting row counts, changes, and final missing values.
missing_counts = df.isna().sum()
remaining_missing = {str(col): int(count) for col, count in missing_counts.items() if count > 0}
report_lines = [
    "BREWBUZZ ORDERS DATA CLEANING REPORT",
    "=" * 42,
    f"Input file: {INPUT_FILE.name}",
    f"Output file: {OUTPUT_FILE.name}",
    "",
    "ROW COUNTS",
    f"Original rows: {original_rows}",
    f"Exact duplicate rows removed: {exact_duplicates_removed}",
    f"Rows removed for invalid/missing core fields: {invalid_core_rows_removed}",
    f"Repeated order IDs removed: {repeated_order_ids_removed}",
    f"Final cleaned rows: {len(df)}",
    f"Columns in cleaned file: {len(df.columns)}",
    "",
    "VALUE CLEANING",
    f"Rows with missing/invalid/non-positive unit price detected: {invalid_price_rows}",
    f"Unit prices imputed using product median: {product_price_imputations}",
    f"Unit prices imputed using category median fallback: {category_price_imputations}",
    "Quantity text 'two' normalized to 2 where present.",
    "Numeric columns converted using pandas.to_numeric(errors='coerce').",
    "Promotion rules applied: BOGO=50%, FREEPASTRY=100%, no promo=0%.",
    "order_total recalculated from quantity * unit_price * (1 - discount_percent/100).",
    "Rows sorted by order_date, store_name, and order_id.",
    "",
    "REMAINING MISSING VALUES",
]
if remaining_missing:
    report_lines.extend([f"{column}: {count}" for column, count in remaining_missing.items()])
else:
    report_lines.append("None")

report_lines.extend(["", "NUMERIC SUMMARY"])
summary_cols = [c for c in ["quantity", "unit_price", "discount_percent", "order_total"] if c in df.columns]
report_lines.append(df[summary_cols].describe().round(2).to_string())
report_lines.extend([
    "",
    "IMPORTANT NOTES",
    "- Missing customer emails are intentionally left blank rather than fabricated.",
    "- Invalid/missing dates and invalid quantities are excluded from the cleaned dataset.",
    "- Unit-price imputations use observed median prices by product, then category.",
    "- Promotion discount rules and total calculation should be confirmed with the",
    "  instructor if the assignment specifies different business rules.",
])
REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")

print("BrewBuzz data cleaning completed.")
print(f"Original shape: ({original_rows}, {original_columns})")
print(f"Cleaned shape:  {df.shape}")
print(f"Exact duplicates removed: {exact_duplicates_removed}")
print(f"Rows removed for invalid core fields: {invalid_core_rows_removed}")
print(f"Repeated order IDs removed: {repeated_order_ids_removed}")
print(f"Unit prices imputed from product median: {product_price_imputations}")
print(f"Unit prices imputed from category median: {category_price_imputations}")
print(f"Remaining missing values: {remaining_missing}")
print(f"Cleaned CSV: {OUTPUT_FILE}")
print(f"Report: {REPORT_FILE}")
