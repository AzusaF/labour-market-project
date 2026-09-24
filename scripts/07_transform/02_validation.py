"""
07 — Data Transformation
02 — Transformation Validation

Validates processed datasets against their corresponding extracted datasets.

The processed tables are compared with the expected result of the documented
transformation rules, not with the raw extract. Differences that follow from
those rules are reported as NOTE. Differences the rules do not explain are
reported as WARNING.

Status levels:
- OK:      the processed table matches the expectation.
- NOTE:    the processed table differs from the extract by design.
- WARNING: unexpected difference that needs review.

Transformation rules reflected in the expectations:
- Canada only
- Analysis period 2021-01 to 2025-12
- Selected measures and dimensions only
- NAICS label normalization
- Suppressed observations (x) removed before reshaping
- Unreliable observations (F) set to NULL, quality flag kept

Checks:
- Dataset correspondence
- Row counts (expected vs. actual)
- Column structure
- Date coverage
- Geography
- NAICS coverage
- Duplicate rows
- Missing values
- Expected analytical grain
- Value reconciliation (sampled values and flags vs. the extract)
- Quality flag columns (vacancies)
- Internal consistency (labour force total)

The value reconciliation reads values directly from the extract and does not
reuse any function of 01_transform.py, so that a bug in the transformation
cannot be repeated here.

Input:
- data/extracted/*.csv
- data/processed/*.csv

Output:
- outputs/07_transform/02_validation.txt
"""

from pathlib import Path

import numpy as np
import pandas as pd


EXTRACTED_DIR = Path("data/extracted")
PROCESSED_DIR = Path("data/processed")
OUTPUT_FILE = Path("outputs/07_transform/02_validation.txt")

# These constants must match 01_transform.py.
START_DATE = pd.Timestamp("2021-01-01")
END_DATE = pd.Timestamp("2025-12-01")
EXPECTED_GEO = "Canada"

NAICS_LABEL_FIXES = {
    "[55, 56]": "[55-56]",
    "[52, 53]": "[52-53]",
}

TOTAL_ALL_INDUSTRIES = "Total, all industries"

# Statistics Canada data quality indicators (A = best, F = unreliable).
QUALITY_FLAGS = ["A", "B", "C", "D", "E", "F"]

# Value reconciliation: number of random rows checked per table.
# Tables with at most SAMPLE_ALL_BELOW rows are checked completely.
SAMPLE_SIZE = 20
SAMPLE_SEED = 42
SAMPLE_ALL_BELOW = 100

# Internal consistency tolerances of the labour force total.
# Source values are rounded to 0.1 thousand and 0.1 percent.
IDENTITY_TOLERANCE_THOUSANDS = 0.3
RATE_TOLERANCE_PCT = 0.15

