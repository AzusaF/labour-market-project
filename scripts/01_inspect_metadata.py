# # from pathlib import Path
# # import pandas as pd


# # METADATA_DIR = Path("data/metadata")


# # def inspect_metadata(metadata_dir: Path) -> None:
# #     """Inspect all metadata CSV files in the specified directory."""

# #     metadata_files = sorted(metadata_dir.rglob("*.csv"))

# #     if not metadata_files:
# #         print(f"No CSV files found in {metadata_dir}")
# #         return

# #     print(f"Found {len(metadata_files)} metadata CSV file(s).\n")

# #     for file_path in metadata_files:
# #         print("=" * 80)
# #         print(f"File: {file_path}")
# #         print("=" * 80)

# #         df = pd.read_csv(file_path)

# #         print(f"Rows: {len(df):,}")
# #         print(f"Columns: {len(df.columns):,}")
# #         print("\nColumn names:")
        
# #         for column in df.columns:
# #             print(f"  - {column}")

# #         print()


# # if __name__ == "__main__":
# #     inspect_metadata(METADATA_DIR)

# from pathlib import Path
# import csv


# # ============================================================
# # Configuration
# # ============================================================

# DATA_DIR = Path("data/metadata")


# # ============================================================
# # Helper functions
# # ============================================================

# def is_blank_row(row):
#     """Return True if a CSV row contains no meaningful values."""
#     return not any(cell.strip() for cell in row)


# def is_separator_row(row):
#     """
#     Detect rows that are likely to separate metadata tables.

#     A separator row is treated as a row where all cells are empty.
#     """
#     return is_blank_row(row)


# def inspect_csv(file_path):
#     """
#     Inspect the structure of a metadata CSV file without assuming
#     the number of tables, columns, or sections.
#     """

#     print("=" * 80)
#     print(f"FILE: {file_path.name}")
#     print("=" * 80)

#     tables = []
#     current_table = []
#     table_start_line = None

#     with file_path.open(
#         mode="r",
#         encoding="utf-8-sig",
#         newline=""
#     ) as f:

#         reader = csv.reader(f)

#         for line_number, row in enumerate(reader, start=1):

#             # ------------------------------------------------
#             # Blank row = possible boundary between tables
#             # ------------------------------------------------
#             if is_separator_row(row):

#                 if current_table:
#                     tables.append({
#                         "start_line": table_start_line,
#                         "end_line": line_number - 1,
#                         "rows": current_table,
#                     })

#                     current_table = []
#                     table_start_line = None

#                 continue

#             # ------------------------------------------------
#             # Start a new table
#             # ------------------------------------------------
#             if table_start_line is None:
#                 table_start_line = line_number

#             current_table.append(row)

#         # ----------------------------------------------------
#         # Save final table
#         # ----------------------------------------------------
#         if current_table:
#             tables.append({
#                 "start_line": table_start_line,
#                 "end_line": line_number,
#                 "rows": current_table,
#             })

#     # ========================================================
#     # Print inspection result
#     # ========================================================

#     print(f"\nDetected tables: {len(tables)}")

#     for table_number, table in enumerate(tables, start=1):

#         rows = table["rows"]

#         # Number of columns can vary between rows, so inspect
#         # every row rather than assuming the first row is enough.
#         column_counts = [len(row) for row in rows]

#         min_columns = min(column_counts)
#         max_columns = max(column_counts)

#         print("\n" + "-" * 80)
#         print(f"TABLE {table_number}")
#         print("-" * 80)

#         print(
#             f"Rows: {len(rows)} "
#             f"(CSV lines {table['start_line']}–{table['end_line']})"
#         )

#         if min_columns == max_columns:
#             print(f"Columns: {max_columns}")
#         else:
#             print(
#                 f"Columns: {min_columns}–{max_columns} "
#                 f"(variable row width)"
#             )

#         # ----------------------------------------------------
#         # Assume the first row of the detected table is the
#         # header, but explicitly report it as a candidate.
#         # ----------------------------------------------------

#         header = rows[0]

#         print("\nCandidate column names:")

#         for column_number, column_name in enumerate(header, start=1):

#             column_name = column_name.strip()

#             if column_name:
#                 print(f"  {column_number:>3}: {column_name}")
#             else:
#                 print(f"  {column_number:>3}: <EMPTY>")

#         # ----------------------------------------------------
#         # Show first few data rows for structural verification
#         # ----------------------------------------------------

#         preview_rows = rows[1:4]

#         if preview_rows:
#             print("\nFirst data rows:")

#             for row_number, row in enumerate(preview_rows, start=1):
#                 print(f"  Row {row_number}: {row}")

#     return tables


# # ============================================================
# # Main
# # ============================================================

# def main():

#     metadata_files = sorted(DATA_DIR.glob("*.csv"))

