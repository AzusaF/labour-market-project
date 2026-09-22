"""
01 — Metadata Inspection

Inspects Statistics Canada metadata CSV files and extracts:
- Metadata table structure
- Column names and sample rows
- Dataset-level information
- Dimension definitions
- Basic structural consistency checks

Output:
- outputs/01_metadata.txt
"""

from pathlib import Path
import csv


# =============================================================================
# CONFIGURATION
# =============================================================================

METADATA_DIR = Path("data/metadata")
OUTPUT_DIR = Path("outputs")
OUTPUT_FILE = OUTPUT_DIR / "01_metadata.txt"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_blank_row(row):
  """Return True if the row is empty or contains only blank cells."""
  return not row or all(cell.strip() == "" for cell in row)


def detect_tables(rows):
  """Split a metadata CSV into tables using blank rows as separators."""
  tables = []
  current_table = []

  for row in rows:
    if is_blank_row(row):
      if current_table:
        tables.append(current_table)
        current_table = []
    else:
      current_table.append(row)

  if current_table:
    tables.append(current_table)

  return tables


def clean_cell(value):
  """Remove surrounding whitespace from a cell."""
  return value.strip()


# =============================================================================
# TABLE INSPECTION
# =============================================================================

def inspect_table(table, table_number, start_line, end_line, output):
  """Write structural information and a small preview of a metadata table."""

  output.write("\n" + "-" * 80 + "\n")
  output.write(f"TABLE {table_number}\n")
  output.write("-" * 80 + "\n")

  output.write(
    f"Rows: {len(table)} (CSV lines {start_line}–{end_line})\n"
  )

  # Check whether all rows have the same number of columns.
  widths = [len(row) for row in table]
  min_width = min(widths)
  max_width = max(widths)

  if min_width == max_width:
    output.write(f"Columns: {max_width}\n")
  else:
    output.write(
      f"Columns: {min_width}–{max_width} "
      "(variable row width)\n"
    )
    output.write("WARNING: Row widths are not consistent.\n")

  # Treat the first row as the table header.
  header = table[0]

  output.write("\nColumns:\n")

  for column_number, column_name in enumerate(header, start=1):
    column_name = clean_cell(column_name)

    if column_name:
      output.write(f"    {column_number}: {column_name}\n")
    else:
      output.write(f"    {column_number}: <blank>\n")

  # Show a small preview of the first data rows.
  output.write("\nFirst data rows:\n")

  if len(table) > 1:
    preview_rows = table[1:4]

    for row_number, row in enumerate(preview_rows, start=1):
      cleaned_row = [clean_cell(value) for value in row]
      output.write(f"  Row {row_number}: {cleaned_row}\n")
  else:
    output.write("  <none>\n")


# =============================================================================
# DATASET SUMMARY
# =============================================================================

def extract_dataset_summary(tables):
  """
  Extract high-level dataset information from the metadata tables.

  The first table contains cube-level information.
  The second table contains dimension definitions.
  """

  summary = {
    "title": None,
    "product_id": None,
    "frequency": None,
    "start_period": None,
    "end_period": None,
    "dimension_count": None,
    "dimensions": [],
  }

  # ------------------------------------------------------------------
  # Table 1: Cube-level information
  # ------------------------------------------------------------------

  if tables:
    cube_table = tables[0]

    if len(cube_table) >= 2:
      header = cube_table[0]
      data = cube_table[1]

      header_map = {
        clean_cell(name): index
        for index, name in enumerate(header)
        if clean_cell(name)
      }

      def get_value(column_name):
        index = header_map.get(column_name)

        if index is not None and index < len(data):
          return clean_cell(data[index])

        return None

      summary["title"] = get_value("Cube Title")
      summary["product_id"] = get_value("Product Id")
      summary["frequency"] = get_value("Frequency")
      summary["start_period"] = get_value("Start Reference Period")
      summary["end_period"] = get_value("End Reference Period")

      dimension_count = get_value("Total number of dimensions")

      if dimension_count:
        try:
          summary["dimension_count"] = int(dimension_count)
        except ValueError:
          summary["dimension_count"] = dimension_count

  # ------------------------------------------------------------------
  # Table 2: Dimension definitions
  # ------------------------------------------------------------------

  if len(tables) >= 2:
    dimension_table = tables[1]

    if len(dimension_table) >= 2:
      header = dimension_table[0]

      header_map = {
        clean_cell(name): index
        for index, name in enumerate(header)
        if clean_cell(name)
      }

      dimension_id_index = header_map.get("Dimension ID")
      dimension_name_index = header_map.get("Dimension name")

      if (
        dimension_id_index is not None
        and dimension_name_index is not None
      ):
        for row in dimension_table[1:]:
          if (
            dimension_id_index < len(row)
            and dimension_name_index < len(row)
          ):
            dimension_id = clean_cell(
              row[dimension_id_index]
            )
            dimension_name = clean_cell(
              row[dimension_name_index]
            )

            if dimension_name:
              summary["dimensions"].append(
                (dimension_id, dimension_name)
              )

  return summary