# "filters" and "suppressed_flags" must match the row selection and the
# flag handling in 01_transform.py.
#
# flag_handling:
# - "remove": observations with the flag are removed before reshaping
# - "null":   observations with the flag are kept, value set to NULL
#
# value_columns: processed column -> measure in the extract
# (and the processed column that holds its quality flag, if any).
#
# Filters on "_naics" use the normalized NAICS label.
DATASETS = {
    "employment": {
        "id": "14100022",
        "processed": "employment.csv",
        "measure_column": "Labour force characteristics",
        "filters": {
            "Labour force characteristics": ["Employment"],
            "Gender": ["Total - Gender"],
            "Age group": ["15 years and over"],
        },
        "suppressed_flags": ["x"],
        "flag_handling": "remove",
        "total_label": TOTAL_ALL_INDUSTRIES,
        "expected_columns": [
            "REF_DATE",
            "GEO",
            "NAICS",
            "Employment_thousands",
        ],
        "value_columns": {
            "Employment_thousands": {"measure": "Employment"},
        },
    },
    "wages": {
        "id": "14100063",
        "processed": "wages.csv",
        "measure_column": "Wages",
        "filters": {
            "Wages": [
                "Average hourly wage rate",
                "Median hourly wage rate",
                "Total employees, all wages",
            ],
            "Gender": ["Total - Gender"],
            "Age group": ["15 years and over"],
            "Type of work": ["Both full- and part-time employees"],
        },
        "suppressed_flags": ["x"],
        "flag_handling": "remove",
        "total_label": "Total employees, all industries",
        "expected_columns": [
            "REF_DATE",
            "GEO",
            "NAICS",
            "Average_hourly_wage_cad",
            "Median_hourly_wage_cad",
            "Total_employees_thousands",
        ],
        "value_columns": {
            "Average_hourly_wage_cad": {
                "measure": "Average hourly wage rate",
            },
            "Median_hourly_wage_cad": {
                "measure": "Median hourly wage rate",
            },
            "Total_employees_thousands": {
                "measure": "Total employees, all wages",
            },
        },
    },
    "vacancies": {
        "id": "14100372",
        "processed": "vacancies.csv",
        "measure_column": "Statistics",
        "filters": {},
        "suppressed_flags": ["F"],
        "flag_handling": "null",
        "total_label": TOTAL_ALL_INDUSTRIES,
        "expected_columns": [
            "REF_DATE",
            "GEO",
            "NAICS",
            "Job_vacancies",
            "Payroll_employees",
            "Job_vacancy_rate_pct",
            "Job_vacancies_quality",
            "Payroll_employees_quality",
            "Job_vacancy_rate_quality",
        ],
        "value_columns": {
            "Job_vacancies": {
                "measure": "Job vacancies",
                "quality": "Job_vacancies_quality",
            },
            "Payroll_employees": {
                "measure": "Payroll employees",
                "quality": "Payroll_employees_quality",
            },
            "Job_vacancy_rate_pct": {
                "measure": "Job vacancy rate",
                "quality": "Job_vacancy_rate_quality",
            },
        },
    },
    "labour_force_total": {
        "id": "14100022",
        "processed": "labour_force_total.csv",
        "measure_column": "Labour force characteristics",
        "filters": {
            "_naics": [TOTAL_ALL_INDUSTRIES],
            "Labour force characteristics": [
                "Labour force",
                "Employment",
                "Unemployment",
                "Unemployment rate",
            ],
            "Gender": ["Total - Gender"],
            "Age group": ["15 years and over"],
        },
        "suppressed_flags": ["x"],
        "flag_handling": "remove",
        "has_naics": False,
        "fixed_naics": TOTAL_ALL_INDUSTRIES,
        "grain": ["GEO", "REF_DATE"],
        "expected_columns": [
            "REF_DATE",
            "GEO",
            "Labour_force_thousands",
            "Employment_thousands",
            "Unemployment_thousands",
            "Unemployment_rate_pct",
        ],
        "value_columns": {
            "Labour_force_thousands": {"measure": "Labour force"},
            "Employment_thousands": {"measure": "Employment"},
            "Unemployment_thousands": {"measure": "Unemployment"},
            "Unemployment_rate_pct": {"measure": "Unemployment rate"},
        },
    },
}


class Report:
    """Collect report lines and count check statuses."""

    def __init__(self):
        self.lines = []
        self.counts = {"OK": 0, "NOTE": 0, "WARNING": 0}

    def add(self, text=""):
        self.lines.append(text)

    def info(self, text):
        self.lines.append(f"- {text}")

    def sub(self, text):
        self.lines.append(f"  - {text}")

    def check(self, status, text):
        self.counts[status] += 1
        self.lines.append(f"- [{status}] {text}")


def has_naics(config):
    """Return True if the processed table has an industry column."""
    return config.get("has_naics", True)


def quality_columns(config):
    """Return the processed columns that hold quality flags."""
    return [
        spec["quality"]
        for spec in config["value_columns"].values()
        if "quality" in spec
    ]


def find_dataset(directory, dataset_id):
    """Find the CSV file for a dataset ID."""
    files = sorted(directory.glob(f"*{dataset_id}*.csv"))

    if not files:
        raise FileNotFoundError(
            f"No CSV found for {dataset_id} in {directory}"
        )

    return files[0]


def get_date_column(df):
    """Return the reference date column if available."""
    for column in df.columns:
        if "ref_date" in column.lower():
            return column

    for column in df.columns:
        if "reference period" in column.lower():
            return column

    return None


def get_naics_column(df):
    """Return the NAICS column if available."""
    for column in df.columns:
        if column.lower() == "naics":
            return column

    for column in df.columns:
        if "naics" in column.lower():
            return column

    return None


def normalize_naics(labels):
    """Apply the same NAICS label fixes as the transformation."""
    labels = pd.Series(labels)

    for old, new in NAICS_LABEL_FIXES.items():
        labels = labels.str.replace(old, new, regex=False)

    return labels


