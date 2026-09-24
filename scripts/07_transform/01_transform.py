"""
07 — Data Transformation
01 — Transformation

Transforms the extracted Statistics Canada datasets into
four independent analysis-ready tables:
- Employment              (Canada × Industry × Month)
- Wages                   (Canada × Industry × Month)
- Job vacancies           (Canada × Industry × Month)
- Labour force total      (Canada × Month, all industries)

Transformation steps:
- Standardize common columns and dates
- Normalize selected NAICS labels
- Filter to Canada and the primary analysis period
- Remove suppressed observations (x)
- Keep the data-quality flag of the job vacancy estimates and set
  unreliable values (F) to NULL instead of dropping the rows
- Select required dimensions and measures
- Reshape measures into analysis-ready columns
- Validate the target analytical grain

Units are NOT converted. Column names carry the unit of the source:
- *_thousands : persons in thousands (14100022, 14100063)
- *_cad       : current dollars      (14100063)
- *_pct       : percent
- no suffix   : persons (units)      (14100372)

Output:
- data/processed/employment.csv
- data/processed/wages.csv
- data/processed/vacancies.csv
- data/processed/labour_force_total.csv
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

# Define the status flags handled in each dataset.
# Keep these consistent with 02_validation.py.
SUPPRESSED_FLAGS = ("x",)
UNRELIABLE_FLAGS = ("F",)

# Label of the all-industries total in the labour force survey.
TOTAL_ALL_INDUSTRIES = "Total, all industries"

# Define the analytical grain of the industry-level tables.
KEY_COLUMNS = ["REF_DATE", "GEO", "NAICS"]


# Load an extracted dataset from the input directory.
def load_data(filename):
  path = EXTRACTED_DIR / filename
  return pd.read_csv(path, low_memory=False)


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
# Keep these replacements consistent with 02_validation.py.
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


# Apply the steps shared by all datasets.
# Canada is filtered first so that the large provincial
# tables are reduced before the remaining copies are made.
def apply_common_steps(df):
  df = filter_canada(df)
  df = standardize_common_columns(df)
  df = normalize_naics_labels(df)
  df = filter_common_period(df)

  return df


# Remove observations marked with the given status flags.
def remove_flagged_values(df, flags):
  if "STATUS" in df.columns:
    df = df[
      ~df["STATUS"].isin(flags)
    ].copy()

  return df


# Set the value of flagged observations to NULL but keep the row
# and its status flag.
def null_flagged_values(df, flags):
  df = df.copy()

  df["VALUE"] = df["VALUE"].mask(
    df["STATUS"].isin(flags)
  )

  return df


# Transform the labour force dataset into an employment table.
# Expects the output of apply_common_steps().
def transform_employment(labour_force):
  df = labour_force.copy()

  # Remove suppressed observations.
  df = remove_flagged_values(df, SUPPRESSED_FLAGS)

  # Select total employment for people aged 15 and over.
  df = df[
    (df["Gender"] == "Total - Gender") &
    (df["Age group"] == "15 years and over") &
    (
      df["Labour force characteristics"]
      == "Employment"
    )
  ].copy()

  # Rename the measure column (persons in thousands).
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


# Transform the labour force dataset into a Canada-level total table.
# Expects the output of apply_common_steps().
# This table supports the Beveridge curve (unemployment vs vacancies).
def transform_labour_force_total(labour_force):
  df = labour_force.copy()

  # Remove suppressed observations.
  df = remove_flagged_values(df, SUPPRESSED_FLAGS)

  # Select all industries, both genders, aged 15 and over.
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
  # pivot raises an error if the selected rows are not unique.
  df = df.pivot(
    index=[
      "REF_DATE",
      "GEO"
    ],
    columns="Labour force characteristics",
    values="VALUE"
  ).reset_index()
  df.columns.name = None

  # Rename measures for the processed dataset.
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


# Transform the wage dataset into an industry-level wage table.
def transform_wages():
  df = load_data(
    "14100063_extracted.csv"
  )

  # Apply common transformations and filters.
  df = apply_common_steps(df)

  # Remove suppressed observations.
  df = remove_flagged_values(df, SUPPRESSED_FLAGS)

  # Select wages for people aged 15 and over,
  # covering both full- and part-time employees.
  # The employee count uses the same population so that it can
  # later be used as a weight for the wage measures.
  df = df[
    (df["Gender"] == "Total - Gender") &
    (df["Age group"] == "15 years and over") &
    (
      df["Type of work"]
      == "Both full- and part-time employees"
    )
  ].copy()

  # Retain wage measures and the number of employees.
  df = df[
    df["Wages"].isin(
      [
        "Average hourly wage rate",
        "Median hourly wage rate",
        "Total employees, all wages"
      ]
    )
  ].copy()

  # Reshape wage measures into separate columns.
  # pivot raises an error if the selected rows are not unique,
  # so a missing filter cannot go unnoticed.
  df = df.pivot(
    index=KEY_COLUMNS,
    columns="Wages",
    values="VALUE"
  ).reset_index()
  df.columns.name = None

  # Rename wage measures for the processed dataset.
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


# Transform the job vacancy dataset into an industry-level table.
def transform_vacancies():
  df = load_data(
    "14100372_extracted.csv"
  )

  # Apply common transformations and filters.
  df = apply_common_steps(df)

  # Set values marked as too unreliable to publish to NULL.
  # The rows are kept so that the status flag is not lost.
  df = null_flagged_values(df, UNRELIABLE_FLAGS)

  # Reshape values and status flags into separate columns.
  # pivot raises an error if the selected rows are not unique.
  values = df.pivot(
    index=KEY_COLUMNS,
    columns="Statistics",
    values="VALUE"
  )
  quality = df.pivot(
    index=KEY_COLUMNS,
    columns="Statistics",
    values="STATUS"
  )

  # Rename measures for the processed dataset.
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

  df = values.join(quality).reset_index()
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


# Validate the target grain and basic structure of a processed table.
def validate_table(
  df,
  table_name,
  key_columns=KEY_COLUMNS
):
  # Check for duplicate records at the target grain.
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

  # Confirm that no month of the analysis period is missing.
  expected_months = set(
    pd.date_range(START_DATE, END_DATE, freq="MS")
  )
  missing_months = expected_months - set(df["REF_DATE"])

  if missing_months:
    raise ValueError(
      f"{table_name}: "
      f"{len(missing_months)} months are missing."
    )

  # Report basic validation results.
  print(
    f"{table_name} validation passed."
  )
  print(
    f"Rows: {len(df):,}"
  )

  if "NAICS" in df.columns:
    print(
      f"Industries: {df['NAICS'].nunique():,}"
    )

  print(
    f"Date range: "
    f"{min_date:%Y-%m} to {max_date:%Y-%m}"
  )

  # Report missing cells so that they are never silent.
  missing = df.isna().sum()
  missing = missing[missing > 0]

  if missing.empty:
    print("Missing cells: 0")
  else:
    print("Missing cells:")
    for column, count in missing.items():
      print(f"  {column}: {count:,}")

  print()


# Run all transformations, validations, and exports.
def main():
  PROCESSED_DIR.mkdir(
    parents=True,
    exist_ok=True
  )

  # Load the labour force survey once and reuse it for two tables.
  labour_force = apply_common_steps(
    load_data("14100022_extracted.csv")
  )

  # Transform each source dataset independently.
  employment = transform_employment(labour_force)
  labour_force_total = transform_labour_force_total(
    labour_force
  )
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

  validate_table(
    labour_force_total,
    "Labour force total",
    key_columns=["REF_DATE", "GEO"]
  )

  # Save the four independent processed datasets.
  outputs = {
    "employment.csv": employment,
    "wages.csv": wages,
    "vacancies.csv": vacancies,
    "labour_force_total.csv": labour_force_total
  }

  for filename, table in outputs.items():
    table.to_csv(
      PROCESSED_DIR / filename,
      index=False
    )
    print(
      f"Saved: {PROCESSED_DIR / filename}"
    )


if __name__ == "__main__":
  main()