# Scripts

This directory contains Python scripts for inspecting, preparing, extracting, and transforming project data.

The scripts follow a sequential workflow:

### 01 — Metadata Inspection

**Script:** `01_metadata.py`

Inspects the files in the raw data directory and reports basic file metadata, such as:

- File name
- File size
- File type

---

### 02 — Data Inspection

**Script:** `02_inspect.py`

Examines the structure of the source CSV files, including:

- Column names
- Number of columns
- Sample records
- Potential data-format issues
- Differences between datasets

Large files are inspected without loading the entire file into memory.

---

### 03 — Prepare Data

**Script:** `03_prepare.py`

Provides an interactive overview of available CSV files and allows the user to select one for analysis.

Large files are sampled rather than loaded in full.

The preparation stage does not modify the source data.

---

### 04 — Extract Data

**Script:** `04_extract.py`

Extracts the required data from the raw CSV files and saves the results to the `data/extracted/` directory.

The extraction process:

- Reads the source CSV files in chunks to handle large datasets
- Filters data based on the project requirements
- Processes data from 2021 onward
- Saves extracted datasets for subsequent analysis

---

## Running the Scripts

Scripts are run from the project root directory.

For example:

**Script:** `python scripts/01_metadata.py`

As the data pipeline develops, additional scripts will be documented here in numerical order.