def explain_missing(column, df):
    """Explain why an extracted column contains missing cells."""
    if df[column].isna().all():
        return "empty metadata column"

    if column == "STATUS":
        return "no quality flag (valid observation)"

    if column == "VALUE":
        return "no value published (suppressed or unreliable)"

    return ""


def select_slice(extracted, config):
    """
    Reproduce the row selection of the transformation.

    Returns:
    - in_scope: Canada within the analysis period
    - selected: in_scope restricted to the selected measures and dimensions
    - kept:     selected observations that enter the reshaping
    - removed:  selected observations removed as suppressed
    - nulled:   selected observations kept with the value set to NULL
    """
    in_scope = extracted[
        (extracted["GEO"] == EXPECTED_GEO)
        & (extracted["_date"] >= START_DATE)
        & (extracted["_date"] <= END_DATE)
    ]

    selected = in_scope

    for column, values in config["filters"].items():
        selected = selected[selected[column].isin(values)]

    if "STATUS" in selected.columns:
        flagged = selected["STATUS"].isin(config["suppressed_flags"])
    else:
        flagged = pd.Series(False, index=selected.index)

    empty = selected.iloc[0:0]

    if config.get("flag_handling", "remove") == "null":
        return in_scope, selected, selected, empty, selected[flagged]

    return in_scope, selected, selected[~flagged], selected[flagged], empty


def check_shape(report, config, extracted_rows, processed, in_scope,
                selected, kept, removed, nulled, expected_rows,
                n_industries, n_months, extracted_columns):
    report.add("2. Shape")
    report.info(f"Extracted rows: {extracted_rows:,}")
    report.info(f"Processed rows: {len(processed):,}")
    report.info(f"Extracted columns: {len(extracted_columns)}")
    report.info(f"Processed columns: {len(processed.columns)}")

    valid_count = len(selected) - len(removed) - len(nulled)

    report.add("- Row funnel (extracted → processed):")
    report.sub(f"Extracted rows: {extracted_rows:,}")
    report.sub(f"After Canada and analysis period: {len(in_scope):,}")
    report.sub(f"After selected measures and dimensions: {len(selected):,}")
    report.sub(f"Suppressed observations removed: {len(removed):,}")

    if config.get("flag_handling") == "null":
        report.sub(
            "Unreliable observations set to NULL (flag kept): "
            f"{len(nulled):,}"
        )

    report.sub(f"Valid observations: {valid_count:,}")
    report.sub(
        f"Expected processed rows (month × industry): {expected_rows:,}"
    )

    if len(processed) == expected_rows:
        report.check(
            "OK",
            "Processed rows match the expected rows "
            f"({len(processed):,}). The reduction from "
            f"{extracted_rows:,} extracted rows is due to the Canada "
            "filter, the analysis period, and the selected measures."
        )
    else:
        report.check(
            "WARNING",
            f"Processed rows ({len(processed):,}) differ from expected "
            f"rows ({expected_rows:,})."
        )

    full_grid = n_industries * n_months

    if expected_rows == full_grid:
        report.check(
            "OK",
            f"Complete month × industry grid: {n_industries} industries "
            f"× {n_months} months = {full_grid:,}."
        )
    else:
        report.check(
            "NOTE",
            f"{full_grid - expected_rows:,} month × industry combinations "
            "have no valid observation (all observations suppressed)."
        )

    report.add()


def check_columns(report, extracted_columns, processed, config):
    report.add("3. Column changes")

    expected = config["expected_columns"]
    actual = list(processed.columns)

    if sorted(actual) == sorted(expected):
        report.check(
            "OK",
            "Processed columns match the expected output structure: "
            + ", ".join(expected)
        )
    else:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))

        report.check(
            "WARNING",
            "Processed columns differ from the expected structure."
        )

        if missing:
            report.sub("Missing: " + ", ".join(missing))

        if unexpected:
            report.sub("Unexpected: " + ", ".join(unexpected))

    removed = sorted(set(extracted_columns) - set(actual))
    added = sorted(set(actual) - set(extracted_columns))

    report.check(
        "NOTE",
        f"Extracted columns not carried over ({len(removed)}): "
        "metadata columns and dimensions collapsed by the filters or "
        "the reshaping."
    )

    for column in removed:
        report.sub(column)

    report.info("Added or renamed in processed: " + ", ".join(added))
    report.add()


