"""
07 — Data Transformation
01 — Transformation

Transforms the extracted Statistics Canada datasets into
three independent analysis-ready datasets:
- Employment
- Wages
- Job vacancies

Transformation steps:
- Standardize common columns and dates
- Normalize selected NAICS labels
- Filter to Canada and the primary analysis period
- Remove suppressed or unreliable observations
- Select required dimensions and measures
- Reshape measures into analysis-ready columns
- Validate the target analytical grain

Output:
- data/processed/employment.csv
- data/processed/wages.csv
- data/processed/vacancies.csv
"""


from pathlib import Path
import pandas as pd


# Define input and output directories.
EXTRACTED_DIR = Path("data/extracted")
PROCESSED_DIR = Path("data/processed")

# Define the common analysis period.
START_DATE = "2021-01"
END_DATE = "2025-12"

# Define the original Statistics Canada NAICS column name.
NAICS_SOURCE_COLUMN = (
  "North American Industry Classification System (NAICS)"
)


# Load an extracted dataset from the input directory.
def load_data(filename):
  path = EXTRACTED_DIR / filename
  return pd.read_csv(path)


# Standardize columns shared across the datasets.
def standardize_common_columns(df):
  df = df.copy()

  # Rename the long Statistics Canada NAICS column.
  if NAICS_SOURCE_COLUMN in df.columns:
    df = df.rename(
      columns={
        NAICS_SOURCE_COLUMN: "NAICS"
      }
    )

  # Convert the reference date to datetime format.
  if "REF_DATE" in df.columns:
    df["REF_DATE"] = pd.to_datetime(
      df["REF_DATE"],
      format="%Y-%m"
    )

  return df


# Standardize minor differences in NAICS labels.
def normalize_naics_labels(df):
  df = df.copy()

  if "NAICS" not in df.columns:
    raise ValueError("NAICS column not found.")

  df["NAICS"] = (
    df["NAICS"]
    .str.replace(
      "[55, 56]",
      "[55-56]",
      regex=False
    )
    .str.replace(
      "[52, 53]",
      "[52-53]",
      regex=False
    )
  )

  return df


# Restrict the dataset to the primary analysis period.
def filter_common_period(df):
  return df[
    (df["REF_DATE"] >= pd.Timestamp(START_DATE)) &
    (df["REF_DATE"] <= pd.Timestamp(END_DATE))
  ].copy()


# Restrict the dataset to Canada-level observations.
def filter_canada(df):
  return df[
    df["GEO"] == "Canada"
  ].copy()


# Remove suppressed observations.
def remove_suppressed_values(df):
  if "STATUS" in df.columns:
    df = df[
      df["STATUS"] != "x"
    ].copy()

  return df


# Transform the labour force dataset into an employment table.
def transform_employment():
  df = load_data(
    "14100022_extracted.csv"
  )

  # Apply common transformations and filters.
  df = standardize_common_columns(df)
  df = normalize_naics_labels(df)
  df = filter_canada(df)
  df = filter_common_period(df)
  df = remove_suppressed_values(df)

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
      "VALUE": "Employment"
    }
  )

  # Keep columns required for analysis.
  return df[
    [
      "REF_DATE",
      "GEO",
      "NAICS",
      "Employment"
    ]
  ]


# Transform the wage dataset into an industry-level wage table.
def transform_wages():
  df = load_data(
    "14100063_extracted.csv"
  )

  # Apply common transformations and filters.
  df = standardize_common_columns(df)
  df = normalize_naics_labels(df)
  df = filter_canada(df)
  df = filter_common_period(df)
  df = remove_suppressed_values(df)

  # Select total wages for people aged 15 and over.
  df = df[
    (df["Gender"] == "Total - Gender") &
    (df["Age group"] == "15 years and over")
  ].copy()

  # Retain average and median hourly wage measures.
  df = df[
    df["Wages"].isin(
      [
        "Average hourly wage rate",
        "Median hourly wage rate"
      ]
    )
  ].copy()

  # Reshape wage measures into separate columns.
  df = df.pivot_table(
    index=[
      "REF_DATE",
      "GEO",
      "NAICS"
    ],
    columns="Wages",
    values="VALUE",
    aggfunc="first"
  ).reset_index()

  # Rename wage measures for the processed dataset.
  df = df.rename(
    columns={
      "Average hourly wage rate":
        "Average_hourly_wage",
      "Median hourly wage rate":
        "Median_hourly_wage"
    }
  )

  # Keep columns required for analysis.
  return df[
    [
      "REF_DATE",
      "GEO",
      "NAICS",
      "Average_hourly_wage",
      "Median_hourly_wage"
    ]
  ]


