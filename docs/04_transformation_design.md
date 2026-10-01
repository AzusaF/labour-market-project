# Stage 04: Transformation Design

## 1. Purpose

This project examines labour market tightness in Canada by connecting employment, wages, and job vacancy indicators.

Stage 06 turns the raw Statistics Canada tables into clean, consistently structured tables that later stages can build on.

## 2. Target grain

- One table per dataset at **Canada × Industry × Month** (the labour force total table is Canada × Month).
- Analysis period: **January 2021 to December 2025** (60 months).
- Geography: Canada only.
- Industries are kept as published by Statistics Canada. No industries are merged in this stage.

## 3. Source datasets

Four monthly Statistics Canada datasets:

| Dataset                                                            | Table        | Content                                                   | Output table         |
| ------------------------------------------------------------------ | ------------ | --------------------------------------------------------- | -------------------- |
| Labour force characteristics by industry                           | 14100022     | Employment by industry                                    | `employment`         |
| Employee wages by industry                                         | 14100063     | Average and median hourly wages, number of employees      | `wages`              |
| Job vacancies, payroll employees, and job vacancy rate by industry | 14100372     | Labour demand and tightness                               | `vacancies`          |
| Labour force characteristics, all industries                       | Canada total | Labour force, employment, unemployment, unemployment rate | `labour_force_total` |

The three industry-level datasets differ in structure and industry granularity. The labour force total has no industry dimension and serves as a control total.

## 4. Dimension and data alignment

Each dataset is aligned independently to the target grain using:

- **Canada** as the common geography
- **NAICS** as the industry column
- **Month** (`REF_DATE`) as the time dimension
- The measures relevant to that dataset

The datasets stay separate tables. They are not joined in this stage, because their raw industry labels are not directly comparable across tables.

## 5. Transformation requirements

For each dataset, the transformation will:

- Standardize column names and data types.
- Standardize the industry column as `NAICS`.
- Filter to Canada and the analysis period (2021-01 to 2025-12).
- Normalize equivalent NAICS label formats, for example `[55, 56]` to `[55-56]` and `[52, 53]` to `[52-53]`.
- Keep the original industry labels, including the bracketed NAICS codes (for example `Utilities [22]`).
- Keep published aggregate rows (Goods-producing sector, Services-producing sector, Total, all industries). They are not removed here.
- Convert suppressed (`x`) and grade-F values to NULL. Do not impute them.
- Keep Statistics Canada quality flags (A to F) as separate columns where published.
- Select and reshape only the required measures.
- Validate that each table is unique at its grain: (`REF_DATE`, `GEO`, `NAICS`), or (`REF_DATE`, `GEO`) for the labour force total.
- Save the processed tables to `data/processed/`.

## 6. Measures retained

| Dataset            | Measures                                                                             |
| ------------------ | ------------------------------------------------------------------------------------ |
| Employment         | Employment (thousands)                                                               |
| Wages              | Average hourly wage (CAD), median hourly wage (CAD), total employees (thousands)     |
| Vacancies          | Job vacancies, payroll employees, job vacancy rate (%), plus a quality flag for each |
| Labour force total | Labour force, employment, unemployment (thousands), unemployment rate (%)            |

Additional dimensions are kept only when needed to identify or interpret these measures.

## 7. Data quality rules

- Suppressed (`x`) and grade-F values are set to NULL and excluded from numerical analysis. The quality flag stays on the row so the missingness is documented.
- Only Canada-level data in the analysis period is kept.

## 8. Output tables

| Table                | Grain                     |
| -------------------- | ------------------------- |
| `employment`         | Canada × Industry × Month |
| `wages`              | Canada × Industry × Month |
| `vacancies`          | Canada × Industry × Month |
| `labour_force_total` | Canada × Month            |

Each row is one industry (or Canada overall) in one month, with the selected measures as columns. The tables share common dimensions but remain separate. All are saved in `data/processed/`.

## 9. Changes from the original design

| Original design              | Current design                             | Reason                                                                                        |
| ---------------------------- | ------------------------------------------ | --------------------------------------------------------------------------------------------- |
| Exclude `x` and `F` values   | Set to NULL, keep the quality flag         | The flag documents why a value is missing and lets later analysis footnote unreliable points. |
| Three datasets               | Four, adding the Canada labour force total | Used as an independent control total for employment.                                          |
| Filter aggregates implicitly | Aggregate rows retained                    | Needed later for reconciliation against published totals.                                     |
