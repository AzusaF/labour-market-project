"""
09 — Data Warehouse
01 - Load Tables into DuckDB

Loads the four analysis-ready tables from 07_transform and the NAICS
crosswalk from config/ into a DuckDB database file. Each CREATE is
idempotent (CREATE OR REPLACE), so this script can be re-run safely
after a data refresh without manual cleanup.

After loading, each table's row count is checked against its source
CSV's row count. This is a narrower check than the full 08_02
validation — it only confirms that DuckDB's CSV reader didn't drop or
duplicate rows on the way in (e.g. due to quoting or type-inference
issues), not that the data is semantically correct.

Output:
- data/warehouse.duckdb
- outputs/09_01_load_report.txt
"""

import sys
from pathlib import Path

import duckdb
import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

PROCESSED_DIR = Path("data/processed")
MAPPING_FILE = Path("config/naics_mapping.csv")
DB_FILE = Path("data/warehouse.duckdb")
OUTPUT_FILE = Path("outputs/09_01_load_report.txt")

# table_name -> source CSV. naics_mapping is included here so the whole
# warehouse load goes through one loop instead of a special case.
TABLE_SOURCES = {
    "employment": PROCESSED_DIR / "employment.csv",
    "wages": PROCESSED_DIR / "wages.csv",
    "vacancies": PROCESSED_DIR / "vacancies.csv",
    "labour_force_total": PROCESSED_DIR / "labour_force_total.csv",
    "naics_mapping": MAPPING_FILE,
}


# =============================================================================
# HELPERS
# =============================================================================

def print_section(title, file=None):
    """Print a formatted section header."""
    print(file=file)
    print("=" * 80, file=file)
    print(title, file=file)
    print("=" * 80, file=file)


def print_subsection(title, file=None):
    """Print a smaller subsection header."""
    print(file=file)
    print(f"[{title}]", file=file)


def count_csv_rows(file_path):
    """
    Count data rows in a CSV without loading the whole file into memory,
    so this check stays cheap even on the larger processed files.
    """
    with file_path.open("r", encoding="utf-8") as csv_file:
        row_count = sum(1 for _ in csv_file) - 1  # minus the header row

    return row_count


def load_table(connection, table_name, file_path):
    """
    Load one CSV into DuckDB as table_name.

    CREATE OR REPLACE makes this idempotent: re-running the script after
    an upstream data refresh overwrites the table instead of erroring
    out on "table already exists".
    """
    connection.execute(
        f"""
        CREATE OR REPLACE TABLE {table_name} AS
        SELECT * FROM read_csv_auto(?, header = true)
        """,
        [str(file_path)],
    )


def check_row_count(connection, table_name, file_path, file):
    """Compare the loaded table's row count against the source CSV."""
    csv_row_count = count_csv_rows(file_path)

    db_row_count = connection.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()[0]

    print(
        f"CSV rows   : {csv_row_count:,}",
        file=file,
    )
    print(
        f"DuckDB rows: {db_row_count:,}",
        file=file,
    )

    return csv_row_count == db_row_count


def print_schema(connection, table_name, file):
    """Print the DESCRIBE output for one table."""
    schema = connection.execute(
        f"DESCRIBE {table_name}"
    ).fetchdf()

    print(
        schema[["column_name", "column_type"]].to_string(index=False),
        file=file,
    )


# =============================================================================
# MAIN
# =============================================================================

def main():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(DB_FILE))

    with OUTPUT_FILE.open("w", encoding="utf-8") as output_file:
        print_section("DUCKDB LOAD", file=output_file)

        print(f"Database file: {DB_FILE}", file=output_file)
        print(f"Output file  : {OUTPUT_FILE}", file=output_file)

        all_ok = True

        # -----------------------------------------------------------------
        # Load each table and verify its row count
        # -----------------------------------------------------------------

        for table_name, file_path in TABLE_SOURCES.items():
            print_subsection(table_name, file=output_file)

            if not file_path.exists():
                print(
                    f"Source file not found, skipped: {file_path}",
                    file=output_file,
                )

                all_ok = False
                continue

            load_table(connection, table_name, file_path)

            row_count_ok = check_row_count(
                connection,
                table_name,
                file_path,
                output_file,
            )

            print(file=output_file)
            print("Schema:", file=output_file)

            print_schema(connection, table_name, output_file)

            if not row_count_ok:
                print(file=output_file)
                print(
                    "Row count MISMATCH — investigate before using "
                    "this table.",
                    file=output_file,
                )

                all_ok = False

        # -----------------------------------------------------------------
        # Verdict
        # -----------------------------------------------------------------

        print_section("LOAD RESULT", file=output_file)

        print(
            f"Status: {'PASSED' if all_ok else 'FAILED'}",
            file=output_file,
        )

    connection.close()

    if all_ok:
        print(
            f"Load complete. Database: {DB_FILE} | "
            f"Report: {OUTPUT_FILE}"
        )
    else:
        print(
            f"Load completed with issues — see report: {OUTPUT_FILE}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()