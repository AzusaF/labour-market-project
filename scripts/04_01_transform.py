"""
04 — Data Transformation
01 — Transformation

Transforms the extracted Statistics Canada datasets into
five independent analysis-ready tables:

- Employment (GEO × Industry × Month)
- Wages (GEO × Industry × Month)
- Job vacancies (GEO × Industry × Month)
- Labour force total (GEO × Month, all industries)
- CPI (GEO × Month, All-items)

Transformation steps:

- Standardize common columns and dates
- Normalize selected NAICS labels
- Keep all available geographies
- Filter to the primary analysis period
- Remove suppressed observations (x)
- Keep the data-quality flag of the job vacancy estimates and set
  unreliable values (F) to NULL instead of dropping the rows
- Select required dimensions and measures
- Reshape measures into analysis-ready columns
- Validate the target analytical grain

Units are NOT converted. Column names carry the unit of the source:

- *_thousands : persons in thousands (14100022, 14100063)
- *_cad       : current dollars (14100063)
- *_pct       : percent
- no suffix   : persons (units) (14100372)
- CPI         : index, 2002=100 (18100004)

Output:

- data/processed/employment.csv
- data/processed/wages.csv
- data/processed/vacancies.csv
- data/processed/labour_force_total.csv
- data/processed/cpi.csv
"""

from pathlib import Path
import pandas as pd


# =============================================================================
# DIRECTORIES
# =============================================================================

EXTRACTED_DIR = Path("data/extracted")
PROCESSED_DIR = Path("data/processed")


# =============================================================================
# ANALYSIS PERIOD
# =============================================================================

START_DATE = "2021-01"
END_DATE = "2025-12"


# =============================================================================
# SOURCE COLUMN NAMES
# =============================================================================

NAICS_SOURCE_COLUMN = (
  "North American Industry Classification System (NAICS)"
)


# =============================================================================
# STATUS FLAGS
# =============================================================================

# Suppressed values are removed from the processed data.
SUPPRESSED_FLAGS = ("x",)

# Unreliable values are kept as rows, but VALUE is set to NULL.
UNRELIABLE_FLAGS = ("F",)


# =============================================================================
# LABOUR FORCE CONSTANTS
# =============================================================================

TOTAL_ALL_INDUSTRIES = "Total, all industries"

# =============================================================================
# GEO
# =============================================================================

NATIONAL_GEO = "Canada"
PROVINCES = [
  "Newfoundland and Labrador",
  "Prince Edward Island",
  "Nova Scotia",
  "New Brunswick",
  "Quebec",
  "Ontario",
  "Manitoba",
  "Saskatchewan",
  "Alberta",
  "British Columbia",
]

ALL_GEOS = [NATIONAL_GEO] + PROVINCES

TABLE_GEOS = {
  "employment": ALL_GEOS,
  "wages": ALL_GEOS,
  "vacancies": [NATIONAL_GEO],
  "labour_force_total": ALL_GEOS,
  "cpi": ALL_GEOS,
}


# =============================================================================
# ANALYTICAL GRAIN
# =============================================================================

# Industry-level tables:
# GEO × Industry × Month

KEY_COLUMNS = [
  "REF_DATE",
  "GEO",
  "NAICS"
]


# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(filename):
  """
  Load an extracted Statistics Canada dataset.
  """
  path = EXTRACTED_DIR / filename

  return pd.read_csv(
    path,
    low_memory=False
  )


# =============================================================================
# COMMON TRANSFORMATIONS
# =============================================================================

def standardize_common_columns(df):
  """
  Standardize columns shared across datasets.
  """

  df = df.copy()

  # Rename the long Statistics Canada NAICS column.
  if NAICS_SOURCE_COLUMN in df.columns:
    df = df.rename(
      columns={
        NAICS_SOURCE_COLUMN: "NAICS"
      }
    )

  # Convert REF_DATE from YYYY-MM string to datetime.
  if "REF_DATE" in df.columns:
    df["REF_DATE"] = pd.to_datetime(
      df["REF_DATE"],
      format="%Y-%m"
    )

  return df


def normalize_naics_labels(df):
  """
  Standardize minor differences in NAICS labels.
  """

  df = df.copy()

  if "NAICS" not in df.columns:
    return df

  df["NAICS"] = (
    df["NAICS"]
    .str.replace(
      "Business, building and other support services [55, 56]",
      "Business, building and other support services [55-56]",
      regex=False
    )
    .str.replace(
      "Finance, insurance, real estate, rental and leasing [52, 53]",
      "Finance, insurance, real estate, rental and leasing [52-53]",
      regex=False
    )
  )

  return df


