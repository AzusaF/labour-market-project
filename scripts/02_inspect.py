"""
02 — Data Inspection

Inspects Statistics Canada raw CSV datasets without loading
the full datasets into memory and extracts:
- File size information
- CSV structure and delimiter
- Column names
- Row width consistency
- Beginning, middle, and end-of-file samples

Output:
- outputs/02_inspect.txt
"""

from pathlib import Path
import csv
import os


# ============================================================
# Configuration
# ============================================================

DATA_DIR = Path("data/raw")
OUTPUT_DIR = Path("outputs")

TARGET_FILES = [
  "14100022.csv",
  "14100063.csv",
  "14100372.csv",
]

SAMPLE_ROWS = 5
STRUCTURE_CHECK_ROWS = 1000


# ============================================================
# File information
# ============================================================

def inspect_file_info(file_path, output):
  """Display basic information about the CSV file."""

  file_size_bytes = os.path.getsize(file_path)
  file_size_mb = file_size_bytes / (1024 ** 2)
  file_size_gb = file_size_bytes / (1024 ** 3)

  output.write("-" * 80 + "\n")
  output.write(f"FILE: {file_path.name}\n")
  output.write("-" * 80 + "\n")
  output.write(f"Size: {file_size_bytes:,} bytes\n")

  if file_size_gb >= 1:
    output.write(f"Size: {file_size_gb:.2f} GB\n")
  else:
    output.write(f"Size: {file_size_mb:.2f} MB\n")


# ============================================================
# CSV structure detection
# ============================================================

def detect_csv_structure(file_path, output):
  """
  Inspect the CSV structure without loading the entire file.

  Checks:
  - delimiter
  - header
  - row width consistency in an initial sample
  """

  output.write("\n[CSV structure]\n")

  with open(
    file_path,
    "r",
    encoding="utf-8-sig",
    newline=""
  ) as file:

    sample = file.read(100_000)

    try:
      dialect = csv.Sniffer().sniff(
        sample,
        delimiters=",\t;|"
      )
      delimiter = dialect.delimiter
    except csv.Error:
      delimiter = ","

    file.seek(0)

    reader = csv.reader(
      file,
      delimiter=delimiter
    )

    header = next(reader, None)

    if header is None:
      output.write("WARNING: Empty file.\n")
      return None, None

    output.write(
      f"Detected delimiter: {repr(delimiter)}\n"
    )
    output.write(
      f"Number of columns: {len(header)}\n"
    )

    output.write("\nColumn names:\n")

    for index, column in enumerate(header, start=1):
      output.write(
        f"  {index}. {column}\n"
      )

    # Check row width consistency using a limited sample.
    inconsistent_rows = []
    rows_checked = 0

    for row_number, row in enumerate(
      reader,
      start=2
    ):
      rows_checked += 1

      if len(row) != len(header):
        inconsistent_rows.append(
          (row_number, len(row))
        )

      if rows_checked >= STRUCTURE_CHECK_ROWS:
        break

    output.write(
      f"\nChecked first {rows_checked} data rows.\n"
    )

    if inconsistent_rows:
      output.write(
        "WARNING: Inconsistent row structure detected.\n"
      )

      for row_number, width in inconsistent_rows[:10]:
        output.write(
          f"  Row {row_number}: "
          f"{width} columns "
          f"(expected {len(header)})\n"
        )

      if len(inconsistent_rows) > 10:
        output.write(
          f"  ... and "
          f"{len(inconsistent_rows) - 10} more.\n"
        )
    else:
      output.write(
        "Row structure is consistent "
        "within the checked sample.\n"
      )

    return delimiter, header


# ============================================================
# Safe data sampling
# ============================================================

def inspect_head(file_path, delimiter, output):
  """Display the first few data rows."""

  output.write("\n[Beginning of file]\n")

  with open(
    file_path,
    "r",
    encoding="utf-8-sig",
    newline=""
  ) as file:

    reader = csv.reader(
      file,
      delimiter=delimiter
    )

    header = next(reader, None)

    if header is None:
      return

    output.write(
      f"Header columns: {len(header)}\n"
    )

    for row_number, row in enumerate(
      reader,
      start=1
    ):
      output.write(
        f"Row {row_number}: {row}\n"
      )

      if row_number >= SAMPLE_ROWS:
        break


def inspect_middle(file_path, delimiter, output):
  """
  Display a small sample from the middle of the file.

  This does not load the entire file into memory.
  """

  output.write("\n[Middle of file]\n")

  file_size = os.path.getsize(file_path)
  middle_position = file_size // 2

  with open(
    file_path,
    "rb"
  ) as file:

    file.seek(middle_position)

    # Skip the partial line at the middle position.
    file.readline()

    data = file.read(100_000)

  text = data.decode(
    "utf-8-sig",
    errors="replace"
  )

  lines = text.splitlines()

  for line in lines[:SAMPLE_ROWS]:
    output.write(line + "\n")


def inspect_tail(file_path, delimiter, output):
  """
  Display the last few physical lines of the file.

  This does not load the entire file into memory.
  """

  output.write("\n[End of file]\n")

  with open(
    file_path,
    "rb"
  ) as file:

    file.seek(0, 2)
    file_size = file.tell()

    read_size = min(100_000, file_size)

    file.seek(
      max(0, file_size - read_size)
    )

    data = file.read(read_size)

  text = data.decode(
    "utf-8-sig",
    errors="replace"
  )

  lines = text.splitlines()

  for line in lines[-SAMPLE_ROWS:]:
    output.write(line + "\n")


# ============================================================
# Main inspection
# ============================================================

def inspect_dataset(file_path, output):
  """Run all safe inspection steps for one dataset."""

  if not file_path.exists():
    output.write(
      f"\nWARNING: File not found: {file_path}\n"
    )
    return

  inspect_file_info(
    file_path,
    output
  )

  delimiter, header = detect_csv_structure(
    file_path,
    output
  )

  if delimiter is None:
    return

  inspect_head(
    file_path,
    delimiter,
    output
  )

  inspect_middle(
    file_path,
    delimiter,
    output
  )

  inspect_tail(
    file_path,
    delimiter,
    output
  )

  output.write("\n[Full-file analysis]\n")
  output.write(
    "Skipped intentionally to avoid loading "
    "the entire dataset into memory.\n"
  )


def main():
  """Inspect all selected datasets and save the output."""

  OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
  )

  output_path = OUTPUT_DIR / "02_inspect.txt"

  with open(
    output_path,
    "w",
    encoding="utf-8"
  ) as output:

    output.write("=" * 80 + "\n")
    output.write("DATA INSPECTION\n")
    output.write("=" * 80 + "\n")
    output.write(
      f"Data directory: {DATA_DIR}\n"
    )
    output.write(
      f"Output directory: {OUTPUT_DIR}\n"
    )
    output.write("\n")

    for filename in TARGET_FILES:
      file_path = DATA_DIR / filename

      output.write("\n")
      inspect_dataset(
        file_path,
        output
      )

    output.write("\n")
    output.write("=" * 80 + "\n")
    output.write("INSPECTION COMPLETE\n")
    output.write("=" * 80 + "\n")

  print(
    f"Inspection output saved to: {output_path}"
  )


if __name__ == "__main__":
  main()