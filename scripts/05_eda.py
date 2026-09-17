"""
05 — Exploratory Data Analysis

Provides an initial overview of the extracted data and evaluates
whether the datasets are ready for transformation and analysis.

Sections:
- Dataset Overview
- Structure
- Dimension Profile
- Date / Time Coverage
- Data Grain / Key Check
- Value & Unit Semantics
- Missing / Data Quality
- Industry Compatibility
- Analysis Readiness
"""

from pathlib import Path

import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

EXTRACTED_DIR = Path("data/extracted")

ANALYSIS_START = "2021-01"
ANALYSIS_END = "2025-12"

DATASET_CONFIG = {
  "14100022_extracted.csv": {
    "measure_column": "Labour force characteristics",
    "key_columns": [
      "REF_DATE",
      "GEO",
      "NAICS",
      "Labour force characteristics",
      "Gender",
      "Age group",
    ],
  },
  "14100063_extracted.csv": {
    "measure_column": "Wages",
    "key_columns": [
      "REF_DATE",
      "GEO",
      "NAICS",
      "Wages",
      "Type of work",
      "Gender",
      "Age group",
    ],
  },
  "14100372_extracted.csv": {
    "measure_column": "Statistics",
    "key_columns": [
      "REF_DATE",
      "GEO",
      "NAICS",
      "Statistics",
    ],
  },
}


# =============================================================================
# HELPERS
# =============================================================================

def print_section(title):
  """Print a formatted section header."""
  print()
  print("=" * 80)
  print(title)
  print("=" * 80)


def print_subsection(title):
  """Print a smaller subsection header."""
  print()
  print(f"[{title}]")


def get_date_profile(df):
  """Return basic information about the REF_DATE column."""
  dates = pd.to_datetime(
    df["REF_DATE"],
    format="%Y-%m",
    errors="coerce",
  )

  return {
    "min": dates.min().strftime("%Y-%m") if dates.notna().any() else "N/A",
    "max": dates.max().strftime("%Y-%m") if dates.notna().any() else "N/A",
    "unique": dates.nunique(),
    "invalid": dates.isna().sum(),
  }


def get_analysis_period_profile(df):
  """Check coverage of the target analysis period."""
  dates = pd.to_datetime(
    df["REF_DATE"],
    format="%Y-%m",
    errors="coerce",
  )

  start = pd.Period(ANALYSIS_START, freq="M")
  end = pd.Period(ANALYSIS_END, freq="M")

  analysis_dates = dates[
    (dates.dt.to_period("M") >= start)
    & (dates.dt.to_period("M") <= end)
  ]

  expected_months = pd.period_range(
    start=start,
    end=end,
    freq="M",
  )

  actual_months = set(
    analysis_dates.dt.to_period("M").dropna().unique()
  )

  missing_months = [
    str(month)
    for month in expected_months
    if month not in actual_months
  ]

  return {
    "expected": len(expected_months),
    "available": len(actual_months),
    "missing": missing_months,
  }


def profile_dimensions(df):
  """Print profiles for important dimension columns."""
  dimension_columns = [
    "REF_DATE",
    "GEO",
    "NAICS",
    "Gender",
    "Age group",
    "Type of work",
    "Labour force characteristics",
    "Wages",
    "Statistics",
  ]

  available_columns = [
    column
    for column in dimension_columns
    if column in df.columns
  ]

  print_section("DIMENSION PROFILE")

  for column in available_columns:
    print_subsection(column)

    print(
      f"Unique values: "
      f"{df[column].nunique(dropna=True):,}"
    )

    if column == "REF_DATE":
      date_profile = get_date_profile(df)

      print(
        f"Minimum date : "
        f"{date_profile['min']}"
      )
      print(
        f"Maximum date : "
        f"{date_profile['max']}"
      )
      print(
        f"Date periods : "
        f"{date_profile['unique']:,}"
      )
      print(
        f"Invalid dates: "
        f"{date_profile['invalid']:,}"
      )

    else:
      value_counts = (
        df[column]
        .value_counts(dropna=False)
        .head(10)
      )

      print(value_counts.to_string())


