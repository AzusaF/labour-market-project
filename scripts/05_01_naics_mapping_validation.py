"""
05 — Industry Classification Mapping
01 - Validate NAICS Mapping

Validates the hand-built NAICS crosswalk (config/naics_mapping.csv)
against the NAICS values that actually appear in the three processed
datasets. The mapping table is a design artifact (how NAICS categories
get harmonized); this script is the safety check that makes sure
the design artifact and the real data still agree before anything
downstream is allowed to JOIN on it.

Output:
- outputs/05_01_naics_mapping_validation.txt
"""

import re
import sys
from pathlib import Path

import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

PROCESSED_DIR = Path("data/processed")
MAPPING_FILE = Path("config/naics_mapping.csv")
OUTPUT_FILE = Path("outputs/05_01_naics_mapping_validation.txt")

# source_table -> processed file that holds its NAICS breakdown.
# labour_force_total.csv is intentionally excluded: it is Canada x Month,
# all industries, and carries no NAICS dimension to validate.
FILE_BY_SOURCE_TABLE = {
    "14100022": "employment.csv",
    "14100063": "wages.csv",
    "14100372": "vacancies.csv",
}

# Column names in config/naics_mapping.csv.
MAPPING_SOURCE_TABLE_COLUMN = "source_table"
MAPPING_ORIGINAL_COLUMN = "naics_original"
MAPPING_TYPE_COLUMN = "mapping_type"

# mapping_type values that are expected to survive into data/processed/.
PRESENT_MAPPING_TYPES = {
    "direct",
    "component",
    "exclude_redundant",
    "aggregate_qa",
}

# mapping_type values that are expected to have been filtered out by
# 07_transform, and should therefore NOT appear in data/processed/.
ABSENT_MAPPING_TYPES = {
    "residual_excluded",
}

# Matches a trailing " [21, 2100]" / " [55-56]" style code suffix, so the
# processed-file label can be compared against the code-free mapping
# table label. The code itself is not used as part of the key, since it
# is written inconsistently across the three source tables.
CODE_SUFFIX_PATTERN = re.compile(r"\s*\[[^\]]*\]\s*$")


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


def strip_code_suffix(label):
    """Remove a trailing ' [code]' suffix so labels compare on name alone."""
    return CODE_SUFFIX_PATTERN.sub("", label).strip()


def load_naics_labels(file_path):
    """
    Read the NAICS column from one processed CSV and return its unique,
    code-stripped labels as a set.

    Processed files are small enough (relative to the raw extracted
    files) that reading the full file rather than a single column is
    not worth the extra complexity here.
    """
    df = pd.read_csv(file_path, low_memory=False)

    if "NAICS" not in df.columns:
        raise ValueError(
            f"'NAICS' column not found in {file_path}"
        )

    labels = df["NAICS"].dropna().map(strip_code_suffix)

    return set(labels.unique())


def load_mapping_table(file_path):
    """Load the hand-built NAICS crosswalk from config/."""
    df = pd.read_csv(
        file_path,
        dtype={MAPPING_SOURCE_TABLE_COLUMN: str},
    )

    required_columns = [
        MAPPING_SOURCE_TABLE_COLUMN,
        MAPPING_ORIGINAL_COLUMN,
        MAPPING_TYPE_COLUMN,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Mapping file is missing required column(s): "
            f"{missing_columns}"
        )

    return df


def check_composite_key(mapping_df, file):
    """
    Check that (source_table, naics_original) is unique.

    naics_original alone is NOT expected to be unique, since the same
    category name legitimately recurs across the three source tables.
    """
    key_columns = [
        MAPPING_SOURCE_TABLE_COLUMN,
        MAPPING_ORIGINAL_COLUMN,
    ]

    duplicate_count = mapping_df.duplicated(subset=key_columns).sum()

    print_subsection("MAPPING TABLE — KEY CHECK", file=file)

    print(
        f"Rows in mapping table                          : "
        f"{len(mapping_df):,}",
        file=file,
    )
    print(
        f"Duplicate (source_table, naics_original) rows  : "
        f"{duplicate_count:,}",
        file=file,
    )

    return duplicate_count == 0


def check_unknown_mapping_types(mapping_df, file):
    """
    Check that every mapping_type value is one this script knows how to
    handle. An unrecognized value would otherwise silently fall through
    both the present/absent checks below and never get validated.
    """
    known_types = PRESENT_MAPPING_TYPES | ABSENT_MAPPING_TYPES

    actual_types = set(mapping_df[MAPPING_TYPE_COLUMN].dropna().unique())

    unknown_types = sorted(actual_types - known_types)

    print_subsection("MAPPING TABLE — KNOWN mapping_type CHECK", file=file)

    if unknown_types:
        print("Unrecognized mapping_type value(s):", file=file)

        for value in unknown_types:
            print(f"  - {value}", file=file)
    else:
        print("All mapping_type values recognized.", file=file)

    return not unknown_types