def filter_common_period(df):
  """
  Restrict the dataset to the primary analysis period.
  """

  return df[
    (df["REF_DATE"] >= pd.Timestamp(START_DATE)) &
    (df["REF_DATE"] <= pd.Timestamp(END_DATE))
  ].copy()


def apply_common_steps(df):
  """
  Apply transformations shared by the datasets.

  Geography is intentionally NOT filtered here.
  All available GEO values are retained.
  """

  df = standardize_common_columns(df)
  df = normalize_naics_labels(df)
  df = filter_common_period(df)

  return df


# =============================================================================
# STATUS HANDLING
# =============================================================================

def remove_flagged_values(df, flags):
  """
  Remove observations with the specified STATUS flags.
  """

  if "STATUS" in df.columns:
    df = df[
      ~df["STATUS"].isin(flags)
    ].copy()

  return df


def null_flagged_values(df, flags):
  """
  Set VALUE to NULL for specified STATUS flags,
  while keeping the rows and their status flags.
  """

  df = df.copy()

  if "STATUS" in df.columns:
    df["VALUE"] = df["VALUE"].mask(
      df["STATUS"].isin(flags)
    )

  return df


# =============================================================================
# EMPLOYMENT
# =============================================================================

def transform_employment(labour_force):
  """
  Transform the labour force dataset into an
  industry-level employment table.

  Grain:
      GEO × NAICS × Month
  """

  df = labour_force.copy()

  # Remove suppressed observations.
  df = remove_flagged_values(
    df,
    SUPPRESSED_FLAGS
  )

  # Select total employment for people aged 15 and over.
  df = df[
    (df["Gender"] == "Total - Gender") &
    (df["Age group"] == "15 years and over") &
    (
      df["Labour force characteristics"]
      == "Employment"
    )
  ].copy()

  # Rename the measure column.
  df = df.rename(
    columns={
      "VALUE": "Employment_thousands"
    }
  )

  # Keep columns required for analysis.
  return df[
    [
      "REF_DATE",
      "GEO",
      "NAICS",
      "Employment_thousands"
    ]
  ]


# =============================================================================
# LABOUR FORCE TOTAL
# =============================================================================

def transform_labour_force_total(labour_force):
  """
  Transform the labour force dataset into a
  geography-level labour force total table.

  Grain:
      GEO × Month

  This table supports Beveridge curve analysis.
  """

  df = labour_force.copy()

  # Remove suppressed observations.
  df = remove_flagged_values(
    df,
    SUPPRESSED_FLAGS
  )

  # Select:
  # - all industries
  # - both genders
  # - age 15 years and over
  df = df[
    (df["NAICS"] == TOTAL_ALL_INDUSTRIES) &
    (df["Gender"] == "Total - Gender") &
    (df["Age group"] == "15 years and over") &
    (
      df["Labour force characteristics"].isin(
        [
          "Labour force",
          "Employment",
          "Unemployment",
          "Unemployment rate"
        ]
      )
    )
  ].copy()

  # Reshape measures into separate columns.
  df = df.pivot(
    index=[
      "REF_DATE",
      "GEO"
    ],
    columns="Labour force characteristics",
    values="VALUE"
  ).reset_index()

  df.columns.name = None

  # Rename measures.
  df = df.rename(
    columns={
      "Labour force":
        "Labour_force_thousands",

      "Employment":
        "Employment_thousands",

      "Unemployment":
        "Unemployment_thousands",

      "Unemployment rate":
        "Unemployment_rate_pct"
    }
  )

  # Keep columns required for analysis.
  return df[
    [
      "REF_DATE",
      "GEO",
      "Labour_force_thousands",
      "Employment_thousands",
      "Unemployment_thousands",
      "Unemployment_rate_pct"
    ]
  ]


# =============================================================================
# WAGES
# =============================================================================