def check_candidate_key(df, key_columns):
  """Check whether the candidate analytical key is unique."""
  print_section("DATA GRAIN / KEY CHECK")

  print("Candidate key:")

  for column in key_columns:
    print(f"  - {column}")

  missing_columns = [
    column
    for column in key_columns
    if column not in df.columns
  ]

  if missing_columns:
    print()
    print("Missing key columns:")

    for column in missing_columns:
      print(f"  - {column}")

    return

  duplicate_count = df.duplicated(
    subset=key_columns
  ).sum()

  unique_key_count = (
    df[key_columns]
    .drop_duplicates()
    .shape[0]
  )

  print()
  print(
    f"Unique key combinations: "
    f"{unique_key_count:,}"
  )
  print(
    f"Duplicate key rows     : "
    f"{duplicate_count:,}"
  )

  if duplicate_count == 0:
    print("Key status             : UNIQUE")
  else:
    print("Key status             : DUPLICATES FOUND")


def print_value_unit_semantics(df, measure_column):
  """Show how measures map to units and scalar factors."""
  print_section("VALUE & UNIT SEMANTICS")

  if measure_column not in df.columns:
    print(
      f"Measure column not found: "
      f"{measure_column}"
    )
    return

  columns = [
    measure_column,
    "UOM",
    "SCALAR_FACTOR",
  ]

  available_columns = [
    column
    for column in columns
    if column in df.columns
  ]

  semantics = (
    df[available_columns]
    .drop_duplicates()
    .sort_values(available_columns)
  )

  print(
    semantics.to_string(index=False)
  )


def print_missing_analysis(df, measure_column):
  """Analyze missing VALUE and STATUS relationships."""
  print_section("MISSING / DATA QUALITY")

  value_missing = df["VALUE"].isna()

  print(
    f"Missing VALUE      : "
    f"{value_missing.sum():,}"
  )
  print(
    f"Missing VALUE (%)  : "
    f"{value_missing.mean() * 100:.2f}%"
  )

  if "STATUS" in df.columns:
    status_missing = df["STATUS"].isna().sum()

    print(
      f"Non-null STATUS    : "
      f"{df['STATUS'].notna().sum():,}"
    )
    print(
      f"Missing STATUS     : "
      f"{status_missing:,}"
    )

    print()
    print("STATUS × VALUE missingness:")

    status_table = pd.crosstab(
      df["STATUS"].fillna("<NA>"),
      value_missing,
    )

    status_table.columns = [
      "VALUE present",
      "VALUE missing",
    ]

    print(
      status_table.to_string()
    )

  if measure_column in df.columns:
    print()
    print(
      f"Missing VALUE by "
      f"[{measure_column}]:"
    )

    measure_missing = (
      df.groupby(measure_column)["VALUE"]
      .agg(
        rows="size",
        missing=lambda s: s.isna().sum(),
      )
    )

    measure_missing["missing_pct"] = (
      measure_missing["missing"]
      / measure_missing["rows"]
      * 100
    ).round(2)

    print(
      measure_missing.to_string()
    )


def compare_industries(file_paths):
  """Compare NAICS categories across datasets."""
  print_section("INDUSTRY COMPATIBILITY")

  industry_sets = {}

  for file_path in file_paths:
    try:
      naics = pd.read_csv(
        file_path,
        usecols=["NAICS"],
        low_memory=False,
      )["NAICS"]

      industry_sets[file_path.name] = set(
        naics.dropna().unique()
      )

    except Exception as error:
      print(
        f"Could not inspect "
        f"{file_path.name}: {error}"
      )

  comparisons = [
    (
      "14100022_extracted.csv",
      "14100063_extracted.csv",
    ),
    (
      "14100063_extracted.csv",
      "14100372_extracted.csv",
    ),
  ]

  for left_name, right_name in comparisons:
    if (
      left_name not in industry_sets
      or right_name not in industry_sets
    ):
      continue

    left = industry_sets[left_name]
    right = industry_sets[right_name]

    common = sorted(left & right)
    only_left = sorted(left - right)
    only_right = sorted(right - left)

    print()
    print(
      f"{left_name} × {right_name}"
    )

    print()
    print(
      f"Common industries "
      f"({len(common)}):"
    )

    for industry in common:
      print(f"  - {industry}")

    print()
    print(
      f"Only in {left_name} "
      f"({len(only_left)}):"
    )

    for industry in only_left:
      print(f"  - {industry}")

    print()
    print(
      f"Only in {right_name} "
      f"({len(only_right)}):"
    )

    for industry in only_right:
      print(f"  - {industry}")


