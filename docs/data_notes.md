# Data Notes

## Sources (Statistics Canada, Canada-level, monthly, Jan 2021 to Dec 2025)

| Table          | Content                                         | Role                 |
| -------------- | ----------------------------------------------- | -------------------- |
| 14100022       | Employment by industry                          | `employment`         |
| 14100063       | Wages and employees by industry                 | `wages`              |
| 14100372       | Job vacancies and payroll employees by industry | `vacancies`          |
| (labour force) | Labour force, employment, unemployment, rate    | `labour_force_total` |

## NAICS harmonization (`naics_mapping`)

Industry names in each source table are mapped to a common `naics_harmonized` list (15 industries).

| mapping_type      | Treatment                                                   |
| ----------------- | ----------------------------------------------------------- |
| direct, component | Used. Components are summed into their harmonized industry. |
| aggregate_qa      | Not used in analysis. Kept for reconciliation only.         |
| exclude_redundant | Dropped. Parent categories that would double count.         |
| residual_excluded | Dropped (Unclassified industries).                          |

Source-row lineage (used / total): employment 1,200 / 1,680; wages 960 / 1,140; vacancies 1,200 / 1,260.

## Aggregation rules

- Employment: sum of components.
- Average wage: employment-weighted mean across components.
- Median wage: only for single-component industries (medians are not additive); NULL otherwise.
- Vacancies and payroll employees: sums; vacancy rate recomputed as V / (V + payroll).

## Missing data

- 8 of 1,260 vacancy observations (0.6%) were suppressed by Statistics Canada (quality grade F): Utilities (6), Mining/oil and gas (1), Finance and insurance (1).
- They are left NULL, not imputed, and excluded from vacancy-rate analysis. Any harmonized industry-month containing one is also NULL (no partial sums).
- `industry_monthly.worst_vacancy_quality` carries the worst A-F flag among an industry-month's components.

## Validation results

- 06_02: 50 checks passed (counts, keys, ranges, consistency, NAICS coverage).
- 06_03: 12 checks passed; harmonized employment equals total employment (ratio 1.000).
- 06_04: 11 checks passed; harmonized sums match StatCan's Goods-producing, Services-producing, and Total aggregates within 0.3k.
