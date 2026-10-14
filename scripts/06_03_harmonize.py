"""
06 — Data Warehouse
03 - HARMONIZE

Builds NAICS-harmonized tables in data/warehouse.duckdb using naics_mapping:
  employment_h, wages_h, vacancies_h, cpi_h, industry_monthly, geo_monthly

Geography:
  - GEO (Canada + 10 provinces) is part of every grouping and join key.
  - Canada is a national total. Nothing is ever summed across GEO.
  - vacancies is Canada only, so provincial rows in industry_monthly have
    NULL vacancy columns by design.

Rules:
  - keep mapping_type in ('direct','component'); drop aggregate_qa /
    exclude_redundant / residual_excluded
  - expected component count per harmonized industry comes from naics_mapping.
    With provinces, suppressed components are common, so a harmonized value
    is computed only when ALL expected components are present (no partial sums)
  - employment: SUM across components
  - wages: employment-weighted mean of average wage; median only when the
    harmonized industry has a single component (medians are not additive)
  - vacancies: SUM vacancies and payroll; rate recomputed as V/(V+P)
  - cpi_h: CPI, year-over-year % change (vs same GEO, 12 months earlier),
    index rebased to BASE_MONTH = 100 per GEO
  - real wages: wage * base_cpi / cpi, in BASE_MONTH dollars of the same GEO.
    Valid for trends within a GEO; CPI levels are not comparable across GEO.

Writes outputs/06_03_harmonize_report.txt. Exit 1 on FAIL.
"""
import sys
from pathlib import Path
import duckdb

DB = "data/warehouse.duckdb"
OUT = Path("outputs/06_03_harmonize_report.txt")
OUT.parent.mkdir(exist_ok=True)

SRC = {"employment": 14100022, "wages": 14100063, "vacancies": 14100372}
STRIP = r"\s*\[[^\]]*\]\s*$"
BASE_MONTH = "2021-01-01"

NATIONAL_GEO = "Canada"
PROVINCES = [
  "Newfoundland and Labrador",
  "Prince Edward Island",
  "Nova Scotia",
  "New Brunswick",
  "Quebec",
  "Ontario",
  "Manitoba",
  "Saskatchewan",
  "Alberta",
  "British Columbia",
]
ALL_GEOS = [NATIONAL_GEO] + PROVINCES

con = duckdb.connect(DB)
lines, results = [], []


def log(s=""):
  print(s)
  lines.append(s)


