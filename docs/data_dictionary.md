# Data Dictionary

## Overview

- **Target period**: 2021-01 to 2025-12
- **Geography**: Canada (national level)
- **Analysis focus**: Employment, wages, job vacancies and labour tightness
- **Source tables**: 14100022, 14100063, 14100372

---

## Processed Tables

### employment

- **Grain**: REF_DATE × NAICS (Canada, Total gender, 15+ years)
- **Rows**: 1,680 (28 industries × 60 months)
- **Source**: 14100022, Labour force characteristics = Employment

| Column               | Unit             | Definition                 | Note                                                |
| -------------------- | ---------------- | -------------------------- | --------------------------------------------------- |
| REF_DATE             | YYYY-MM          | Month reference            |                                                     |
| GEO                  | text             | Geography                  | Fixed to Canada                                     |
| NAICS                | text             | Industry label             | Normalized                                          |
| Employment_thousands | thousand persons | Number of employed persons | LFS; seasonally unadjusted; Total gender; 15+ years |

---

### wages

- **Grain**: REF_DATE × NAICS (Canada, both full- and part-time employees)
- **Rows**: 1,140 (19 industries × 60 months)
- **Source**: 14100063

| Column                    | Unit             | Definition          | Note                                    |
| ------------------------- | ---------------- | ------------------- | --------------------------------------- |
| REF_DATE                  | YYYY-MM          | Month reference     |                                         |
| GEO                       | text             | Geography           | Fixed to Canada                         |
| NAICS                     | text             | Industry label      |                                         |
| Average_hourly_wage_cad   | CAD              | Average hourly wage | Nominal (current dollars); both FT & PT |
| Median_hourly_wage_cad    | CAD              | Median hourly wage  | Nominal; primary wage metric            |
| Total_employees_thousands | thousand persons | Total employees     | For weighting/context                   |

---

### vacancies

- **Grain**: REF_DATE × NAICS (Canada)
- **Rows**: 1,260 (21 industries × 60 months)
- **Source**: 14100372

| Column               | Unit    | Definition                                  | Quality Flag              | Note                                      |
| -------------------- | ------- | ------------------------------------------- | ------------------------- | ----------------------------------------- |
| REF_DATE             | YYYY-MM | Month reference                             | —                         |                                           |
| GEO                  | text    | Geography                                   | —                         | Fixed to Canada                           |
| NAICS                | text    | Industry label                              | —                         |                                           |
| Job_vacancies        | persons | Number of job vacancies                     | Job_vacancies_quality     | **Unit differs from employment by 1000x** |
| Payroll_employees    | persons | Payroll employees                           | Payroll_employees_quality |                                           |
| Job_vacancy_rate_pct | percent | Job vacancies / (vacancies + payroll) × 100 | Job_vacancy_rate_quality  |                                           |
| \*\_quality          | A–F     | Quality flags                               | —                         | F = NULL value; A–E retained              |

---

### labour_force_total

- **Grain**: REF_DATE (Canada, all industries)
- **Rows**: 60 months
- **Source**: 14100022

| Column                 | Unit             | Definition         | Note                                               |
| ---------------------- | ---------------- | ------------------ | -------------------------------------------------- |
| REF_DATE               | YYYY-MM          | Month reference    |                                                    |
| GEO                    | text             | Geography          | Canada                                             |
| Labour_force_thousands | thousand persons | Total labour force | All industries                                     |
| Employment_thousands   | thousand persons | Total employment   | All industries (validate against employment total) |
| Unemployment_thousands | thousand persons | Total unemployment |                                                    |
| Unemployment_rate_pct  | percent          | Unemployment rate  | Canada × all industries                            |

---

## Important Notes

### 1. Unit differences

- **Employment, wages, total employees**: thousand persons
- **Job vacancies, payroll employees**: persons
- **Conversion factor**: 1,000×

**Action**: Always confirm units when joining tables.

### 2. Source program differences

| Metric                   | Program      | Definition                  |
| ------------------------ | ------------ | --------------------------- |
| Employment, unemployment | LFS          | Labour Force Survey         |
| Job vacancies            | JVWS         | Job Vacancy and Wage Survey |
| Wages, employee counts   | SEPH-related | Different survey base       |

**Implication**: Do NOT compare levels directly across source programs.
**Instead**: Compare growth rates, rankings, ratios, and co-movement.

### 3. Wages are nominal

- All wage figures are in current dollars (not inflation-adjusted).
- Real wage analysis requires CPI deflation (not in scope).

### 4. Industry classification mismatches

- Source tables use different NAICS aggregation levels.
- Use `naics_mapping.csv` and `NAICS_harmonized` codes to join.
- See `naics_mapping.md` for mapping rules.

### 5. Quality flags in vacancies

- Quality flag = F → value is NULL
- Quality flags A–E are retained
- Default analysis includes A–E only
- Sensitivity analyses available with A–C only

### 6. Seasonality

- No seasonal adjustment applied.
- Month-over-month comparisons may reflect seasonal patterns.
- Use YoY or moving averages for trend analysis.

---

## Data Quality Checks Performed

✓ No duplicate rows  
✓ All expected date range covered  
✓ No unexpected nulls (except F flags)  
✓ Internal consistency: Labour force = employment + unemployment  
✓ Unemployment rate formula verified  
✓ Values reconciled with source extracts

See `02_data_quality.sql` for validation queries.
