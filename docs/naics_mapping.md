# NAICS Mapping Harmonization Rules

## Background

The three source tables use NAICS at different aggregation levels:

| Table    | Metric        | Categories | Granularity                                                                                                                                                    |
| -------- | ------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 14100022 | Employment    | 29         | Mixed: contains both parent and child rows in the same table (e.g. "Finance and insurance [52]" AND "Finance, insurance, real estate... [52,53]" both present) |
| 14100063 | Wages         | 19         | Coarsest: already pre-combined groups, no finer split available                                                                                                |
| 14100372 | Job vacancies | 21         | Finest: close to raw 2-digit NAICS                                                                                                                             |

Only 10 category labels matched exactly as strings across all three (see `05_02_naics_comparison.txt`). Direct joins on the raw NAICS label are not usable beyond that.

## Harmonization strategy

Target the coarsest level that all three tables can reach without double-counting: **wages (14100063)'s level**, since it has no finer split available. Employment and vacancies rows are aggregated up (summed) to match.

**Exception:** Agriculture and "Forestry, fishing, mining, quarrying, oil and gas" cannot both be kept separate, because vacancies' sector-11 row ("Agriculture, forestry, fishing and hunting [11]") bundles agriculture together with forestry/fishing and cannot be split further. These two groups are therefore merged into one combined category:

> **"Agriculture, forestry, fishing, mining, quarrying, oil and gas"**

This is the one place where the harmonized set is coarser than wages' native level.

## Result: 15 harmonized industry categories

1. Accommodation and food services [72]
2. Agriculture, forestry, fishing, mining, quarrying, oil and gas [11, 21]
3. Business, building and other support services [55-56]
4. Construction [23]
5. Educational services [61]
6. Finance, insurance, real estate, rental and leasing [52-53]
7. Health care and social assistance [62]
8. Information, culture and recreation [51, 71]
9. Manufacturing [31-33]
10. Other services (except public administration) [81]
11. Professional, scientific and technical services [54]
12. Public administration [91]
13. Transportation and warehousing [48-49]
14. Utilities [22]
15. Wholesale and retail trade [41, 44-45]

These 15 categories are usable as a common join key (`NAICS_harmonized`) across employment, wages, and vacancies.

## mapping_type values (in naics_mapping.csv)

- **direct**: row maps 1:1 to a harmonized category, no summing needed.
- **component**: row must be summed with one or more sibling rows (same source table) to reach the harmonized category. Group by `source_table, naics_harmonized` and sum.
- **exclude_redundant**: employment (14100022) only. These are pre-combined rows that duplicate what granular component rows already cover (e.g. "Finance, insurance, real estate..." duplicates "Finance and insurance" + "Real estate..."). Dropped to avoid double-counting. Also covers Durables/Non-durables, which duplicate Manufacturing.
- **aggregate_qa**: "Goods-producing sector", "Services-producing sector", and the grand totals. Not part of the 15-category industry partition; keep separately for validating that the 15 categories sum to the expected total.
- **residual_excluded**: "Unclassified industries" (employment only). No equivalent in the other two tables; excluded from cross-table analysis.

## Usage pattern (SQL-style)

```sql
SELECT source_table, ref_date, naics_harmonized, SUM(value) AS value
FROM raw_data
JOIN naics_mapping USING (source_table, naics_original)
WHERE mapping_type IN ('direct', 'component')
GROUP BY source_table, ref_date, naics_harmonized
```

Then join `employment`, `wages`, `vacancies` on `REF_DATE × NAICS_harmonized`.

## Validation to run after applying this mapping

1. Per table, per REF_DATE: sum of the 15 harmonized categories should reconcile with the `TOTAL_QA` row (employment/wages should match within rounding; vacancies too — check the "Total, all industries" row is actually the sum of the 21 raw industries and not a separately-collected series).
2. Row count check: 15 industries × 60 months = 900 rows expected per table after harmonization (down from 1,680 / 1,140 / 1,260 raw rows).
3. Confirm no row was assigned `mapping_type` in more than one bucket (i.e. no accidental double inclusion of an `exclude_redundant` row).
4. Spot-check the merged "Agriculture, forestry, fishing, mining..." category against source totals, since it's the one non-obvious merge.

## Known limitation

Because Agriculture is merged with Forestry/fishing/mining/oil & gas, this pipeline **cannot** isolate pure agriculture (crop/animal production) trends separately from mining/energy trends. If that split becomes analytically important later, it would require sourcing vacancies data at a finer level (e.g. 3-digit NAICS) than what's in 14100372, which is out of scope for now.
