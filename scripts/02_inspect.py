from pathlib import Path
import csv
import os


# ============================================================
# Configuration
# ============================================================

DATA_DIR = Path("data/raw")

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

def inspect_file_info(file_path):
  """Display basic information about the CSV file."""

  file_size_bytes = os.path.getsize(file_path)
  file_size_mb = file_size_bytes / (1024 ** 2)
  file_size_gb = file_size_bytes / (1024 ** 3)

  print("-" * 80)
  print(f"FILE: {file_path.name}")
  print("-" * 80)
  print(f"Size: {file_size_bytes:,} bytes")

  if file_size_gb >= 1:
    print(f"Size: {file_size_gb:.2f} GB")
  else:
    print(f"Size: {file_size_mb:.2f} MB")


# ============================================================
# CSV structure detection
# ============================================================

def detect_csv_structure(file_path):
  """
  Inspect the CSV structure without loading the entire file.

  Checks:
  - delimiter
  - header
  - row width consistency in an initial sample
  """

  print("\n[CSV structure]")

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
      print("WARNING: Empty file.")
      return None, None

    print(f"Detected delimiter: {repr(delimiter)}")
    print(f"Number of columns: {len(header)}")

    print("\nColumn names:")

    for index, column in enumerate(header, start=1):
      print(f"  {index}. {column}")

    # Check row width consistency using a limited sample.
    inconsistent_rows = []

    for row_number, row in enumerate(
      reader,
      start=2
    ):
      if len(row) != len(header):
        inconsistent_rows.append(
          (row_number, len(row))
        )

      if row_number > STRUCTURE_CHECK_ROWS:
        break

    print(
      f"\nChecked first "
      f"{min(STRUCTURE_CHECK_ROWS, row_number - 1)} data rows."
    )

    if inconsistent_rows:
      print(
        "WARNING: Inconsistent row structure detected."
      )

      for row_number, width in inconsistent_rows[:10]:
        print(
          f"  Row {row_number}: "
          f"{width} columns "
          f"(expected {len(header)})"
        )

      if len(inconsistent_rows) > 10:
        print(
          f"  ... and "
          f"{len(inconsistent_rows) - 10} more."
        )
    else:
      print(
        "Row structure is consistent "
        "within the checked sample."
      )

    return delimiter, header


# ============================================================
# Safe data sampling
# ============================================================

def inspect_head(file_path, delimiter):
  """Display the first few data rows."""

  print("\n[Beginning of file]")

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

    print(f"Header columns: {len(header)}")

    for row_number, row in enumerate(
      reader,
      start=1
    ):
      print(f"Row {row_number}: {row}")

      if row_number >= SAMPLE_ROWS:
        break

def inspect_middle(file_path, delimiter):
  """
  Display a small sample from the middle of the file.

  This does not load the entire file into memory.
  """

  print("\n[Middle of file]")

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
    print(line)


def inspect_tail(file_path, delimiter):
  """
  Display the last few physical lines of the file.

  This does not load the entire file into memory.
  """

  print("\n[End of file]")

  with open(
    file_path,
    "rb"
  ) as file:

    file.seek(0, 2)
    file_size = file.tell()

    read_size = min(100_000, file_size)

    file.seek(max(0, file_size - read_size))

    data = file.read(read_size)

  text = data.decode(
    "utf-8-sig",
    errors="replace"
  )

  lines = text.splitlines()

  for line in lines[-SAMPLE_ROWS:]:
    print(line)


# ============================================================
# Main inspection
# ============================================================

def inspect_dataset(file_path):
  """Run all safe inspection steps for one dataset."""

  if not file_path.exists():
    print(f"\nWARNING: File not found: {file_path}")
    return

  inspect_file_info(file_path)

  delimiter, header = detect_csv_structure(file_path)

  if delimiter is None:
    return

  inspect_head(
    file_path,
    delimiter
  )

  inspect_middle(
    file_path,
    delimiter
  )

  inspect_tail(
    file_path,
    delimiter
  )

  print("\n[Full-file analysis]")
  print(
    "Skipped intentionally to avoid loading "
    "the entire dataset into memory."
  )


def main():
  """Inspect all selected datasets."""

  print("=" * 80)
  print("DATA INSPECTION")
  print("=" * 80)
  print(f"Data directory: {DATA_DIR}")
  print()

  for filename in TARGET_FILES:
    file_path = DATA_DIR / filename

    print("\n")
    inspect_dataset(file_path)

  print("\n")
  print("=" * 80)
  print("INSPECTION COMPLETE")
  print("=" * 80)


if __name__ == "__main__":
  main()