# Transform the job vacancy dataset into an industry-level table.
def transform_vacancies():
  df = load_data(
    "14100372_extracted.csv"
  )

  # Apply common transformations and filters.
  df = standardize_common_columns(df)
  df = normalize_naics_labels(df)
  df = filter_canada(df)
  df = filter_common_period(df)

  # Remove observations marked as too unreliable to publish.
  if "STATUS" in df.columns:
    df = df[
      df["STATUS"] != "F"
    ].copy()

  # Reshape statistics into separate columns.
  df = df.pivot_table(
    index=[
      "REF_DATE",
      "GEO",
      "NAICS"
    ],
    columns="Statistics",
    values="VALUE",
    aggfunc="first"
  ).reset_index()

  # Rename measures for the processed dataset.
  df = df.rename(
    columns={
      "Job vacancies":
        "Job_vacancies",
      "Payroll employees":
        "Payroll_employees",
      "Job vacancy rate":
        "Job_vacancy_rate"
    }
  )

  # Keep columns required for analysis.
  return df[
    [
      "REF_DATE",
      "GEO",
      "NAICS",
      "Job_vacancies",
      "Payroll_employees",
      "Job_vacancy_rate"
    ]
  ]


# Validate the target grain and basic structure of a processed table.
def validate_table(df, table_name):
  key_columns = [
    "REF_DATE",
    "GEO",
    "NAICS"
  ]

  # Check for duplicate Canada × Industry × Month records.
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

  # Confirm that only one geography is present.
  if df["GEO"].nunique() != 1:
    raise ValueError(
      f"{table_name}: "
      "Multiple geographies found."
    )

  # Confirm that the geography is Canada.
  if df["GEO"].iloc[0] != "Canada":
    raise ValueError(
      f"{table_name}: "
      "Non-Canada records found."
    )

  # Confirm that the expected analysis period is present.
  min_date = df["REF_DATE"].min()
  max_date = df["REF_DATE"].max()

  if min_date != pd.Timestamp(START_DATE):
    raise ValueError(
      f"{table_name}: "
      f"Unexpected minimum date: {min_date}"
    )

  if max_date != pd.Timestamp(END_DATE):
    raise ValueError(
      f"{table_name}: "
      f"Unexpected maximum date: {max_date}"
    )

  # Report basic validation results.
  print(
    f"{table_name} validation passed."
  )
  print(
    f"Rows: {len(df):,}"
  )
  print(
    f"Industries: {df['NAICS'].nunique():,}"
  )
  print(
    f"Date range: "
    f"{min_date:%Y-%m} to {max_date:%Y-%m}"
  )


# Run all transformations, validations, and exports.
def main():
  PROCESSED_DIR.mkdir(
    parents=True,
    exist_ok=True
  )

  # Transform each source dataset independently.
  employment = transform_employment()
  wages = transform_wages()
  vacancies = transform_vacancies()

  # Validate the target grain and basic structure.
  validate_table(
    employment,
    "Employment"
  )

  validate_table(
    wages,
    "Wages"
  )

  validate_table(
    vacancies,
    "Vacancies"
  )

  # Save the three independent processed datasets.
  employment.to_csv(
    PROCESSED_DIR / "employment.csv",
    index=False
  )

  wages.to_csv(
    PROCESSED_DIR / "wages.csv",
    index=False
  )

  vacancies.to_csv(
    PROCESSED_DIR / "vacancies.csv",
    index=False
  )

  # Report the output files.
  print(
    f"Saved: "
    f"{PROCESSED_DIR / 'employment.csv'}"
  )
  print(
    f"Saved: "
    f"{PROCESSED_DIR / 'wages.csv'}"
  )
  print(
    f"Saved: "
    f"{PROCESSED_DIR / 'vacancies.csv'}"
  )


if __name__ == "__main__":
  main()