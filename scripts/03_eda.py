# """
# Exploratory Data Analysis
# """

# import pandas as pd


# FILE_PATH = "data/raw/14100372.csv"


# def load_data(file_path):
#   """
#   Load the dataset.
#   """
#   return pd.read_csv(file_path)


# def inspect_overview(df):
#   """
#   Display basic information about the dataset.
#   """
#   print("\n[Dataset Overview]")
#   print(f"Shape: {df.shape}")

#   print("\nColumns:")
#   print(df.columns.tolist())

#   print("\nData types:")
#   print(df.dtypes)


# def inspect_missing_values(df):
#   """
#   Display missing value counts.
#   """
#   print("\n[Missing Values]")
#   print(df.isna().sum())


# def inspect_missing_value_status(df):
#   """
#   Display STATUS values for rows with missing VALUE.
#   """
#   print("\n[Missing VALUE by STATUS]")
#   print(
#     df[df["VALUE"].isna()]["STATUS"].value_counts()
#   )


# def inspect_unique_values(df):
#   """
#   Display the number of unique values in each column.
#   """
#   print("\n[Unique Values]")
#   print(df.nunique())


# def inspect_categories(df):
#   """
#   Display the distribution of key categorical columns.
#   """
#   print("\n[Statistics × UOM]")
#   print(
#     df.groupby("Statistics")["UOM"]
#       .unique()
#   )

#   print("\n[Statistics × NAICS]")
#   print(
#     df.groupby(
#       ["Statistics", "North American Industry Classification System (NAICS)"]
#     ).size()
#   )


# def inspect_date_range(df):
#   """
#   Display the date range and number of periods.
#   """
#   print("\n[REF_DATE]")
#   print(f"Number of periods: {df['REF_DATE'].nunique()}")
#   print(f"First period: {df['REF_DATE'].min()}")
#   print(f"Last period: {df['REF_DATE'].max()}")


# def inspect_status(df):
#   """
#   Display the distribution of STATUS values.
#   """
#   print("\n[STATUS]")
#   print(df["STATUS"].value_counts(dropna=False))


# def inspect_numeric_statistics(df):
#   """
#   Display descriptive statistics for numeric columns.
#   """
#   print("\n[Numeric Statistics]")
#   print(df.describe())

#   print("\n[VALUE SUMMARY]")
#   print(df["VALUE"].describe())

#   print("\n[VALUE BY STATISTICS]")
#   print(
#     df.groupby("Statistics")["VALUE"]
#       .describe()
#   )

# def main():
#   df = load_data(FILE_PATH)

#   inspect_overview(df)
#   inspect_missing_values(df)
#   inspect_missing_value_status(df)
#   inspect_unique_values(df)
#   inspect_categories(df)
#   inspect_date_range(df)
#   inspect_status(df)
#   inspect_numeric_statistics(df)


# if __name__ == "__main__":
#   main()

from pathlib import Path

import pandas as pd


# ============================================================
# Configuration
# ============================================================

DATA_DIR = Path("data/raw")

# Files larger than this size are treated as large files.
LARGE_FILE_SIZE_MB = 500

# Number of rows to read from the beginning of a large file.
SAMPLE_ROWS = 10000


# ============================================================
# Find CSV files
# ============================================================

def find_csv_files():
  csv_files = sorted(DATA_DIR.glob("*.csv"))

  if not csv_files:
    print(f"No CSV files found in: {DATA_DIR}")
    return []

  return csv_files


# ============================================================
# Select CSV file
# ============================================================

def select_file(csv_files):
  if len(csv_files) == 1:
    print(f"CSV file found: {csv_files[0].name}")
    return csv_files[0]

  print("CSV files found:\n")

  for i, file_path in enumerate(csv_files, start=1):
    print(f"[{i}] {file_path.name}")

  print("\nSelect a file to analyze:")

  while True:
    try:
      selection = int(input("> "))

      if 1 <= selection <= len(csv_files):
        return csv_files[selection - 1]

      print(
        f"Please enter a number between 1 and {len(csv_files)}."
      )

    except ValueError:
      print("Please enter a valid number.")


# ============================================================
# Load data
# ============================================================