def validate_source_table(source_table, mapping_df, data_labels, file):
    """
    Compare one source table's mapping rows against its processed file.

    Returns True if this source table passes every check, False
    otherwise.
    """
    table_rows = mapping_df[
        mapping_df[MAPPING_SOURCE_TABLE_COLUMN] == source_table
    ]

    expected_labels = set(
        table_rows.loc[
            table_rows[MAPPING_TYPE_COLUMN].isin(PRESENT_MAPPING_TYPES),
            MAPPING_ORIGINAL_COLUMN,
        ]
    )

    residual_labels = set(
        table_rows.loc[
            table_rows[MAPPING_TYPE_COLUMN].isin(ABSENT_MAPPING_TYPES),
            MAPPING_ORIGINAL_COLUMN,
        ]
    )

    missing_from_data = sorted(expected_labels - data_labels)
    unexpected_residual = sorted(residual_labels & data_labels)
    unmapped_in_data = sorted(
        data_labels - expected_labels - residual_labels
    )

    print(
        f"Expected labels (present-type)  : "
        f"{len(expected_labels):,}",
        file=file,
    )
    print(
        f"Residual labels (should be absent): "
        f"{len(residual_labels):,}",
        file=file,
    )
    print(
        f"Labels actually in processed file : "
        f"{len(data_labels):,}",
        file=file,
    )

    print(file=file)
    print(
        f"Expected but missing from data ({len(missing_from_data)}):",
        file=file,
    )

    for label in missing_from_data:
        print(f"  - {label}", file=file)

    print(file=file)
    print(
        f"Residual labels found in data — should have been "
        f"filtered in 04 ({len(unexpected_residual)}):",
        file=file,
    )

    for label in unexpected_residual:
        print(f"  - {label}", file=file)

    print(file=file)
    print(
        f"In data but not in mapping table at all "
        f"({len(unmapped_in_data)}):",
        file=file,
    )

    for label in unmapped_in_data:
        print(f"  - {label}", file=file)

    return not (missing_from_data or unexpected_residual or unmapped_in_data)


# =============================================================================
# MAIN
# =============================================================================

def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as output_file:
        print_section(
            "NAICS MAPPING VALIDATION (per source table)",
            file=output_file,
        )

        print(f"Mapping file  : {MAPPING_FILE}", file=output_file)
        print(f"Processed dir : {PROCESSED_DIR}", file=output_file)
        print(f"Output file   : {OUTPUT_FILE}", file=output_file)

        # ---------------------------------------------------------------
        # Load mapping table and run table-wide checks
        # ---------------------------------------------------------------

        mapping_df = load_mapping_table(MAPPING_FILE)

        key_ok = check_composite_key(mapping_df, output_file)
        types_ok = check_unknown_mapping_types(mapping_df, output_file)

        # ---------------------------------------------------------------
        # Validate each source table against its own processed file
        # ---------------------------------------------------------------

        print_section(
            "PER-SOURCE-TABLE VALIDATION",
            file=output_file,
        )

        table_results = {}

        for source_table, file_name in FILE_BY_SOURCE_TABLE.items():
            file_path = PROCESSED_DIR / file_name

            print_subsection(
                f"{source_table} → {file_name}",
                file=output_file,
            )

            if not file_path.exists():
                print(
                    f"Processed file not found: {file_path}",
                    file=output_file,
                )
                table_results[source_table] = False
                continue

            data_labels = load_naics_labels(file_path)

            table_results[source_table] = validate_source_table(
                source_table,
                mapping_df,
                data_labels,
                output_file,
            )

        # ---------------------------------------------------------------
        # Verdict
        # ---------------------------------------------------------------

        print_section("VALIDATION RESULT", file=output_file)

        all_ok = key_ok and types_ok and all(table_results.values())

        for source_table, passed in table_results.items():
            status = "PASSED" if passed else "FAILED"

            print(f"{source_table}: {status}", file=output_file)

        print(file=output_file)
        print(
            f"Overall status: {'PASSED' if all_ok else 'FAILED'}",
            file=output_file,
        )

    if all_ok:
        print(f"Validation passed. Report written to: {OUTPUT_FILE}")
    else:
        print(
            f"Validation FAILED — see report for details: {OUTPUT_FILE}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()