def print_analysis_readiness():
  """Print the planned analytical grains and time period."""
  print_section("ANALYSIS READINESS")

  print(
    f"Analysis period: "
    f"{ANALYSIS_START} → {ANALYSIS_END}"
  )

  start = pd.Period(
    ANALYSIS_START,
    freq="M",
  )

  end = pd.Period(
    ANALYSIS_END,
    freq="M",
  )

  months = len(
    pd.period_range(
      start,
      end,
      freq="M",
    )
  )

  print(
    f"Expected months: "
    f"{months}"
  )

  print()
  print(
    "Analysis A — Labour force × Wage"
  )

  print("Datasets:")
  print("  - 14100022")
  print("  - 14100063")

  print()
  print("Common dimensions:")
  print("  - REF_DATE")
  print("  - GEO")
  print("  - NAICS")
  print("  - Gender")
  print("  - Age group")

  print()
  print("Dataset-specific dimensions:")
  print(
    "  - 14100022: "
    "Labour force characteristics"
  )
  print(
    "  - 14100063: "
    "Wages, Type of work"
  )

  print()
  print("Potential analysis grain:")
  print(
    "  REF_DATE × GEO × NAICS × "
    "Gender × Age group"
  )

  print()
  print(
    "Analysis B — Wage × Job vacancy"
  )

  print("Datasets:")
  print("  - 14100063")
  print("  - 14100372")

  print()
  print("Common dimensions:")
  print("  - REF_DATE")
  print("  - GEO")
  print("  - NAICS")

  print()
  print("Dataset-specific dimensions:")
  print(
    "  - 14100063: "
    "Wages, Type of work, Gender, Age group"
  )
  print(
    "  - 14100372: "
    "Statistics"
  )

  print()
  print("Potential analysis grain:")
  print(
    "  REF_DATE × GEO × NAICS"
  )

  print()
  print("Transformation considerations:")
  print(
    "  - Filter to "
    "2021-01 → 2025-12"
  )
  print(
    "  - Harmonize NAICS categories"
  )
  print(
    "  - Pivot measures where appropriate"
  )
  print(
    "  - Create calendar YEAR "
    "for annual analysis"
  )
  print(
    "  - Aggregate dimensions "
    "before cross-dataset joins"
  )
  print(
    "  - Preserve STATUS information "
    "where relevant"
  )