def check_dates(report, extracted, processed, processed_date_column,
                n_months):
    report.add("4. Date coverage")

    extracted_dates = extracted["_date"]
    processed_dates = pd.to_datetime(
        processed[processed_date_column],
        errors="coerce",
    )

    report.info(
        f"Extracted: {extracted_dates.min():%Y-%m} → "
        f"{extracted_dates.max():%Y-%m}"
    )
    report.info(
        f"Processed: {processed_dates.min():%Y-%m} → "
        f"{processed_dates.max():%Y-%m}"
    )

    outside = extracted_dates[
        (extracted_dates < START_DATE) | (extracted_dates > END_DATE)
    ]

    if len(outside) > 0:
        report.check(
            "NOTE",
            f"Extracted data covers {outside.nunique()} months outside "
            f"the analysis period ({START_DATE:%Y-%m} → "
            f"{END_DATE:%Y-%m}). These months are trimmed by design."
        )

    if (
        processed_dates.min() == START_DATE
        and processed_dates.max() == END_DATE
    ):
        report.check(
            "OK",
            "Processed date range matches the analysis period."
        )
    else:
        report.check(
            "WARNING",
            "Processed date range differs from the analysis period."
        )

    expected_months = set(
        pd.date_range(START_DATE, END_DATE, freq="MS")
    )
    missing_months = sorted(expected_months - set(processed_dates))

    if missing_months:
        report.check(
            "WARNING",
            "Missing months: "
            + ", ".join(f"{m:%Y-%m}" for m in missing_months)
        )
    else:
        report.check(
            "OK",
            f"All {n_months} months of the analysis period are present."
        )

    report.add()


def check_geography(report, extracted, processed):
    report.add("5. Geography")

    extracted_geo = set(extracted["GEO"].dropna().unique())
    processed_geo = set(processed["GEO"].dropna().unique())

    report.info(f"Extracted unique GEO values: {len(extracted_geo)}")
    report.info(f"Processed unique GEO values: {len(processed_geo)}")

    if processed_geo != {EXPECTED_GEO}:
        report.check(
            "WARNING",
            f"Processed GEO values are not only {EXPECTED_GEO}: "
            + ", ".join(sorted(processed_geo))
        )
    elif extracted_geo != processed_geo:
        report.check(
            "NOTE",
            f"Extracted geographies ({len(extracted_geo)}) are reduced "
            f"to {EXPECTED_GEO} only by design (national-level analysis)."
        )
    else:
        report.check(
            "OK",
            f"Single geography ({EXPECTED_GEO}) in both datasets."
        )

    report.add()


def check_naics(report, extracted, processed, extracted_naics_column,
                processed_naics_column, in_scope, selected, kept, config):
    report.add("6. NAICS coverage")

    raw_labels = sorted(extracted[extracted_naics_column].dropna().unique())
    normalized = normalize_naics(raw_labels)

    for raw, fixed in zip(raw_labels, normalized):
        if raw != fixed:
            report.check("NOTE", f"Label normalized: {raw} → {fixed}")

    all_naics = set(extracted["_naics"].dropna().unique())
    reported_naics = set(selected["_naics"].unique())
    kept_naics = set(kept["_naics"].unique())
    processed_naics = set(
        processed[processed_naics_column].dropna().unique()
    )

    report.info(
        f"Extracted unique NAICS values: {len(raw_labels)} "
        f"({len(all_naics)} after normalization)"
    )
    report.info(f"Processed unique NAICS values: {len(processed_naics)}")

    measure_column = config["measure_column"]
    measures = ", ".join(
        config["filters"].get(measure_column, ["all measures"])
    )

    for naics in sorted(all_naics - reported_naics):
        appears_under = sorted(
            in_scope.loc[
                in_scope["_naics"] == naics, measure_column
            ].dropna().unique()
        )

        if appears_under:
            detail = (
                f"appears only under {measure_column}: "
                + ", ".join(appears_under)
            )
        else:
            detail = "no observations for Canada in the analysis period"

        report.check(
            "NOTE",
            f"{naics} — not reported for the selected measure "
            f"({measures}); {detail}. Excluded by design."
        )

    for naics in sorted(reported_naics - kept_naics):
        report.check(
            "NOTE",
            f"{naics} — every observation is suppressed in the analysis "
            "period. Excluded by design."
        )

    unexpected_missing = sorted(kept_naics - processed_naics)
    unexpected_extra = sorted(processed_naics - all_naics)

    for naics in unexpected_missing:
        report.check(
            "WARNING",
            f"{naics} — has valid observations but is missing from "
            "processed."
        )

    for naics in unexpected_extra:
        report.check(
            "WARNING",
            f"{naics} — in processed but not in the extracted data."
        )

    if not unexpected_missing and not unexpected_extra:
        report.check(
            "OK",
            f"Processed NAICS ({len(processed_naics)}) match the "
            "industries with valid observations for the selected "
            "measures."
        )

    report.add()