def print_dataset_summary(summary, output):
  """Write a concise summary of the metadata file."""

  output.write("\n" + "=" * 80 + "\n")
  output.write("DATASET SUMMARY\n")
  output.write("=" * 80 + "\n")

  output.write(f"Title: {summary['title']}\n")
  output.write(f"Product ID: {summary['product_id']}\n")
  output.write(f"Frequency: {summary['frequency']}\n")
  output.write(
    f"Reference period: "
    f"{summary['start_period']} to {summary['end_period']}\n"
  )
  output.write(f"Dimensions: {summary['dimension_count']}\n")

  output.write("\nDimension names:\n")

  if summary["dimensions"]:
    for dimension_id, dimension_name in summary["dimensions"]:
      output.write(
        f"    {dimension_id}: {dimension_name}\n"
      )
  else:
    output.write("    <none detected>\n")


# =============================================================================
# METADATA FILE INSPECTION
# =============================================================================

def inspect_metadata_file(file_path, output):
  """Inspect one Statistics Canada metadata CSV file."""

  output.write("\n" + "=" * 80 + "\n")
  output.write(f"FILE: {file_path.name}\n")
  output.write("=" * 80 + "\n")

  with open(
    file_path,
    "r",
    encoding="utf-8-sig",
    newline=""
  ) as file:
    rows = list(csv.reader(file))

  # Remove trailing blank rows.
  while rows and is_blank_row(rows[-1]):
    rows.pop()

  if not rows:
    output.write("WARNING: File is empty.\n")
    return

  output.write(f"Total CSV rows: {len(rows)}\n")

  # Detect metadata tables dynamically.
  tables = detect_tables(rows)

  output.write(f"Detected tables: {len(tables)}\n")

  # Track the original CSV line numbers.
  table_start = 1
  table_number = 1

  for table in tables:
    table_end = table_start + len(table) - 1

    inspect_table(
      table,
      table_number,
      table_start,
      table_end,
      output
    )

    table_start = table_end + 2
    table_number += 1

  # Write the high-level dataset summary.
  summary = extract_dataset_summary(tables)

  print_dataset_summary(summary, output)

  # Run basic structural checks.
  output.write("\nStructural checks:\n")

  if summary["dimension_count"] is not None:
    detected_count = len(summary["dimensions"])

    if isinstance(summary["dimension_count"], int):
      if detected_count == summary["dimension_count"]:
        output.write("    Dimension count: OK\n")
      else:
        output.write(
          "    WARNING: Declared dimension count "
          f"({summary['dimension_count']}) does not match "
          f"detected dimension rows ({detected_count}).\n"
        )

  if len(tables) < 2:
    output.write(
      "    WARNING: Expected dimension information "
      "was not detected.\n"
    )
  else:
    output.write("    Dimension table: detected\n")


# =============================================================================
# MAIN
# =============================================================================

def main():
  """Inspect all metadata CSV files and save the results."""

  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

  metadata_files = sorted(
    METADATA_DIR.glob("*_MetaData.csv")
  )

  with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
  ) as output:

    output.write("01 — Metadata Inspection\n")
    output.write("=" * 80 + "\n")
    output.write(
      f"Metadata directory: {METADATA_DIR}\n"
    )
    output.write(
      f"CSV files found: {len(metadata_files)}\n"
    )

    if not metadata_files:
      output.write(
        "WARNING: No metadata CSV files found.\n"
      )
      return

    for file_path in metadata_files:
      inspect_metadata_file(file_path, output)

  print(f"Metadata inspection complete: {OUTPUT_FILE}")


if __name__ == "__main__":
  main()