def transform_wages():
  """
  Transform the wage dataset into an
  industry-level wage table.

  Grain:
      GEO × NAICS × Month
  """

  df = load_data(
    "14100063_extracted.csv"
  )

  # Apply common transformations and filters.
  df = apply_common_steps(df)

  # Remove suppressed observations.
  df = remove_flagged_values(
    df,
    SUPPRESSED_FLAGS
  )

  # Select wages for:
  # - total gender
  # - age 15 years and over
  # - both full- and part-time employees
  df = df[
    (df["Gender"] == "Total - Gender") &
    (df["Age group"] == "15 years and over") &
    (
      df["Type of work"]
      == "Both full- and part-time employees"
    )
  ].copy()

  # Retain:
  # - average hourly wage
  # - median hourly wage
  # - total employees
  df = df[
    df["Wages"].isin(
      [
        "Average hourly wage rate",
        "Median hourly wage rate",
        "Total employees, all wages"
      ]
    )
  ].copy()

  # Reshape wage measures.
  df = df.pivot(
    index=KEY_COLUMNS,
    columns="Wages",
    values="VALUE"
  ).reset_index()

  df.columns.name = None

  # Rename measures.
  df = df.rename(
    columns={
      "Average hourly wage rate":
        "Average_hourly_wage_cad",

      "Median hourly wage rate":
        "Median_hourly_wage_cad",

      "Total employees, all wages":
        "Total_employees_thousands"
    }
  )

  # Keep columns required for analysis.
  return df[
    [
      "REF_DATE",
      "GEO",
      "NAICS",
      "Average_hourly_wage_cad",
      "Median_hourly_wage_cad",
      "Total_employees_thousands"
    ]
  ]


# =============================================================================
# JOB VACANCIES
# =============================================================================

def transform_vacancies():
  """
  Transform the job vacancy dataset into an
  industry-level table.

  Grain:
      GEO × NAICS × Month
  """

  df = load_data(
    "14100372_extracted.csv"
  )

  # Apply common transformations and filters.
  df = apply_common_steps(df)

  # Set values marked as too unreliable to publish
  # to NULL while keeping the rows and quality flags.
  df = null_flagged_values(
    df,
    UNRELIABLE_FLAGS
  )

  # Reshape values.
  values = df.pivot(
    index=KEY_COLUMNS,
    columns="Statistics",
    values="VALUE"
  )

  # Reshape quality flags.
  quality = df.pivot(
    index=KEY_COLUMNS,
    columns="Statistics",
    values="STATUS"
  )

  # Rename measures.
  values = values.rename(
    columns={
      "Job vacancies":
        "Job_vacancies",

      "Payroll employees":
        "Payroll_employees",

      "Job vacancy rate":
        "Job_vacancy_rate_pct"
  }
  )

  # Rename quality columns.
  quality = quality.rename(
    columns={
      "Job vacancies":
        "Job_vacancies_quality",

      "Payroll employees":
        "Payroll_employees_quality",

      "Job vacancy rate":
        "Job_vacancy_rate_quality"
    }
  )

  # Combine values and quality flags.
  df = values.join(
    quality
  ).reset_index()

  df.columns.name = None

  # Keep columns required for analysis.
  return df[
    [
      "REF_DATE",
      "GEO",
      "NAICS",
      "Job_vacancies",
      "Payroll_employees",
      "Job_vacancy_rate_pct",
      "Job_vacancies_quality",
      "Payroll_employees_quality",
      "Job_vacancy_rate_quality"
    ]
  ]


# =============================================================================
# CPI
# =============================================================================

def transform_cpi():
  """
  Transform the CPI dataset into a single
  headline inflation table.

  Grain:
      GEO × Month

  Only the headline All-items CPI with
  the 2002=100 index is retained.
  """

  df = load_data(
    "18100004_extracted.csv"
  )

  # Apply common transformations and filters.
  df = apply_common_steps(df)

  # Keep headline CPI only.
  #
  # "All-items (1992=100)" is excluded because it is
  # an alternative index-base series for the same concept.
  df = df[
    (df["Products and product groups"] == "All-items") &
    (df["UOM"] == "2002=100")
  ].copy()

  # Keep Canada and the 10 provinces.
  df = df[
    df["GEO"].isin(TABLE_GEOS["cpi"])
  ].copy()

  # Remove suppressed observations if any.
  df = remove_flagged_values(
    df,
    SUPPRESSED_FLAGS
  )

  # Rename CPI measure.
  df = df.rename(
    columns={
      "VALUE": "CPI"
    }
  )

  # Keep columns required for analysis.
  return df[
    [
      "REF_DATE",
      "GEO",
      "CPI"
    ]
  ]


# =============================================================================
# VALIDATION
# =============================================================================

