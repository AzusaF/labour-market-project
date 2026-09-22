"""
05 — Exploratory Data Analysis
02 - NAICS Comparison

Compares NAICS categories across the three extracted datasets
to determine whether industry categories are directly compatible
for cross-dataset analysis and future joins.

Output:
- output/05_eda/02_naics_comparison.txt
"""

from pathlib import Path
import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

EXTRACTED_DIR = Path("data/extracted")
OUTPUT_FILE = Path("output/05_eda/02_naics_comparison.txt")

DATASETS = [
  "14100022_extracted.csv",
  "14100063_extracted.csv",
  "14100372_extracted.csv",
]


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


def load_naics(file_path):
  """Load unique NAICS values from one extracted dataset."""
  try:
    df = pd.read_csv(
      file_path,
      usecols=["North American Industry Classification System (NAICS)"],
      low_memory=False,
    )
  except Exception as error:
    print(
      f"Could not read {file_path.name}: {error}"
    )
    return None

  naics = (
    df["North American Industry Classification System (NAICS)"]
    .dropna()
    .astype(str)
    .str.strip()
  )

  naics = naics[
    naics != ""
  ]

  return sorted(
    naics.unique()
  )


def print_dataset_profiles(industry_sets):
  """Print NAICS profiles for each dataset."""
  print_section("NAICS PROFILE BY DATASET")

  for dataset_name, naics in industry_sets.items():
    print_subsection(dataset_name)

    print(
      f"Unique NAICS categories: "
      f"{len(naics):,}"
    )

    if not naics:
      print("No NAICS values found.")
      continue

    print()
    print("NAICS categories:")

    for industry in naics:
      print(f"  - {industry}")


def compare_pair(left_name, right_name, left, right):
  """Compare NAICS categories between two datasets."""
  print_section(
    f"NAICS COMPARISON: {left_name} × {right_name}"
  )

  common = sorted(left & right)
  only_left = sorted(left - right)
  only_right = sorted(right - left)

  print(
    f"Categories in {left_name}: "
    f"{len(left):,}"
  )

  print(
    f"Categories in {right_name}: "
    f"{len(right):,}"
  )

  print(
    f"Common categories: "
    f"{len(common):,}"
  )

  print(
    f"Only in {left_name}: "
    f"{len(only_left):,}"
  )

  print(
    f"Only in {right_name}: "
    f"{len(only_right):,}"
  )

  print()

  print_subsection("COMMON CATEGORIES")

  if common:
    for industry in common:
      print(f"  - {industry}")
  else:
    print("None")

  print_subsection(
    f"ONLY IN {left_name}"
  )

  if only_left:
    for industry in only_left:
      print(f"  - {industry}")
  else:
    print("None")

  print_subsection(
    f"ONLY IN {right_name}"
  )

  if only_right:
    for industry in only_right:
      print(f"  - {industry}")
  else:
    print("None")

  return common, only_left, only_right


def print_three_way_comparison(industry_sets):
  """Compare NAICS categories across all three datasets."""
  print_section(
    "THREE-WAY NAICS COMPATIBILITY"
  )

  available_sets = list(
    industry_sets.values()
  )

  if len(available_sets) < 3:
    print(
      "Three-way comparison could not be completed."
    )
    return

  common_all = set.intersection(
    *available_sets
  )

  union_all = set.union(
    *available_sets
  )

  print(
    f"Total distinct NAICS categories "
    f"across all datasets: "
    f"{len(union_all):,}"
  )

  print(
    f"NAICS categories common to all "
    f"three datasets: "
    f"{len(common_all):,}"
  )

  print()

  print_subsection(
    "COMMON TO ALL THREE DATASETS"
  )

  if common_all:
    for industry in sorted(common_all):
      print(f"  - {industry}")
  else:
    print("None")

  print_subsection(
    "CATEGORIES NOT COMMON TO ALL THREE"
  )

  not_common_all = sorted(
    union_all - common_all
  )

  if not_common_all:
    for industry in not_common_all:
      print(f"  - {industry}")
  else:
    print("None")