def check_duplicates(report, extracted_duplicates, processed):
    report.add("7. Duplicate rows")

    processed_duplicates = processed.duplicated().sum()

    report.info(f"Extracted duplicates: {extracted_duplicates:,}")
    report.info(f"Processed duplicates: {processed_duplicates:,}")

    if processed_duplicates == 0:
        report.check("OK", "No duplicate rows in processed.")
    else:
        report.check("WARNING", "Duplicate rows found in processed.")

    report.add()


def check_missing(report, config, extracted_missing, extracted_view,
                  processed, kept, removed, nulled):
    report.add("8. Missing values")

    report.info(
        f"Extracted missing cells: {extracted_missing.sum():,}"
    )

    for column, count in extracted_missing[
        extracted_missing > 0
    ].sort_values(ascending=False).items():
        explanation = explain_missing(column, extracted_view)
        suffix = f" — {explanation}" if explanation else ""
        report.sub(f"{column}: {count:,}{suffix}")

    processed_missing = processed.isna().sum()

    # Quality flag columns are checked separately (section 11).
    value_missing = processed_missing.drop(
        labels=quality_columns(config),
        errors="ignore",
    )
    value_total = int(value_missing.sum())

    # A removed observation leaves an empty cell only when another measure
    # of the same month × industry is still valid after reshaping.
    kept_keys = set(zip(kept["_date"], kept["_naics"]))
    expected_from_removed = sum(
        (date, naics) in kept_keys
        for date, naics in zip(removed["_date"], removed["_naics"])
    )

    # An observation set to NULL always leaves one empty value cell.
    expected_total = expected_from_removed + len(nulled)

    report.info(f"Processed missing cells: {int(processed_missing.sum()):,}")

    if value_total != expected_total:
        report.check(
            "WARNING",
            f"Processed missing value cells ({value_total:,}) differ from "
            f"the expected count ({expected_total:,})."
        )

        for column, count in value_missing[value_missing > 0].items():
            report.sub(f"{column}: {count:,}")
    elif expected_total == 0:
        report.check(
            "OK",
            "No missing cells in processed. Suppressed observations "
            "are removed before reshaping."
        )
    elif len(nulled) > 0:
        report.check(
            "NOTE",
            f"{value_total:,} missing value cells are expected: each "
            "unreliable observation keeps its row, its value is set to "
            "NULL, and its flag stays in the quality column."
        )

        for column, count in value_missing[value_missing > 0].items():
            report.sub(f"{column}: {count:,}")
    else:
        report.check(
            "NOTE",
            f"{value_total:,} missing cells are expected: each "
            "removed suppressed observation leaves an empty cell where "
            "another measure of the same month × industry is valid."
        )

        for column, count in value_missing[value_missing > 0].items():
            report.sub(f"{column}: {count:,}")

    report.add()


def check_grain(report, processed, selected, config):
    report.add("9. Analytical grain")

    required_grain = config.get("grain", ["GEO", "NAICS", "REF_DATE"])

    missing_grain_columns = [
        column
        for column in required_grain
        if column not in processed.columns
    ]

    report.info("Target grain: " + " × ".join(required_grain))

    if missing_grain_columns:
        report.check(
            "WARNING",
            "Cannot validate grain. Missing columns: "
            + ", ".join(missing_grain_columns)
        )
    else:
        grain_duplicates = processed.duplicated(
            subset=required_grain
        ).sum()

        if grain_duplicates == 0:
            report.check("OK", "No duplicate analytical keys.")
        else:
            report.check(
                "WARNING",
                f"Duplicate analytical keys: {grain_duplicates:,}"
            )

    # Reshaping with an aggregation such as "first" hides duplicates.
    # Confirm that the filters alone already determine the grain.
    source_duplicates = selected.duplicated(
        subset=[
            "_date",
            "GEO",
            "_naics",
            config["measure_column"],
        ]
    ).sum()

    if source_duplicates == 0:
        report.check(
            "OK",
            "Selected extracted rows are unique per month × industry × "
            "measure (the filters fully determine the grain)."
        )
    else:
        report.check(
            "WARNING",
            f"{source_duplicates:,} extracted rows share the same month × "
            "industry × measure. The filters do not fully determine the "
            "grain, so reshaping would silently pick one value. Check "
            "for a missing filter."
        )

    report.add()


