"""
05 — Exploratory Data Analysis

Provides an initial overview of the extracted data:
- File information
- Variable names and data types
- Missing values
- Unique values
- Basic statistics
- Sample values for categorical variables
"""

from pathlib import Path

import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

EXTRACTED_DIR = Path("data/extracted")


# =============================================================================
# HELPERS
# =============================================================================

def print_section(title):
  """Print a formatted section header."""
  print()
  print("=" * 80)
  print(title)
  print("=" * 80)


def inspect_file(file_path):
  """Inspect one extracted CSV file."""
  print_section(f"FILE: {file_path.name}")

  df = pd.read_csv(file_path, low_memory=False)

  print(f"Rows       : {len(df):,}")
  print(f"Columns    : {len(df.columns):,}")
  print(f"Memory     : {df.memory_usage(deep=True).sum() / 1024**2:,.1f} MB")

  # ---------------------------------------------------------------------------
  # Variables
  # ---------------------------------------------------------------------------

  print_section("VARIABLES")

  variable_info = pd.DataFrame({
    "variable": df.columns,
    "dtype": df.dtypes.astype(str).values,
    "non_null": df.notna().sum().values,
    "missing": df.isna().sum().values,
    "missing_pct": (
      df.isna().mean().values * 100
    ).round(2),
    "unique": df.nunique(dropna=True).values,
  })

  print(variable_info.to_string(index=False))

  # ---------------------------------------------------------------------------
  # Numeric statistics
  # ---------------------------------------------------------------------------

  numeric_columns = df.select_dtypes(
    include="number"
  ).columns

  if len(numeric_columns) > 0:
    print_section("NUMERIC VARIABLES — BASIC STATISTICS")

    numeric_stats = df[numeric_columns].describe().T

    numeric_stats["missing"] = df[numeric_columns].isna().sum()
    numeric_stats["missing_pct"] = (
      df[numeric_columns].isna().mean() * 100
    ).round(2)

    print(numeric_stats.to_string())

  # ---------------------------------------------------------------------------
  # Categorical / non-numeric variables
  # ---------------------------------------------------------------------------

  categorical_columns = df.select_dtypes(
    exclude="number"
  ).columns

  if len(categorical_columns) > 0:
    print_section("CATEGORICAL VARIABLES — TOP VALUES")

    for column in categorical_columns:
      print()
      print(f"[{column}]")
      print(f"Unique values: {df[column].nunique(dropna=True):,}")

      value_counts = df[column].value_counts(
        dropna=False
      ).head(10)

      print(value_counts.to_string())

  return df


# =============================================================================
# MAIN
# =============================================================================

def main():
  print_section("EXPLORATORY DATA ANALYSIS")

  print(f"Extracted directory: {EXTRACTED_DIR}")

  csv_files = sorted(EXTRACTED_DIR.glob("*.csv"))

  if not csv_files:
    print()
    print("No CSV files found.")
    return

  print()
  print("CSV files found:")

  for file_path in csv_files:
    print(f"  - {file_path.name}")

  for file_path in csv_files:
    inspect_file(file_path)

  print()
  print("=" * 80)
  print("EDA COMPLETE")
  print("=" * 80)


if __name__ == "__main__":
  main()