def check(name, ok, detail=""):
  results.append(ok)
  log(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


def q(sql):
  return con.execute(sql).fetchall()


def mapped(t):
  """Source rows joined to the mapping (direct/component only) with expected component count."""
  return f"""
    SELECT d.*, m.naics_harmonized, m.mapping_type, x.expected_components
    FROM {t} d
    JOIN naics_mapping m
      ON m.source_table = {SRC[t]}
     AND trim(m.naics_original) = trim(regexp_replace(d.NAICS, '{STRIP}', ''))
    JOIN naics_expected x
      ON x.source_table = m.source_table
     AND x.naics_harmonized = m.naics_harmonized
    WHERE m.mapping_type IN ('direct', 'component')
  """


log("=" * 80)
log("HARMONIZE")
log("=" * 80)

# ---- expected number of components per harmonized industry ----
con.execute("""
  CREATE OR REPLACE TABLE naics_expected AS
  SELECT source_table, naics_harmonized, COUNT(*) AS expected_components
  FROM naics_mapping
  WHERE mapping_type IN ('direct', 'component')
  GROUP BY 1, 2
""")

# ---- employment ----
con.execute(f"""
  CREATE OR REPLACE TABLE employment_h AS
  SELECT REF_DATE, GEO, naics_harmonized,
         CASE WHEN COUNT(*) = MAX(expected_components)
               AND COUNT(Employment_thousands) = COUNT(*)
              THEN SUM(Employment_thousands) END AS employment_thousands,
         COUNT(*)                   AS n_components,
         MAX(expected_components)   AS expected_components
  FROM ({mapped('employment')})
  GROUP BY 1, 2, 3
""")

# ---- wages ----
con.execute(f"""
  CREATE OR REPLACE TABLE wages_h AS
  SELECT REF_DATE, GEO, naics_harmonized,
         CASE WHEN COUNT(*) = MAX(expected_components)
               AND COUNT(Total_employees_thousands) = COUNT(*)
              THEN SUM(Total_employees_thousands) END AS employees_thousands,
         CASE WHEN COUNT(*) = MAX(expected_components)
               AND COUNT(Total_employees_thousands) = COUNT(*)
               AND COUNT(Average_hourly_wage_cad) = COUNT(*)
              THEN SUM(Average_hourly_wage_cad * Total_employees_thousands)
                   / NULLIF(SUM(Total_employees_thousands), 0) END AS avg_hourly_wage_cad,
         CASE WHEN MAX(expected_components) = 1 AND COUNT(*) = 1
              THEN MAX(Median_hourly_wage_cad) END AS median_hourly_wage_cad,
         COUNT(*)                   AS n_components,
         MAX(expected_components)   AS expected_components
  FROM ({mapped('wages')})
  GROUP BY 1, 2, 3
""")

# ---- vacancies (Canada only) ----
con.execute(f"""
  CREATE OR REPLACE TABLE vacancies_h AS
  WITH agg AS (
    SELECT REF_DATE, GEO, naics_harmonized,
           COUNT(*)                   AS n_components,
           MAX(expected_components)   AS expected_components,
           COUNT(Job_vacancies)       AS n_vac_values,
           COUNT(Payroll_employees)   AS n_pay_values,
           SUM(Job_vacancies)         AS sum_vac,
           SUM(Payroll_employees)     AS sum_pay,
           MAX(Job_vacancies_quality) AS worst_vacancy_quality  -- A best ... F worst
    FROM ({mapped('vacancies')})
    GROUP BY 1, 2, 3
  )
  SELECT REF_DATE, GEO, naics_harmonized,
         CASE WHEN n_components = expected_components AND n_vac_values = n_components
              THEN sum_vac END AS job_vacancies,
         CASE WHEN n_components = expected_components AND n_pay_values = n_components
              THEN sum_pay END AS payroll_employees,
         CASE WHEN n_components = expected_components
               AND n_vac_values = n_components AND n_pay_values = n_components
              THEN 100.0 * sum_vac / (sum_vac + sum_pay) END AS job_vacancy_rate_pct,
         n_components,
         expected_components,
         n_components - n_vac_values AS n_null_components,
         worst_vacancy_quality
  FROM agg
""")

# ---- CPI: yoy change and rebased index, per GEO ----
con.execute(f"""
  CREATE OR REPLACE TABLE cpi_h AS
  SELECT c.REF_DATE, c.GEO,
         c.CPI AS cpi,
         b.base_cpi,
         100.0 * c.CPI / b.base_cpi AS cpi_rebased,
         100.0 * (c.CPI / p.CPI - 1) AS cpi_yoy_pct
  FROM cpi c
  LEFT JOIN (SELECT GEO, CPI AS base_cpi FROM cpi WHERE REF_DATE = DATE '{BASE_MONTH}') b
    ON b.GEO = c.GEO
  LEFT JOIN cpi p
    ON p.GEO = c.GEO AND p.REF_DATE = c.REF_DATE - INTERVAL 12 MONTH
""")

# ---- industry x GEO x month, with CPI and real wages ----
con.execute("""
  CREATE OR REPLACE TABLE industry_monthly AS
  SELECT REF_DATE, GEO, naics_harmonized,
         e.employment_thousands,
         w.employees_thousands, w.avg_hourly_wage_cad, w.median_hourly_wage_cad,
         w.avg_hourly_wage_cad    * c.base_cpi / c.cpi AS real_avg_hourly_wage_cad,
         w.median_hourly_wage_cad * c.base_cpi / c.cpi AS real_median_hourly_wage_cad,
         c.cpi, c.cpi_yoy_pct,
         v.job_vacancies, v.payroll_employees, v.job_vacancy_rate_pct,
         v.worst_vacancy_quality,
         e.n_components AS emp_components,
         w.n_components AS wage_components,
         v.n_components AS vac_components
  FROM employment_h e
  FULL JOIN wages_h w     USING (REF_DATE, GEO, naics_harmonized)
  FULL JOIN vacancies_h v USING (REF_DATE, GEO, naics_harmonized)
  LEFT JOIN cpi_h c       USING (REF_DATE, GEO)
""")

# ---- GEO x month, all industries: labour force + CPI (Beveridge-style analysis) ----
con.execute("""
  CREATE OR REPLACE TABLE geo_monthly AS
  SELECT l.*, c.cpi, c.cpi_rebased, c.cpi_yoy_pct
  FROM labour_force_total l
  LEFT JOIN cpi_h c USING (REF_DATE, GEO)
""")

# ---- row counts ----
log("\n-- Output tables --")
for t in ["employment_h", "wages_h", "vacancies_h", "industry_monthly"]:
  n, k, g = q(f"SELECT COUNT(*), COUNT(DISTINCT naics_harmonized), COUNT(DISTINCT GEO) FROM {t}")[0]
  log(f"   {t}: {n} rows, {k} harmonized industries, {g} GEO")
  check(f"{t}: not empty", n > 0)
for t in ["cpi_h", "geo_monthly"]:
  n, g = q(f"SELECT COUNT(*), COUNT(DISTINCT GEO) FROM {t}")[0]
  log(f"   {t}: {n} rows, {g} GEO")
  check(f"{t}: not empty", n > 0)

n_src = q("SELECT COUNT(*) FROM cpi")[0][0]
n_h = q("SELECT COUNT(*) FROM cpi_h")[0][0]
check("cpi_h: same row count as cpi (joins did not multiply rows)", n_src == n_h, f"{n_src} vs {n_h}")
n_src = q("SELECT COUNT(*) FROM labour_force_total")[0][0]
n_h = q("SELECT COUNT(*) FROM geo_monthly")[0][0]
check("geo_monthly: same row count as labour_force_total", n_src == n_h, f"{n_src} vs {n_h}")

# ---- GEO coverage ----
log("\n-- GEO coverage --")
for t, expected in [("employment_h", ALL_GEOS), ("wages_h", ALL_GEOS),
                    ("vacancies_h", [NATIONAL_GEO]), ("cpi_h", ALL_GEOS),
                    ("geo_monthly", ALL_GEOS)]:
  geos = {g[0] for g in q(f"SELECT DISTINCT GEO FROM {t}")}
  check(f"{t}: GEO set == expected ({len(expected)})", geos == set(expected),
        f"missing {sorted(set(expected) - geos)}, extra {sorted(geos - set(expected))}"
        if geos != set(expected) else "")

n = q(f"SELECT COUNT(*) FROM industry_monthly WHERE vac_components IS NOT NULL AND GEO <> '{NATIONAL_GEO}'")[0][0]
check("industry_monthly: vacancy columns populated for Canada rows only", n == 0, f"{n} rows" if n else "")

# ---- components: never more than expected; incomplete months are NULL, not partial ----
log("\n-- Component completeness --")
for t, col in [("employment_h", "employment_thousands"),
               ("wages_h", "avg_hourly_wage_cad"),
               ("vacancies_h", "job_vacancies")]:
  over = q(f"SELECT COUNT(*) FROM {t} WHERE n_components > expected_components")[0][0]
  check(f"{t}: n_components <= expected_components", over == 0, f"{over} rows" if over else "")

  partial = q(f"""
    SELECT COUNT(*) FROM {t}
    WHERE n_components < expected_components AND {col} IS NOT NULL
  """)[0][0]
  check(f"{t}: incomplete components never produce a value (no partial sums)", partial == 0,
        f"{partial} rows" if partial else "")

  inc = q(f"""
    SELECT GEO, COUNT(*) FILTER (WHERE {col} IS NULL), COUNT(*)
    FROM {t} GROUP BY 1 ORDER BY 2 DESC
  """)
  log(f"   {t}.{col} NULL (incomplete or suppressed) by GEO:")
  for geo, nulls, total in inc:
    log(f"     {geo}: {nulls}/{total}")

# ---- one row per period per industry per GEO ----
log("\n-- Grain --")
for t in ["employment_h", "wages_h", "vacancies_h", "industry_monthly"]:
  n = q(f"""SELECT COUNT(*) FROM (SELECT REF_DATE, GEO, naics_harmonized FROM {t}
            GROUP BY 1,2,3 HAVING COUNT(*) > 1)""")[0][0]
  check(f"{t}: unique on (REF_DATE, GEO, naics_harmonized)", n == 0, f"{n} dups" if n else "")
for t in ["cpi_h", "geo_monthly"]:
  n = q(f"""SELECT COUNT(*) FROM (SELECT REF_DATE, GEO FROM {t}
            GROUP BY 1,2 HAVING COUNT(*) > 1)""")[0][0]
  check(f"{t}: unique on (REF_DATE, GEO)", n == 0, f"{n} dups" if n else "")

# ---- CPI checks ----
log("\n-- CPI --")
bad = q(f"""
  SELECT GEO FROM cpi_h WHERE REF_DATE = DATE '{BASE_MONTH}'
  AND (cpi_rebased IS NULL OR ABS(cpi_rebased - 100) > 1e-9)
""")
check(f"cpi_h: rebased index == 100 at {BASE_MONTH[:7]} for every GEO",
      not bad and q("SELECT COUNT(DISTINCT GEO) FROM cpi_h WHERE base_cpi IS NOT NULL")[0][0]
      == q("SELECT COUNT(DISTINCT GEO) FROM cpi_h")[0][0],
      str(bad) if bad else "")

n = q("SELECT COUNT(*) FROM cpi_h WHERE cpi_yoy_pct IS NULL AND REF_DATE >= DATE '2022-01-01'")[0][0]
check("cpi_h: yoy % available from 2022-01 onward in every GEO", n == 0, f"{n} NULL" if n else "")

lo, hi = q("SELECT MIN(cpi_yoy_pct), MAX(cpi_yoy_pct) FROM cpi_h")[0]
log(f"   yoy % range: {lo:.2f} to {hi:.2f}")
check("cpi_h: yoy % within plausible range (-5 to 15)", -5 <= lo and hi <= 15)

n = q("SELECT COUNT(*) FROM industry_monthly WHERE cpi IS NULL")[0][0]
check("industry_monthly: every row has CPI for its GEO and month", n == 0, f"{n} rows without CPI" if n else "")

n = q("""
  SELECT COUNT(*) FROM industry_monthly
  WHERE avg_hourly_wage_cad IS NOT NULL AND real_avg_hourly_wage_cad IS NULL
""")[0][0]
check("industry_monthly: real wage computed wherever nominal wage exists", n == 0, f"{n} rows" if n else "")

# ---- cross-table industry overlap (informational) ----
log("\n-- Harmonized industry overlap across tables --")
rows = q("""
  SELECT naics_harmonized,
         bool_or(src='employment') AS in_emp,
         bool_or(src='wages')      AS in_wages,
         bool_or(src='vacancies')  AS in_vac
  FROM (
    SELECT naics_harmonized, 'employment' src FROM employment_h
    UNION ALL SELECT naics_harmonized, 'wages' FROM wages_h
    UNION ALL SELECT naics_harmonized, 'vacancies' FROM vacancies_h
  ) GROUP BY 1 ORDER BY 1
""")
full = [r[0] for r in rows if r[1] and r[2] and r[3]]
partial = [(r[0], "emp" if r[1] else "-", "wage" if r[2] else "-", "vac" if r[3] else "-")
           for r in rows if not (r[1] and r[2] and r[3])]
log(f"   in all 3 tables: {len(full)}")
for f in full:
  log(f"     {f}")
log(f"   in only some tables: {len(partial)}")
for p in partial:
  log(f"     {p}")
check("at least one industry present in all 3 tables", len(full) > 0)

# ---- reconciliation vs labour force total, per GEO (informational) ----
log("\n-- Harmonized employment vs labour_force_total.Employment_thousands (per GEO) --")
log("   only (GEO, month) where every harmonized industry is present and complete")
rows = q("""
  WITH n AS (SELECT COUNT(DISTINCT naics_harmonized) AS k FROM employment_h),
  r AS (
    SELECT e.GEO, e.REF_DATE,
           SUM(e.employment_thousands) / MAX(l.Employment_thousands) AS ratio
    FROM employment_h e
    JOIN labour_force_total l USING (REF_DATE, GEO)
    GROUP BY e.GEO, e.REF_DATE
    HAVING COUNT(*) = (SELECT k FROM n) AND COUNT(e.employment_thousands) = COUNT(*)
  )
  SELECT GEO, COUNT(*), MIN(ratio), MAX(ratio) FROM r GROUP BY 1 ORDER BY 1
""")
if not rows:
  log("   no complete (GEO, month) found")
for geo, n_m, lo, hi in rows:
  log(f"   {geo}: {n_m} months, ratio min {lo:.3f}, max {hi:.3f}")
log("   (should be close to 1; if not, check for aggregate rows kept as direct)")

# ---- quality flag carried through (Canada rows with vacancy data) ----
log("\n-- worst_vacancy_quality in industry_monthly (rows with vacancy data) --")
for qv, c in q("""
  SELECT worst_vacancy_quality, COUNT(*) FROM industry_monthly
  WHERE vac_components IS NOT NULL GROUP BY 1 ORDER BY 1
"""):
  log(f"   {qv}: {c}")
n = q("SELECT COUNT(*) FROM industry_monthly WHERE vac_components IS NOT NULL AND worst_vacancy_quality IS NULL")[0][0]
check("worst_vacancy_quality populated wherever vacancy data exists", n == 0, f"{n} NULL" if n else "")

# ---- vacancy NULL propagation ----
n = q("SELECT COUNT(*) FROM vacancies_h WHERE job_vacancies IS NULL")[0][0]
log(f"\n-- vacancies_h rows with NULL vacancies (suppressed or incomplete component): {n}")

log("\n" + "=" * 80)
log("HARMONIZE RESULT")
log("=" * 80)
fails = results.count(False)
log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails}")
log("Status: " + ("PASSED" if fails == 0 else "FAILED"))

OUT.write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if fails == 0 else 1)