def check_values(report, config, processed, selected, date_column,
                 naics_column):
    """
    Compare sampled processed values and quality flags with the extract.

    The lookup is built from the extract with its own code path.
    The sample always contains the first and last month of the Total row.
    """
    report.add("10. Value reconciliation (extracted vs processed)")

    measure_column = config["measure_column"]

    if "STATUS" in selected.columns:
        statuses = selected["STATUS"]
    else:
        statuses = pd.Series(np.nan, index=selected.index)

    keys = list(
        zip(
            selected["_date"],
            selected["_naics"],
            selected[measure_column],
        )
    )
    values = dict(zip(keys, selected["VALUE"]))
    flags = dict(zip(keys, statuses))

    frame = processed.copy()
    frame["_date"] = pd.to_datetime(frame[date_column], errors="coerce")

    if naics_column:
        frame["_naics"] = frame[naics_column]
    else:
        frame["_naics"] = config["fixed_naics"]

    if len(frame) <= SAMPLE_ALL_BELOW:
        sample = frame
        sample_text = f"all {len(frame):,} rows"
    else:
        forced_mask = frame["_date"].isin(
            [frame["_date"].min(), frame["_date"].max()]
        )

        if naics_column and config.get("total_label"):
            forced_mask &= frame["_naics"] == config["total_label"]

        forced = frame[forced_mask]
        rest = frame.drop(forced.index)
        random_rows = rest.sample(
            min(SAMPLE_SIZE, len(rest)),
            random_state=SAMPLE_SEED,
        )
        sample = pd.concat([forced, random_rows])
        sample_text = (
            f"{len(sample):,} of {len(frame):,} rows "
            f"({len(forced):,} first/last month of the Total row, "
            f"{len(random_rows):,} random, seed {SAMPLE_SEED})"
        )

    mismatches = []
    n_compared = 0

    for _, row in sample.iterrows():
        label = f"{row['_date']:%Y-%m} | {row['_naics']}"

        for column, spec in config["value_columns"].items():
            key = (row["_date"], row["_naics"], spec["measure"])

            if key not in values:
                mismatches.append(
                    f"{label} | {column}: key not found in the extract"
                )
                continue

            expected = values[key]
            actual = row[column]
            n_compared += 1

            both_missing = pd.isna(expected) and pd.isna(actual)

            if not both_missing:
                one_missing = pd.isna(expected) or pd.isna(actual)

                if one_missing or not np.isclose(expected, actual):
                    mismatches.append(
                        f"{label} | {column}: extract {expected} "
                        f"≠ processed {actual}"
                    )

            if "quality" in spec:
                n_compared += 1
                expected_flag = flags[key]
                actual_flag = row[spec["quality"]]

                if expected_flag != actual_flag:
                    mismatches.append(
                        f"{label} | {spec['quality']}: extract "
                        f"{expected_flag} ≠ processed {actual_flag}"
                    )

    report.info(f"Rows checked: {sample_text}")
    report.info(f"Values and flags compared: {n_compared:,}")

    if not mismatches:
        report.check(
            "OK",
            "All compared values and flags match the extract."
        )
    else:
        report.check(
            "WARNING",
            f"{len(mismatches):,} mismatch(es) between the extract and "
            "processed."
        )

        for text in mismatches[:10]:
            report.sub(text)

        if len(mismatches) > 10:
            report.sub(f"... and {len(mismatches) - 10:,} more")

    report.add()