def load_data(file_path):
  file_size_mb = file_path.stat().st_size / (1024 ** 2)

  print("\n" + "=" * 80)
  print("DATA LOADING")
  print("=" * 80)

  print(f"File: {file_path.name}")
  print(f"File size: {file_size_mb:,.2f} MB")

  if file_size_mb > LARGE_FILE_SIZE_MB:
    print(
      f"Large file detected. "
      f"Reading the first {SAMPLE_ROWS:,} rows only."
    )

    df = pd.read_csv(
      file_path,
      nrows=SAMPLE_ROWS
    )

    is_sample = True

  else:
    print("Small file detected. Reading the full dataset.")

    df = pd.read_csv(file_path)

    is_sample = False

  print(f"Rows loaded: {len(df):,}")
  print(f"Columns loaded: {len(df.columns):,}")

  if is_sample:
    print("Note: This is a sample of the original dataset.")

  return df, is_sample


# ============================================================
# Basic inspection
# ============================================================

def inspect_structure(df):
  print("\n" + "=" * 80)
  print("STRUCTURE")
  print("=" * 80)

  print("\n[SHAPE]")
  print(f"Rows: {len(df):,}")
  print(f"Columns: {len(df.columns):,}")

  print("\n[COLUMNS]")
  print(df.columns.tolist())

  print("\n[DATA TYPES]")
  print(df.dtypes)

  print("\n[FIRST 5 ROWS]")
  print(df.head())


# ============================================================
# Numeric summary
# ============================================================

def summarize_numeric_columns(df):
  numeric_columns = df.select_dtypes(include="number").columns

  print("\n" + "=" * 80)
  print("NUMERIC SUMMARY")
  print("=" * 80)

  if len(numeric_columns) == 0:
    print("No numeric columns found.")
    return

  print(df[numeric_columns].describe())


# ============================================================
# VALUE analysis
# ============================================================

def analyze_value(df):
  if "VALUE" not in df.columns:
    return

  print("\n" + "=" * 80)
  print("VALUE ANALYSIS")
  print("=" * 80)

  print("\n[VALUE SUMMARY]")
  print(df["VALUE"].describe())

  if "STATUS" in df.columns:
    print("\n[VALUE BY STATUS]")
    print(
      df.groupby("STATUS")["VALUE"]
        .agg(["count", "min", "max", "mean"])
    )


# ============================================================
# Duplicate analysis
# ============================================================

def analyze_duplicates(df):
  print("\n" + "=" * 80)
  print("DUPLICATES")
  print("=" * 80)

  duplicate_count = df.duplicated().sum()

  print(f"Duplicate rows: {duplicate_count:,}")


# ============================================================
# Missing value analysis
# ============================================================

def analyze_missing_values(df):
  print("\n" + "=" * 80)
  print("MISSING VALUES")
  print("=" * 80)

  missing = df.isnull().sum()
  missing = missing[missing > 0].sort_values(ascending=False)

  if missing.empty:
    print("No missing values found.")
  else:
    print(missing)


# ============================================================
# Categorical value analysis
# ============================================================

def analyze_categorical_columns(df):
  categorical_columns = df.select_dtypes(
    include=["object", "category"]
  ).columns

  if len(categorical_columns) == 0:
    return

  print("\n" + "=" * 80)
  print("CATEGORICAL COLUMNS")
  print("=" * 80)

  for column in categorical_columns:
    print(f"\n[{column}]")
    print(
      f"Unique values: "
      f"{df[column].nunique(dropna=False):,}"
    )

    print(
      df[column]
        .value_counts(dropna=False)
        .head(20)
    )


# ============================================================
# Main
# ============================================================

def main():
  csv_files = find_csv_files()

  if not csv_files:
    return

  file_path = select_file(csv_files)

  df, is_sample = load_data(file_path)

  inspect_structure(df)
  summarize_numeric_columns(df)
  analyze_value(df)
  analyze_duplicates(df)
  analyze_missing_values(df)
  analyze_categorical_columns(df)

  print("\n" + "=" * 80)
  print("EDA COMPLETE")
  print("=" * 80)


if __name__ == "__main__":
  main()