def inspect_file(file_path):
  """Inspect one extracted CSV file."""
  print_section(
    f"FILE: {file_path.name}"
  )

  df = pd.read_csv(
    file_path,
    low_memory=False,
  )

  config = DATASET_CONFIG.get(
    file_path.name,
    {},
  )

  measure_column = config.get(
    "measure_column"
  )

  key_columns = config.get(
    "key_columns",
    [],
  )

  # ---------------------------------------------------------------------------
  # Dataset overview
  # ---------------------------------------------------------------------------

  print_section("DATASET OVERVIEW")

  print(
    f"Rows       : "
    f"{len(df):,}"
  )

  print(
    f"Columns    : "
    f"{len(df.columns):,}"
  )

  print(
    f"Memory     : "
    f"{df.memory_usage(deep=True).sum() / 1024**2:,.1f} MB"
  )

  if "REF_DATE" in df.columns:
    date_profile = get_date_profile(df)

    period_profile = (
      get_analysis_period_profile(df)
    )

    print()

    print(
      f"Available period: "
      f"{date_profile['min']} → "
      f"{date_profile['max']}"
    )

    print(
      f"Available months: "
      f"{date_profile['unique']:,}"
    )

    print()

    print(
      f"Analysis period: "
      f"{ANALYSIS_START} → "
      f"{ANALYSIS_END}"
    )

    print(
      f"Expected months: "
      f"{period_profile['expected']:,}"
    )

    print(
      f"Available months: "
      f"{period_profile['available']:,}"
    )

    if period_profile["missing"]:
      print(
        "Missing analysis months:"
      )

      for month in period_profile["missing"]:
        print(f"  - {month}")

    else:
      print(
        "Analysis coverage: COMPLETE"
      )

  # ---------------------------------------------------------------------------
  # Variables
  # ---------------------------------------------------------------------------

  print_section("STRUCTURE")

  variable_info = pd.DataFrame({
    "variable": df.columns,
    "dtype": df.dtypes.astype(str).values,
    "non_null": df.notna().sum().values,
    "missing": df.isna().sum().values,
    "missing_pct": (
      df.isna().mean().values * 100
    ).round(2),
    "unique": df.nunique(
      dropna=True
    ).values,
  })

  print(
    variable_info.to_string(
      index=False
    )
  )

  # ---------------------------------------------------------------------------
  # Dimension profile
  # ---------------------------------------------------------------------------

  profile_dimensions(df)

  # ---------------------------------------------------------------------------
  # Numeric statistics
  # ---------------------------------------------------------------------------

  numeric_columns = (
    df.select_dtypes(
      include="number"
    ).columns
  )

  if len(numeric_columns) > 0:
    print_section(
      "NUMERIC VARIABLES — BASIC STATISTICS"
    )

    numeric_stats = (
      df[numeric_columns]
      .describe()
      .T
    )

    numeric_stats["missing"] = (
      df[numeric_columns]
      .isna()
      .sum()
    )

    numeric_stats["missing_pct"] = (
      df[numeric_columns]
      .isna()
      .mean()
      * 100
    ).round(2)

    print(
      numeric_stats.to_string()
    )

  # ---------------------------------------------------------------------------
  # Candidate key
  # ---------------------------------------------------------------------------

  if key_columns:
    check_candidate_key(
      df,
      key_columns,
    )

  # ---------------------------------------------------------------------------
  # Value / Unit semantics
  # ---------------------------------------------------------------------------

  if measure_column:
    print_value_unit_semantics(
      df,
      measure_column,
    )

  # ---------------------------------------------------------------------------
  # Missing / data quality
  # ---------------------------------------------------------------------------

  if (
    "VALUE" in df.columns
    and measure_column
  ):
    print_missing_analysis(
      df,
      measure_column,
    )

  # ---------------------------------------------------------------------------
  # Exact duplicate rows
  # ---------------------------------------------------------------------------

  print_section(
    "EXACT DUPLICATE ROWS"
  )

  duplicate_rows = df.duplicated().sum()

  print(
    f"Duplicate rows: "
    f"{duplicate_rows:,}"
  )

  if duplicate_rows == 0:
    print(
      "Duplicate status: NONE"
    )
  else:
    print(
      "Duplicate status: FOUND"
    )

  return df


# =============================================================================
# MAIN
# =============================================================================

def main():
  print_section(
    "EXPLORATORY DATA ANALYSIS"
  )

  print(
    f"Extracted directory: "
    f"{EXTRACTED_DIR}"
  )

  print()

  print(
    f"Target analysis period: "
    f"{ANALYSIS_START} → "
    f"{ANALYSIS_END}"
  )

  csv_files = sorted(
    EXTRACTED_DIR.glob("*.csv")
  )

  if not csv_files:
    print()
    print("No CSV files found.")
    return

  print()
  print("CSV files found:")

  for file_path in csv_files:
    print(
      f"  - {file_path.name}"
    )

  # ---------------------------------------------------------------------------
  # Inspect each dataset separately
  # ---------------------------------------------------------------------------

  for file_path in csv_files:
    df = inspect_file(file_path)

    # Explicitly release the large DataFrame
    # before loading the next file.
    del df

  # ---------------------------------------------------------------------------
  # Cross-dataset industry compatibility
  # ---------------------------------------------------------------------------

  compare_industries(
    csv_files
  )

  # ---------------------------------------------------------------------------
  # Analysis readiness
  # ---------------------------------------------------------------------------

  print_analysis_readiness()

  print()
  print("=" * 80)
  print("EDA COMPLETE")
  print("=" * 80)


if __name__ == "__main__":
  main()