def check_quality_flags(report, config, processed):
    """Check the quality flag columns of a processed table."""
    if not quality_columns(config):
        return

    report.add("11. Quality flag columns")

    missing_cells = 0
    invalid_values = []
    inconsistent = []

    for value_column, spec in config["value_columns"].items():
        if "quality" not in spec:
            continue

        quality = processed[spec["quality"]]
        counts = quality.value_counts().sort_index()
        distribution = ", ".join(
            f"{flag} {count:,}" for flag, count in counts.items()
        )
        report.info(f"{spec['quality']}: {distribution}")

        missing_cells += int(quality.isna().sum())

        invalid = set(quality.dropna().unique()) - set(QUALITY_FLAGS)
        if invalid:
            invalid_values.append(
                f"{spec['quality']}: " + ", ".join(sorted(invalid))
            )

        # The value must be NULL exactly when the flag is F.
        if not (processed[value_column].isna() == (quality == "F")).all():
            inconsistent.append(value_column)

    if missing_cells == 0:
        report.check("OK", "No missing quality flags.")
    else:
        report.check(
            "WARNING",
            f"{missing_cells:,} missing quality flag cell(s)."
        )

    if not invalid_values:
        report.check(
            "OK",
            "Quality flags contain only " + ", ".join(QUALITY_FLAGS) + "."
        )
    else:
        report.check("WARNING", "Unexpected quality flag values.")

        for text in invalid_values:
            report.sub(text)

    if not inconsistent:
        report.check(
            "OK",
            "Each value is NULL exactly when its quality flag is F."
        )
    else:
        report.check(
            "WARNING",
            "Value NULLs and F flags do not match in: "
            + ", ".join(inconsistent)
        )

    report.add()


def check_labour_force_consistency(report):
    """Check identities inside labour_force_total and against employment."""
    report.add("12. Internal consistency")

    total = pd.read_csv(PROCESSED_DIR / "labour_force_total.csv")
    employment = pd.read_csv(PROCESSED_DIR / "employment.csv")

    employment_total = employment.loc[
        employment["NAICS"] == TOTAL_ALL_INDUSTRIES,
        ["REF_DATE", "Employment_thousands"],
    ]

    merged = total.merge(
        employment_total,
        on="REF_DATE",
        how="outer",
        suffixes=("", "_employment_table"),
    )

    difference = (
        merged["Employment_thousands"]
        - merged["Employment_thousands_employment_table"]
    ).abs()

    unmatched = int(difference.isna().sum())
    max_difference = difference.max()

    if unmatched == 0 and max_difference < 1e-9:
        report.check(
            "OK",
            "Employment_thousands equals the Total row of employment.csv "
            f"in all {len(merged):,} months."
        )
    else:
        report.check(
            "WARNING",
            "Employment_thousands differs from the Total row of "
            f"employment.csv (unmatched months: {unmatched:,}, "
            f"max difference: {max_difference})."
        )

    gap = (
        total["Labour_force_thousands"]
        - total["Employment_thousands"]
        - total["Unemployment_thousands"]
    ).abs()

    report.info(
        "Max |labour force − employment − unemployment|: "
        f"{gap.max():.2f} thousand"
    )

    if gap.max() <= IDENTITY_TOLERANCE_THOUSANDS:
        report.check(
            "OK",
            "Labour force = employment + unemployment "
            f"(tolerance {IDENTITY_TOLERANCE_THOUSANDS} thousand)."
        )
    else:
        report.check(
            "WARNING",
            "Labour force differs from employment + unemployment by more "
            f"than {IDENTITY_TOLERANCE_THOUSANDS} thousand in "
            f"{int((gap > IDENTITY_TOLERANCE_THOUSANDS).sum()):,} "
            "month(s). Review how the Total row is defined."
        )

    implied_rate = (
        total["Unemployment_thousands"]
        / total["Labour_force_thousands"]
        * 100
    )
    rate_gap = (implied_rate - total["Unemployment_rate_pct"]).abs()

    report.info(
        "Max |implied rate − published rate|: "
        f"{rate_gap.max():.3f} percentage points"
    )

    if rate_gap.max() <= RATE_TOLERANCE_PCT:
        report.check(
            "OK",
            "Unemployment rate = unemployment / labour force "
            f"(tolerance {RATE_TOLERANCE_PCT} percentage points)."
        )
    else:
        report.check(
            "WARNING",
            "Unemployment rate differs from unemployment / labour force "
            f"by more than {RATE_TOLERANCE_PCT} percentage points in "
            f"{int((rate_gap > RATE_TOLERANCE_PCT).sum()):,} month(s)."
        )

    report.add()