def print_compatibility_summary(industry_sets):
  """Summarize whether NAICS categories are directly compatible."""
  print_section(
    "COMPATIBILITY SUMMARY"
  )

  dataset_names = list(
    industry_sets.keys()
  )

  if len(dataset_names) < 3:
    print(
      "Insufficient datasets for a complete "
      "compatibility assessment."
    )
    return

  all_sets = list(
    industry_sets.values()
  )

  common_all = set.intersection(
    *all_sets
  )

  union_all = set.union(
    *all_sets
  )

  if len(common_all) == len(union_all):
    print(
      "NAICS compatibility status: "
      "FULLY ALIGNED"
    )
    print()
    print(
      "All datasets contain the same "
      "NAICS categories."
    )
  else:
    print(
      "NAICS compatibility status: "
      "NOT FULLY ALIGNED"
    )
    print()
    print(
      f"Common categories across all datasets: "
      f"{len(common_all):,}"
    )
    print(
      f"Distinct categories across all datasets: "
      f"{len(union_all):,}"
    )
    print()
    print(
      "Direct cross-dataset joins should not "
      "assume identical NAICS coverage."
    )
    print(
      "A mapping or harmonization strategy "
      "may be required before joining datasets."
    )

  print()
  print(
    "Recommended next step:"
  )
  print(
    "Review the NAICS category differences "
    "and determine whether the differences "
    "represent different classification levels, "
    "different category definitions, or "
    "dataset-specific coverage."
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
        "NAICS COMPARISON"
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
        "Compare NAICS categories across the "
        "three extracted datasets before defining "
        "a cross-dataset mapping or join strategy."
      )

      # -----------------------------------------------------------------------
      # Load NAICS categories
      # -----------------------------------------------------------------------

      print_section(
        "DATASET DISCOVERY"
      )

      industry_sets = {}

      for dataset_name in DATASETS:
        file_path = (
          EXTRACTED_DIR / dataset_name
        )

        if not file_path.exists():
          print()
          print(
            f"File not found: {file_path}"
          )
          continue

        print(
          f"Loading: {dataset_name}"
        )

        naics = load_naics(file_path)

        if naics is not None:
          industry_sets[
            dataset_name
          ] = set(naics)

      print()

      print(
        f"Datasets successfully loaded: "
        f"{len(industry_sets):,}"
      )

      # -----------------------------------------------------------------------
      # Dataset-level NAICS profiles
      # -----------------------------------------------------------------------

      print_dataset_profiles(
        {
          name: sorted(values)
          for name, values
          in industry_sets.items()
        }
      )

      # -----------------------------------------------------------------------
      # Pairwise comparisons
      # -----------------------------------------------------------------------

      comparison_pairs = [
        (
          "14100022_extracted.csv",
          "14100063_extracted.csv",
        ),
        (
          "14100022_extracted.csv",
          "14100372_extracted.csv",
        ),
        (
          "14100063_extracted.csv",
          "14100372_extracted.csv",
        ),
      ]

      for left_name, right_name in comparison_pairs:
        if (
          left_name not in industry_sets
          or right_name not in industry_sets
        ):
          continue

        compare_pair(
          left_name,
          right_name,
          industry_sets[left_name],
          industry_sets[right_name],
        )

      # -----------------------------------------------------------------------
      # Three-way comparison
      # -----------------------------------------------------------------------

      if len(industry_sets) == 3:
        print_three_way_comparison(
          industry_sets
        )

      # -----------------------------------------------------------------------
      # Compatibility summary
      # -----------------------------------------------------------------------

      print_compatibility_summary(
        industry_sets
      )

      print()
      print("=" * 80)
      print("NAICS COMPARISON COMPLETE")
      print("=" * 80)

    finally:
      sys.stdout = original_stdout

  print(
    f"NAICS comparison report written to: "
    f"{OUTPUT_FILE}"
  )


if __name__ == "__main__":
  main()