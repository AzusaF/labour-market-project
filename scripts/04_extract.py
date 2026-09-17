from pathlib import Path

import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = PROJECT_ROOT / "data" / "raw"
EXTRACTED_DIR = PROJECT_ROOT / "data" / "extracted"

START_YEAR = 2021
CHUNK_SIZE = 100_000


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_header(title):
  print()
  print("=" * 80)
  print(title)
  print("=" * 80)


def extract_year(ref_date):
  """
  Extract the year from REF_DATE.

  Examples:
    2021-01 -> 2021
    2026-08 -> 2026
  """
  return pd.to_numeric(
    ref_date.astype(str).str[:4],
    errors="coerce"
  )


def extract_file(input_file):
  """
  Extract all records from START_YEAR onward.

  The original columns and values are preserved.
  Only rows outside the target period are removed.
  """

  output_file = EXTRACTED_DIR / f"{input_file.stem}_extracted.csv"

  # Remove an existing output file so the extraction is reproducible.
  if output_file.exists():
    output_file.unlink()

  total_rows = 0
  extracted_rows = 0
  first_chunk = True

  print()
  print("-" * 80)
  print(f"FILE: {input_file.name}")
  print("-" * 80)

  for chunk in pd.read_csv(
    input_file,
    chunksize=CHUNK_SIZE,
    low_memory=False
  ):
    total_rows += len(chunk)

    years = extract_year(chunk["REF_DATE"])

    mask = years >= START_YEAR
    extracted_chunk = chunk.loc[mask]

    if len(extracted_chunk) > 0:
      extracted_rows += len(extracted_chunk)

      extracted_chunk.to_csv(
        output_file,
        mode="w" if first_chunk else "a",
        header=first_chunk,
        index=False
      )

      first_chunk = False

    print(
      f"Rows scanned: {total_rows:,} | "
      f"Rows extracted: {extracted_rows:,}",
      end="\r"
    )

  print()
  print()
  print(f"Rows scanned   : {total_rows:,}")
  print(f"Rows extracted : {extracted_rows:,}")
  print(f"Output         : {output_file}")

  return output_file


def verify_extracted_file(output_file):
  """
  Verify the extracted file without loading the full dataset.

  Checks:
    - number of rows
    - minimum REF_DATE
    - maximum REF_DATE
    - number of columns
  """

  row_count = 0
  min_date = None
  max_date = None
  column_names = None

  for chunk in pd.read_csv(
    output_file,
    chunksize=CHUNK_SIZE,
    usecols=["REF_DATE"],
    low_memory=False
  ):
    row_count += len(chunk)

    chunk_min = chunk["REF_DATE"].min()
    chunk_max = chunk["REF_DATE"].max()

    if min_date is None or chunk_min < min_date:
      min_date = chunk_min

    if max_date is None or chunk_max > max_date:
      max_date = chunk_max

  # Read only the header to confirm the number of columns.
  header = pd.read_csv(
    output_file,
    nrows=0
  )

  column_names = list(header.columns)

  return {
    "rows": row_count,
    "columns": len(column_names),
    "min_date": min_date,
    "max_date": max_date,
    "column_names": column_names,
  }


# =============================================================================
# MAIN
# =============================================================================

def main():
  print_header("DATA EXTRACTION")

  print(f"Raw directory      : {RAW_DIR}")
  print(f"Extracted directory: {EXTRACTED_DIR}")
  print(f"Start year         : {START_YEAR}")
  print(f"Chunk size         : {CHUNK_SIZE:,}")

  # ---------------------------------------------------------------------------
  # Find input files
  # ---------------------------------------------------------------------------

  input_files = sorted(RAW_DIR.glob("*.csv"))

  if not input_files:
    print()
    print("No CSV files found in data/raw.")
    return

  print()
  print("CSV files found:")
  print()

  for file in input_files:
    print(f"  - {file.name}")

  # ---------------------------------------------------------------------------
  # Create output directory
  # ---------------------------------------------------------------------------

  EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

  # ---------------------------------------------------------------------------
  # Extraction
  # ---------------------------------------------------------------------------

  print_header("EXTRACTING DATA")

  print(
    f"Extracting all records from {START_YEAR} onward."
  )

  print(
    "All original columns and values will be preserved."
  )

  output_files = []

  for input_file in input_files:
    output_file = extract_file(input_file)
    output_files.append(output_file)

  # ---------------------------------------------------------------------------
  # Verification
  # ---------------------------------------------------------------------------

  print_header("EXTRACTION VERIFICATION")

  for output_file in output_files:
    result = verify_extracted_file(output_file)

    print()
    print(f"FILE: {output_file.name}")
    print()
    print(f"Rows       : {result['rows']:,}")
    print(f"Columns    : {result['columns']}")
    print(f"REF_DATE   : {result['min_date']} -> {result['max_date']}")

  # ---------------------------------------------------------------------------
  # Complete
  # ---------------------------------------------------------------------------

  print()
  print("=" * 80)
  print("EXTRACTION COMPLETE")
  print("=" * 80)
  print()
  print(f"Output directory: {EXTRACTED_DIR}")
  print()


if __name__ == "__main__":
  main()