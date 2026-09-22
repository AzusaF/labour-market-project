"""
05 — Exploratory Data Analysis
02 - Grain Compatibility

Evaluates the analytical grain of each extracted dataset and
identifies shared and dataset-specific dimensions to determine
whether direct cross-dataset joins are appropriate.

Output:
- output/05_eda/03_grain_compatibility.txt
"""

from pathlib import Path
import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

EXTRACTED_DIR = Path("data/extracted")
OUTPUT_FILE = Path("output/05_eda/03_grain_compatibility.txt")

DATASET_CONFIG = {
  "14100022_extracted.csv": {
    "name": "Labour force characteristics",
    "grain_columns": [
      "REF_DATE",
      "GEO",
      "North American Industry Classification System (NAICS)",
      "Labour force characteristics",
      "Gender",
      "Age group",
    ],
  },
  "14100063_extracted.csv": {
    "name": "Employee wages",
    "grain_columns": [
      "REF_DATE",
      "GEO",
      "North American Industry Classification System (NAICS)",
      "Wages",
      "Type of work",
      "Gender",
      "Age group",
    ],
  },
  "14100372_extracted.csv": {
    "name": "Job vacancies, payroll employees, and vacancy rate",
    "grain_columns": [
      "REF_DATE",
      "GEO",
      "North American Industry Classification System (NAICS)",
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


def load_dataset(file_path):
  """Load one extracted CSV file."""
  try:
    return pd.read_csv(
      file_path,
      low_memory=False,
    )
  except Exception as error:
    print(
      f"Could not read {file_path.name}: {error}"
    )
    return None


def print_grain_profile(file_name, df, config):
  """Print the analytical grain and dimension profiles."""
  print_section(
    f"GRAIN PROFILE: {file_name}"
  )

  print(
    f"Dataset: {config['name']}"
  )

  print()

  print("Candidate analytical grain:")

  for column in config["grain_columns"]:
    print(f"  - {column}")

  missing_columns = [
    column
    for column in config["grain_columns"]
    if column not in df.columns
  ]

  if missing_columns:
    print()
    print("Missing grain columns:")

    for column in missing_columns:
      print(f"  - {column}")

    return

  duplicate_count = df.duplicated(
    subset=config["grain_columns"]
  ).sum()

  unique_combinations = (
    df[config["grain_columns"]]
    .drop_duplicates()
    .shape[0]
  )

  print()
  print(
    f"Unique grain combinations: "
    f"{unique_combinations:,}"
  )

  print(
    f"Duplicate grain rows     : "
    f"{duplicate_count:,}"
  )

  if duplicate_count == 0:
    print(
      "Grain status             : UNIQUE"
    )
  else:
    print(
      "Grain status             : DUPLICATES FOUND"
    )

  print_subsection(
    "Dimension Cardinality"
  )

  for column in config["grain_columns"]:
    print(
      f"{column}: "
      f"{df[column].nunique(dropna=True):,} "
      f"unique values"
    )


def print_shared_dimensions(dataset_columns):
  """Print dimensions shared across all datasets."""
  print_section(
    "SHARED JOIN DIMENSIONS"
  )

  if not dataset_columns:
    print("No datasets available.")
    return

  common_columns = set.intersection(
    *[
      set(columns)
      for columns in dataset_columns.values()
    ]
  )

  print(
    "Dimensions present in all datasets:"
  )

  for column in sorted(common_columns):
    print(f"  - {column}")

  print()

  if common_columns:
    print(
      "These columns are shared across datasets, but shared presence alone does not imply join compatibility. "
      "Analytical join dimensions must be evaluated separately from metadata and observation attributes."
    )
  else:
    print(
      "No common dimensions were found."
    )


def print_dataset_specific_dimensions(dataset_columns):
  """Print dimensions unique to each dataset."""
  print_section(
    "DATASET-SPECIFIC DIMENSIONS"
  )

  all_columns = set.union(
    *[
      set(columns)
      for columns in dataset_columns.values()
    ]
  )

  common_columns = set.intersection(
    *[
      set(columns)
      for columns in dataset_columns.values()
    ]
  )

  for dataset_name, columns in dataset_columns.items():
    specific_columns = sorted(
      set(columns) - common_columns
    )

    print_subsection(dataset_name)

    if specific_columns:
      for column in specific_columns:
        print(f"  - {column}")
    else:
      print(
        "No dataset-specific dimensions."
      )

  print()
  print(
    "Shared dimensions: "
    f"{len(common_columns):,}"
  )

  print(
    "Total dimensions across datasets: "
    f"{len(all_columns):,}"
  )


def compare_common_dimensions(datasets):
  """Compare value compatibility for common dimensions."""
  print_section(
    "COMMON DIMENSION VALUE COMPATIBILITY"
  )

  dataset_names = list(datasets.keys())

  common_dimensions = set.intersection(
    *[
      set(df.columns)
      for df in datasets.values()
    ]
  )

  for column in sorted(common_dimensions):
    print_subsection(column)

    value_sets = {}

    for dataset_name, df in datasets.items():
      values = (
        df[column]
        .dropna()
        .astype(str)
        .str.strip()
      )

      value_sets[dataset_name] = set(
        values.unique()
      )

      print(
        f"{dataset_name}: "
        f"{len(value_sets[dataset_name]):,} "
        f"unique values"
      )

    if len(value_sets) < 2:
      continue

    common_values = set.intersection(
      *value_sets.values()
    )

    union_values = set.union(
      *value_sets.values()
    )

    print(
      f"Common values across all datasets: "
      f"{len(common_values):,}"
    )

    print(
      f"Total distinct values: "
      f"{len(union_values):,}"
    )

    if column == "North American Industry Classification System (NAICS)":
      print(
        "Note: NAICS category coverage is "
        "not identical across datasets. "
        "See 02_naics_comparison.txt."
      )


# =============================================================================
# MAIN
# =============================================================================

def main():
  # Ensure the output directory exists.
  OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True,
  )

  # Redirect all print output to the EDA report file.
  with OUTPUT_FILE.open(
    "w",
    encoding="utf-8",
  ) as output_file:

    import sys

    original_stdout = sys.stdout
    sys.stdout = output_file

    try:
      print_section(
        "GRAIN & JOIN COMPATIBILITY ANALYSIS"
      )

      print(
        f"Extracted directory: "
        f"{EXTRACTED_DIR}"
      )

      print(
        f"Output file: "
        f"{OUTPUT_FILE}"
      )

      print()

      print(
        "Purpose:"
      )

      print(
        "Identify the analytical grain of each dataset and "
        "compare shared and dataset-specific dimensions "
        "to determine whether direct cross-dataset joins "
        "are appropriate before transformation."
      )

      # -----------------------------------------------------------------------
      # Load datasets
      # -----------------------------------------------------------------------

      print_section(
        "DATASET DISCOVERY"
      )

      datasets = {}

      for file_name in DATASET_CONFIG:
        file_path = (
          EXTRACTED_DIR / file_name
        )

        if not file_path.exists():
          print()
          print(
            f"File not found: {file_path}"
          )
          continue

        print(
          f"Loading: {file_name}"
        )

        df = load_dataset(file_path)

        if df is not None:
          datasets[file_name] = df

      print()

      print(
        f"Datasets successfully loaded: "
        f"{len(datasets):,}"
      )

      if not datasets:
        print()
        print("No datasets available.")
        return

      # -----------------------------------------------------------------------
      # Grain profiles
      # -----------------------------------------------------------------------

      for file_name, df in datasets.items():
        config = DATASET_CONFIG[file_name]

        print_grain_profile(
          file_name,
          df,
          config,
        )

      # -----------------------------------------------------------------------
      # Shared dimensions
      # -----------------------------------------------------------------------

      dataset_columns = {
        file_name: list(df.columns)
        for file_name, df in datasets.items()
      }

      print_shared_dimensions(
        dataset_columns
      )

      # -----------------------------------------------------------------------
      # Dataset-specific dimensions
      # -----------------------------------------------------------------------

      print_dataset_specific_dimensions(
        dataset_columns
      )

      # -----------------------------------------------------------------------
      # Common dimension values
      # -----------------------------------------------------------------------

      compare_common_dimensions(
        datasets
      )

      print()
      print("=" * 80)
      print("GRAIN & JOIN COMPATIBILITY ANALYSIS COMPLETE")
      print("=" * 80)

    finally:
      sys.stdout = original_stdout

  print(
    f"Grain compatibility report written to: "
    f"{OUTPUT_FILE}"
  )


if __name__ == "__main__":
  main()