def validate_table(
  df,
  table_name,
  key_columns
):
  """
  Validate the target grain and basic structure
  of a processed table.
  """

  print(
    f"Validating: {table_name}"
  )

  # -------------------------------------------------------------------------
  # Duplicate records
  # -------------------------------------------------------------------------

  duplicates = df.duplicated(
    subset=key_columns,
    keep=False
  )

  if duplicates.any():
    duplicate_count = duplicates.sum()

    raise ValueError(
      f"{table_name}: "
      f"{duplicate_count} duplicate rows found."
    )

  # -------------------------------------------------------------------------
  # Geography
  # -------------------------------------------------------------------------

  if "GEO" in df.columns:

    if df["GEO"].isna().any():
      raise ValueError(
          f"{table_name}: "
          "Missing GEO values found."
      )

    print(
      f"Geographies: "
      f"{df['GEO'].nunique():,}"
    )

  # -------------------------------------------------------------------------
  # Date range
  # -------------------------------------------------------------------------

  min_date = df["REF_DATE"].min()
  max_date = df["REF_DATE"].max()

  if min_date != pd.Timestamp(START_DATE):
    raise ValueError(
      f"{table_name}: "
      f"Unexpected minimum date: {min_date:%Y-%m}"
    )

  if max_date != pd.Timestamp(END_DATE):
    raise ValueError(
      f"{table_name}: "
      f"Unexpected maximum date: {max_date:%Y-%m}"
    )

  # -------------------------------------------------------------------------
  # Month completeness by geography
  # -------------------------------------------------------------------------

  expected_months = set(
    pd.date_range(
      START_DATE,
      END_DATE,
      freq="MS"
    )
  )

  if "GEO" in df.columns:

    missing_by_geo = {}

    for geo, group in df.groupby("GEO"):

      actual_months = set(
        group["REF_DATE"]
      )

      missing_months = (
        expected_months - actual_months
      )

      if missing_months:
        missing_by_geo[geo] = missing_months

    if missing_by_geo:

      print(
        "Warning: Missing months detected:"
      )

      for geo, missing_months in (
        missing_by_geo.items()
      ):
        print(
          f"  {geo}: "
          f"{len(missing_months)} missing"
        )

    else:
      print(
        "Month coverage: "
        "Complete for all geographies."
      )

  # -------------------------------------------------------------------------
  # NAICS coverage
  # -------------------------------------------------------------------------

  if "NAICS" in df.columns:

    print(
      f"Industries: "
      f"{df['NAICS'].nunique():,}"
    )

  # -------------------------------------------------------------------------
  # Basic results
  # -------------------------------------------------------------------------

  print(
    f"Rows: {len(df):,}"
  )

  print(
    f"Date range: "
    f"{min_date:%Y-%m} to "
    f"{max_date:%Y-%m}"
  )

  # -------------------------------------------------------------------------
  # Missing cells
  # -------------------------------------------------------------------------

  missing = df.isna().sum()
  missing = missing[
    missing > 0
  ]

  if missing.empty:

    print(
      "Missing cells: 0"
    )

  else:

    print(
      "Missing cells:"
    )

    for column, count in missing.items():

      print(
        f"  {column}: "
        f"{count:,}"
      )

  print(
    f"{table_name} validation passed."
  )
  print()


# =============================================================================
# MAIN
# =============================================================================

def main():

  PROCESSED_DIR.mkdir(
    parents=True,
    exist_ok=True
  )

  # -------------------------------------------------------------------------
  # Labour force survey
  # -------------------------------------------------------------------------

  # Load once and reuse for:
  # - employment
  # - labour force total

  labour_force = apply_common_steps(
    load_data(
      "14100022_extracted.csv"
    )
  )

  # -------------------------------------------------------------------------
  # Transform datasets
  # -------------------------------------------------------------------------

  employment = transform_employment(
    labour_force
  )

  labour_force_total = (
    transform_labour_force_total(
      labour_force
    )
  )

  wages = transform_wages()

  vacancies = transform_vacancies()

  cpi = transform_cpi()

  # -------------------------------------------------------------------------
  # Validation
  # -------------------------------------------------------------------------

  validate_table(
    employment,
    "Employment",
    key_columns=KEY_COLUMNS
  )

  validate_table(
    wages,
    "Wages",
    key_columns=KEY_COLUMNS
  )

  validate_table(
    vacancies,
    "Vacancies",
    key_columns=KEY_COLUMNS
  )

  validate_table(
    labour_force_total,
    "Labour force total",
    key_columns=[
      "REF_DATE",
      "GEO"
    ]
  )

  validate_table(
    cpi,
    "CPI",
    key_columns=[
      "REF_DATE",
      "GEO"
    ]
  )

  # -------------------------------------------------------------------------
  # Export
  # -------------------------------------------------------------------------

  outputs = {
    "employment.csv":
      employment,

    "wages.csv":
      wages,

    "vacancies.csv":
      vacancies,

    "labour_force_total.csv":
      labour_force_total,

    "cpi.csv":
      cpi
  }

  for filename, table in outputs.items():

    output_path = (
      PROCESSED_DIR / filename
    )

    table.to_csv(
      output_path,
      index=False
    )

    print(
      f"Saved: {output_path}"
    )


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
  main()