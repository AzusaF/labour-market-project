# Scripts

This directory contains Python scripts for inspecting, preparing, extracting, and transforming project data. The results are saved to `output/` for reference and further analysis.

The scripts follow a sequential workflow:

## 01. Metadata Inspection

**Script:** `01_metadata.py`

Inspects the files in the raw data directory and reports basic file metadata, such as:

- File name
- File size
- File type

---

## 02. Data Inspection

**Script:** `02_inspect.py`

Examines the structure of the source CSV files, including:

- Column names
- Number of columns
- Sample records
- Potential data-format issues
- Differences between datasets

Large files are inspected without loading the entire file into memory.

---

## 03. Prepare Data

**Script:** `03_prepare.py`

Provides an interactive overview of available CSV files and allows the user to select one for analysis.

Large files are sampled rather than loaded in full.

The preparation stage does not modify the source data.

---

## 04. Extract Data

**Script:** `04_extract.py`

Extracts the required data from the raw CSV files and saves the results to the `data/extracted/` directory.

The extraction process:

- Reads the source CSV files in chunks to handle large datasets
- Filters data based on the project requirements
- Processes data from 2021 onward
- Saves extracted datasets for subsequent analysis

---

## 05. Exploratory Data Analysis

The EDA stage evaluates the extracted Statistics Canada datasets before transformation and integration.

The analysis is divided into three sequential steps:

| Step   | Script                      | Purpose                                                                                                                  |
| ------ | --------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **01** | `01_overview.py`            | Examine dataset structure, dimensions, date coverage, basic statistics, missing values, data quality, and duplicate rows |
| **02** | `02_naics_comparison.py`    | Compare NAICS / industry structures across datasets and identify differences that affect cross-dataset integration       |
| **03** | `03_grain_compatibility.py` | Assess the analytical grain, shared dimensions, and join compatibility across datasets                                   |

### Step 01: Dataset Overview

Establishes a baseline understanding of each extracted dataset, including:

- Dataset dimensions and memory usage
- Column and variable profiles
- Dimension and date coverage
- Basic numeric statistics
- Missing values and suppression patterns
- Data-quality indicators
- Duplicate row checks

### Step 02: NAICS Comparison

Examines the industry classification structure across the three datasets to determine whether industry categories can be used directly for integration.

This step identifies:

- Available NAICS levels and categories
- Differences in industry coverage
- Inconsistent industry labels or structures

### Step 03: Grain Compatibility

Evaluates whether the datasets share a compatible analytical grain for integration.

This step examines:

- Dataset-specific dimensions
- Shared dimensions
- Candidate analytical keys
- Geography and time coverage
- Direct join compatibility

### Outcome

The three EDA steps provide the structural findings required to define the target analytical grain, NAICS mapping strategy, geographic scope, analysis period, and data-quality handling for the subsequent transformation stage.

---

# Running the Scripts

Scripts are run from the project root directory.

For example:

**Script:** `python scripts/01_metadata.py`