def validate_dataset(name, config):
    """Validate one processed dataset against its extracted source."""
    dataset_id = config["id"]

    extracted_path = find_dataset(EXTRACTED_DIR, dataset_id)
    processed_path = PROCESSED_DIR / config["processed"]

    if not processed_path.exists():
        raise FileNotFoundError(
            f"Processed file not found: {processed_path}"
        )

    extracted = pd.read_csv(extracted_path, low_memory=False)
    processed = pd.read_csv(processed_path, low_memory=False)

    # Collect statistics of the original extract before adding helper
    # columns.
    extracted_rows = len(extracted)
    extracted_columns = list(extracted.columns)
    extracted_missing = extracted.isna().sum()
    extracted_duplicates = extracted.duplicated().sum()
    extracted_view = extracted.copy()

    extracted_date_column = get_date_column(extracted)
    extracted_naics_column = get_naics_column(extracted)
    processed_date_column = get_date_column(processed)
    processed_naics_column = (
        get_naics_column(processed) if has_naics(config) else None
    )

    required = {
        "extracted date": extracted_date_column,
        "extracted NAICS": extracted_naics_column,
        "processed date": processed_date_column,
    }

    if has_naics(config):
        required["processed NAICS"] = processed_naics_column

    for label, column in required.items():
        if column is None:
            raise ValueError(f"{name}: {label} column not found.")

    # Helper columns: parsed date and normalized NAICS label.
    extracted["_date"] = pd.to_datetime(
        extracted[extracted_date_column],
        errors="coerce",
    )
    extracted["_naics"] = normalize_naics(
        extracted[extracted_naics_column]
    )

    in_scope, selected, kept, removed, nulled = select_slice(
        extracted,
        config,
    )

    n_months = len(pd.date_range(START_DATE, END_DATE, freq="MS"))
    n_industries = kept["_naics"].nunique()
    expected_rows = len(
        kept[["_date", "_naics"]].drop_duplicates()
    )

    report = Report()

    report.add(f"Dataset: {name} ({dataset_id})")
    report.add("=" * 80)

    report.add("1. Dataset correspondence")
    report.info(f"Extracted: {extracted_path.name}")
    report.info(f"Processed: {processed_path.name}")
    report.add()

    check_shape(
        report, config, extracted_rows, processed, in_scope, selected,
        kept, removed, nulled, expected_rows, n_industries, n_months,
        extracted_columns,
    )
    check_columns(report, extracted_columns, processed, config)
    check_dates(
        report, extracted, processed, processed_date_column, n_months,
    )
    check_geography(report, extracted, processed)

    if has_naics(config):
        check_naics(
            report, extracted, processed, extracted_naics_column,
            processed_naics_column, in_scope, selected, kept, config,
        )
    else:
        report.add("6. NAICS coverage")
        report.info(
            "Not applicable: the table holds the all-industries total "
            f"only ({config['fixed_naics']})."
        )
        report.add()

    check_duplicates(report, extracted_duplicates, processed)
    check_missing(
        report, config, extracted_missing, extracted_view, processed,
        kept, removed, nulled,
    )
    check_grain(report, processed, selected, config)
    check_values(
        report, config, processed, selected, processed_date_column,
        processed_naics_column,
    )
    check_quality_flags(report, config, processed)

    return report


def main():
    """Validate all extracted and processed dataset pairs."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    reports = {}

    for name, config in DATASETS.items():
        reports[name] = validate_dataset(name, config)

    # Internal consistency of the labour force total.
    check_labour_force_consistency(reports["labour_force_total"])

    total = {"OK": 0, "NOTE": 0, "WARNING": 0}
    summary = []

    for name, report in reports.items():
        counts = report.counts

        for status, count in counts.items():
            total[status] += count

        summary.append(
            f"- {name}: OK {counts['OK']}, "
            f"NOTE {counts['NOTE']}, "
            f"WARNING {counts['WARNING']}"
        )

    if total["WARNING"] == 0:
        overall = (
            "Overall: no unexpected differences found. All differences "
            "between extracted and processed data follow from the "
            "transformation rules."
        )
    else:
        overall = (
            f"Overall: {total['WARNING']} warning(s). "
            "Review the [WARNING] items below."
        )

    output_lines = [
        "02 — Transformation Validation",
        "=" * 80,
        "",
        "Comparison: data/extracted/ → data/processed/",
        "",
        "Status levels:",
        "- [OK]      matches the expectation",
        "- [NOTE]    differs from the extract by design",
        "- [WARNING] unexpected difference, needs review",
        "",
        "Summary",
        "=" * 80,
        *summary,
        overall,
        "",
    ]

    for report in reports.values():
        output_lines.extend(report.lines)

    OUTPUT_FILE.write_text(
        "\n".join(output_lines),
        encoding="utf-8",
    )

    print("\n".join(summary))
    print(overall)
    print(f"Validation completed: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()