#     if not metadata_files:
#         print(f"No CSV files found in: {DATA_DIR}")
#         return

#     print(f"Metadata directory: {DATA_DIR}")
#     print(f"CSV files found: {len(metadata_files)}")

#     for file_path in metadata_files:
#         inspect_csv(file_path)


# if __name__ == "__main__":
#     main()


from pathlib import Path
import csv


# Directory containing Statistics Canada metadata CSV files
METADATA_DIR = Path("data/metadata")


def is_blank_row(row):
    """Return True if the row is empty or contains only blank cells."""
    return not row or all(cell.strip() == "" for cell in row)


def detect_tables(rows):
    """
    Split a metadata CSV into tables using blank rows as table separators.
    """
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


def inspect_table(table, table_number, start_line, end_line):
    """Print structural information and a small preview of a metadata table."""

    print("\n" + "-" * 80)
    print(f"TABLE {table_number}")
    print("-" * 80)

    print(f"Rows: {len(table)} (CSV lines {start_line}–{end_line})")

    # Check whether all rows have the same number of columns
    widths = [len(row) for row in table]
    min_width = min(widths)
    max_width = max(widths)

    if min_width == max_width:
        print(f"Columns: {max_width}")
    else:
        print(
            f"Columns: {min_width}–{max_width} "
            "(variable row width)"
        )
        print("WARNING: Row widths are not consistent.")

    # Treat the first row as the table header
    header = table[0]

    print("\nColumns:")

    for column_number, column_name in enumerate(header, start=1):
        column_name = clean_cell(column_name)

        if column_name:
            print(f"    {column_number}: {column_name}")
        else:
            print(f"    {column_number}: <blank>")

    # Show a small preview of the first data rows
    if len(table) > 1:
        print("\nFirst data rows:")

        preview_rows = table[1:4]

        for row_number, row in enumerate(preview_rows, start=1):
            cleaned_row = [clean_cell(value) for value in row]
            print(f"  Row {row_number}: {cleaned_row}")
    else:
        print("\nFirst data rows:")
        print("  <none>")


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


def print_dataset_summary(summary):
    """Print a concise summary of the metadata file."""

    print("\n" + "=" * 80)
    print("DATASET SUMMARY")
    print("=" * 80)

    print(f"Title: {summary['title']}")
    print(f"Product ID: {summary['product_id']}")
    print(f"Frequency: {summary['frequency']}")
    print(
        f"Reference period: "
        f"{summary['start_period']} to {summary['end_period']}"
    )
    print(f"Dimensions: {summary['dimension_count']}")

    print("\nDimension names:")

    if summary["dimensions"]:
        for dimension_id, dimension_name in summary["dimensions"]:
            print(f"    {dimension_id}: {dimension_name}")
    else:
        print("    <none detected>")


def inspect_metadata_file(file_path):
    """Inspect one Statistics Canada metadata CSV file."""

    print("\n" + "=" * 80)
    print(f"FILE: {file_path.name}")
    print("=" * 80)

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        rows = list(csv.reader(file))

    # Remove trailing blank rows
    while rows and is_blank_row(rows[-1]):
        rows.pop()

    if not rows:
        print("WARNING: File is empty.")
        return

    print(f"Total CSV rows: {len(rows)}")

    # Detect tables dynamically
    tables = detect_tables(rows)

    print(f"Detected tables: {len(tables)}")

    # Track the original CSV line numbers
    table_start = 1
    table_number = 1

    for table in tables:

        # Find the actual end line based on table length
        table_end = table_start + len(table) - 1

        inspect_table(
            table,
            table_number,
            table_start,
            table_end
        )

        table_start = table_end + 2
        table_number += 1

    # Print high-level dataset summary
    summary = extract_dataset_summary(tables)

    print_dataset_summary(summary)

    # Basic structural checks
    print("\nStructural checks:")

    if summary["dimension_count"] is not None:
        detected_count = len(summary["dimensions"])

        if isinstance(summary["dimension_count"], int):
            if detected_count == summary["dimension_count"]:
                print("    Dimension count: OK")
            else:
                print(
                    "    WARNING: Declared dimension count "
                    f"({summary['dimension_count']}) does not match "
                    f"detected dimension rows ({detected_count})."
                )

    if len(tables) < 2:
        print("    WARNING: Expected dimension information was not detected.")
    else:
        print("    Dimension table: detected")


def main():
    """Inspect all metadata CSV files in the metadata directory."""

    print(f"Metadata directory: {METADATA_DIR}")

    metadata_files = sorted(
        METADATA_DIR.glob("*_MetaData.csv")
    )

    print(f"CSV files found: {len(metadata_files)}")

    if not metadata_files:
        print("WARNING: No metadata CSV files found.")
        return

    for file_path in metadata_files:
        inspect_metadata_file(file_path)


if __name__ == "__main__":
    main()

