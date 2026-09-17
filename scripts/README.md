# Scripts

This directory contains Python scripts for inspecting, exploring, extracting, and transforming project data.

The scripts follow a sequential workflow:

### 01 — Metadata Inspection

**Script:** `01_inspect_metadata.py`

Inspects the files in the raw data directory and reports basic file metadata, such as:

- File name
- File size
- File type

---

### 02 — Data Inspection

Examines the structure of the source CSV files, including:

- Column names
- Number of columns
- Sample records
- Potential data-format issues
- Differences between datasets

Large files are inspected without loading the entire file into memory.

---

### 03 — Exploratory Data Analysis

Script: 03_eda.py

Provides an interactive overview of available CSV files. When multiple files are found, the user can select one to analyze:

CSV files found:

[1] 14100022.csv
[2] 14100063.csv
[3] 14100372.csv

Select a file to analyze:

Large files are sampled rather than loaded in full.

The EDA stage does not modify the source data.

## Running the Scripts

Scripts are run from the project root directory.

For example:

**Script:** `python scripts/01_inspect_metadata.py`

As the data pipeline develops, additional scripts will be documented here in numerical order.
