
"""
03 — Profile

Profiles all CSV files in data/raw and reports:
- Data loading information
- Dataset structure
- Numeric summary
- VALUE analysis
- Duplicate rows
- Missing values
- Categorical columns

Output:
- outputs/03_profile.txt
"""


from pathlib import Path
import pandas as pd
import sys


# ============================================================
# Configuration
# ============================================================

DATA_DIR = Path("data/raw")
OUTPUT_DIR = Path("outputs")
OUTPUT_FILE = OUTPUT_DIR / "03_profile.txt"

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
# Profile all files
# ============================================================

def profile_file(file_path):
  print("\n")
  print("#" * 80)
  print(f"# 03 PROFILE — {file_path.name}")
  print("#" * 80)

  df, is_sample = load_data(file_path)

  inspect_structure(df)
  summarize_numeric_columns(df)
  analyze_value(df)
  analyze_duplicates(df)
  analyze_missing_values(df)
  analyze_categorical_columns(df)


# ============================================================
# Main
# ============================================================

def main():
  csv_files = find_csv_files()

  if not csv_files:
    return

  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

  original_stdout = sys.stdout

  try:
    with OUTPUT_FILE.open("w", encoding="utf-8") as output:
      sys.stdout = output

      print("=" * 80)
      print("03 PROFILE")
      print("=" * 80)
      print(f"Data directory: {DATA_DIR}")
      print(f"Files analyzed: {len(csv_files)}")

      for file_path in csv_files:
        profile_file(file_path)

      print("\n" + "=" * 80)
      print("PROFILE COMPLETE")
      print("=" * 80)

  finally:
    sys.stdout = original_stdout

  print(f"Profile saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
  main()