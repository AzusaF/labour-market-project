"""
06 — Data Warehouse
02 - VALIDATION

Reads data/warehouse.duckdb, runs integrity checks, writes
outputs/06_02_validation_report.txt. Exit code 1 if any FAIL.

Geography design:
  - GEO is part of the grain: GEO x NAICS x REF_DATE (GEO x REF_DATE for
    labour_force_total and cpi).
  - "Canada" is a national total, not a sibling of the provinces.
    Rows are never summed across GEO.
  - vacancies is published for Canada only.
"""

import sys
from pathlib import Path
import duckdb

DB = "data/warehouse.duckdb"
PROCESSED_DIR = Path("data/processed")
CONFIG_DIR = Path("config")
OUT = Path("outputs/06_02_validation_report.txt")
OUT.parent.mkdir(exist_ok=True)

START_MONTH = "2021-01"
END_MONTH = "2025-12"
N_MONTHS = 60

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

# table -> source CSV (row count must match what 06_01 loaded)
SOURCES = {
  "employment": PROCESSED_DIR / "employment.csv",
  "wages": PROCESSED_DIR / "wages.csv",
  "vacancies": PROCESSED_DIR / "vacancies.csv",
  "labour_force_total": PROCESSED_DIR / "labour_force_total.csv",
  "cpi": PROCESSED_DIR / "cpi.csv",
  "naics_mapping": CONFIG_DIR / "naics_mapping.csv",
  "province_mapping": CONFIG_DIR / "province_mapping.csv",
}

# expected GEO values per table
TABLE_GEOS = {
  "employment": ALL_GEOS,
  "wages": ALL_GEOS,
  "vacancies": [NATIONAL_GEO],
  "labour_force_total": ALL_GEOS,
  "cpi": ALL_GEOS,
}

# key columns per table (GEO is always part of the key)
keys = {
  "employment": ["REF_DATE", "GEO", "NAICS"],
  "wages": ["REF_DATE", "GEO", "NAICS"],
  "vacancies": ["REF_DATE", "GEO", "NAICS"],
  "labour_force_total": ["REF_DATE", "GEO"],
  "cpi": ["REF_DATE", "GEO"],
}

con = duckdb.connect(DB, read_only=True)
lines, results = [], []


def log(s=""):
  print(s)
  lines.append(s)


def check(name, ok, detail=""):
  status = "PASS" if ok else "FAIL"
  results.append(ok)
  log(f"[{status}] {name}" + (f"  -> {detail}" if detail else ""))


def q(sql):
  return con.execute(sql).fetchall()


def scalar(sql):
  return q(sql)[0][0]


log("=" * 80)
log("VALIDATION")
log("=" * 80)

# ---- row counts vs source CSV ----
log("\n-- Row counts (DuckDB vs source CSV) --")
for t, path in SOURCES.items():
  expected = scalar(f"SELECT COUNT(*) FROM read_csv_auto('{path.as_posix()}', header = true)")
  actual = scalar(f"SELECT COUNT(*) FROM {t}")
  check(f"{t}: row count == source CSV ({expected})", actual == expected, f"{actual} in DuckDB")

# ---- null checks on keys ----
log("\n-- Key NULLs --")
for t, ks in keys.items():
  for k in ks:
    n = scalar(f'SELECT COUNT(*) FROM {t} WHERE "{k}" IS NULL')
    check(f"{t}.{k}: no NULLs", n == 0, f"{n} nulls" if n else "")

# ---- duplicate keys ----
log("\n-- Key uniqueness --")
for t, ks in keys.items():
  cols = ", ".join(f'"{k}"' for k in ks)
  n = scalar(f"SELECT COUNT(*) FROM (SELECT {cols} FROM {t} GROUP BY {cols} HAVING COUNT(*)>1)")
  check(f"{t}: unique on ({', '.join(ks)})", n == 0, f"{n} duplicate keys" if n else "")

# ---- null rates on measures (informational + fail if 100% null) ----
measures = {
  "employment": ["Employment_thousands"],
  "wages": ["Average_hourly_wage_cad", "Median_hourly_wage_cad", "Total_employees_thousands"],
  "vacancies": ["Job_vacancies", "Payroll_employees", "Job_vacancy_rate_pct"],
  "labour_force_total": ["Labour_force_thousands", "Employment_thousands",
                         "Unemployment_thousands", "Unemployment_rate_pct"],
  "cpi": ["CPI"],
}
log("\n-- Measure null rates --")
for t, ms in measures.items():
  total = scalar(f"SELECT COUNT(*) FROM {t}")
  for m in ms:
    n = scalar(f'SELECT COUNT(*) FROM {t} WHERE "{m}" IS NULL')
    log(f"   {t}.{m}: {n}/{total} NULL ({n/total:.1%})")
    check(f"{t}.{m}: not entirely NULL", n < total)

# ---- value ranges ----
log("\n-- Value ranges --")
ranges = [
  ("employment", "Employment_thousands", ">= 0"),
  ("wages", "Average_hourly_wage_cad", "BETWEEN 5 AND 200"),
  ("wages", "Median_hourly_wage_cad", "BETWEEN 5 AND 200"),
  ("wages", "Total_employees_thousands", ">= 0"),
  ("vacancies", "Job_vacancies", ">= 0"),
  ("vacancies", "Payroll_employees", ">= 0"),
  ("vacancies", "Job_vacancy_rate_pct", "BETWEEN 0 AND 30"),
  ("labour_force_total", "Unemployment_rate_pct", "BETWEEN 0 AND 30"),
  ("cpi", "CPI", "BETWEEN 50 AND 300"),  # index, 2002=100
]
for t, c, cond in ranges:
  bad = scalar(f'SELECT COUNT(*) FROM {t} WHERE "{c}" IS NOT NULL AND NOT ("{c}" {cond})')
  check(f"{t}.{c} {cond}", bad == 0, f"{bad} out-of-range" if bad else "")

# ---- date coverage ----
log("\n-- Date coverage --")
for t in keys:
  mn, mx, nd = q(f"SELECT MIN(REF_DATE), MAX(REF_DATE), COUNT(DISTINCT REF_DATE) FROM {t}")[0]
  log(f"   {t}: {mn} -> {mx}, {nd} distinct periods")
  check(f"{t}: covers {START_MONTH} to {END_MONTH} ({N_MONTHS} months)",
        str(mn)[:7] == START_MONTH and str(mx)[:7] == END_MONTH and nd == N_MONTHS,
        f"{mn} -> {mx}, {nd} periods")

# monthly series must be gap-free within each GEO (complete grid for these two)
for t in ["labour_force_total", "cpi"]:
  gaps = scalar(f"""
    SELECT COUNT(*) FROM (
      SELECT GEO, REF_DATE,
             LAG(REF_DATE) OVER (PARTITION BY GEO ORDER BY REF_DATE) prev
      FROM (SELECT DISTINCT GEO, REF_DATE FROM {t})
    ) WHERE prev IS NOT NULL AND date_diff('month', prev, REF_DATE) <> 1
  """)
  check(f"{t}: monthly series has no gaps within any GEO", gaps == 0, f"{gaps} gaps" if gaps else "")

  short = q(f"""
    SELECT GEO, COUNT(DISTINCT REF_DATE) FROM {t}
    GROUP BY 1 HAVING COUNT(DISTINCT REF_DATE) <> {N_MONTHS}
  """)
  check(f"{t}: every GEO has {N_MONTHS} months", not short, str(short) if short else "")

# industry tables: gaps are expected (suppression) -> informational
log("\n   industry series shorter than the full period (informational):")
for t in ["employment", "wages", "vacancies"]:
  n, tot = q(f"""
    SELECT COUNT(*) FILTER (WHERE m < {N_MONTHS}), COUNT(*) FROM (
      SELECT GEO, NAICS, COUNT(DISTINCT REF_DATE) m FROM {t} GROUP BY 1, 2)
  """)[0]
  log(f"     {t}: {n}/{tot} (GEO, NAICS) series have fewer than {N_MONTHS} months")

# ---- GEO ----
log("\n-- GEO values --")
for t, expected_geos in TABLE_GEOS.items():
  geos = {g[0] for g in q(f"SELECT DISTINCT GEO FROM {t}")}
  missing = sorted(set(expected_geos) - geos)
  extra = sorted(geos - set(expected_geos))
  detail = ""
  if missing:
    detail += f"missing: {missing} "
  if extra:
    detail += f"unexpected: {extra}"
  check(f"{t}: GEO set == expected ({len(expected_geos)})", not missing and not extra, detail.strip())

  per_geo = q(f"SELECT GEO, COUNT(*) FROM {t} GROUP BY 1 ORDER BY 2 DESC")
  log(f"   {t} rows per GEO: " + ", ".join(f"{g}={c}" for g, c in per_geo))

# province_mapping: some column must list all 10 provinces (column names unknown, so detect)
cols = [r[0] for r in q("DESCRIBE province_mapping")]
covering = []
has_canada = False
for c in cols:
  vals = {str(r[0]).strip() for r in q(f'SELECT DISTINCT "{c}" FROM province_mapping WHERE "{c}" IS NOT NULL')}
  if set(PROVINCES) <= vals:
    covering.append(c)
    has_canada = has_canada or NATIONAL_GEO in vals
check("province_mapping: a column lists all 10 provinces", len(covering) > 0,
      f"columns: {cols}" if not covering else "")
log(f"   province_mapping columns: {cols}; province column(s): {covering}; Canada listed: {has_canada}")

# ---- cross-field consistency ----
log("\n-- Consistency --")
n = scalar("""
  SELECT COUNT(*) FROM labour_force_total
  WHERE ABS(Labour_force_thousands - (Employment_thousands + Unemployment_thousands)) > 1.0
""")
check("labour_force_total: LF = Employment + Unemployment (tol 1k, every GEO)", n == 0, f"{n} rows off" if n else "")

n = scalar("""
  SELECT COUNT(*) FROM labour_force_total
  WHERE ABS(Unemployment_rate_pct - 100.0*Unemployment_thousands/Labour_force_thousands) > 0.15
""")
check("labour_force_total: unemployment rate recomputes (tol 0.15pp, every GEO)", n == 0, f"{n} rows off" if n else "")

n = scalar("""
  SELECT COUNT(*) FROM vacancies
  WHERE Job_vacancies IS NOT NULL AND Payroll_employees IS NOT NULL AND Job_vacancy_rate_pct IS NOT NULL
    AND ABS(Job_vacancy_rate_pct - 100.0*Job_vacancies/(Job_vacancies+Payroll_employees)) > 0.2
""")
check("vacancies: rate = V/(V+Payroll) (tol 0.2pp)", n == 0, f"{n} rows off" if n else "")

n = scalar("""
  SELECT COUNT(*) FROM wages
  WHERE Average_hourly_wage_cad IS NOT NULL AND Median_hourly_wage_cad IS NOT NULL
    AND Median_hourly_wage_cad > 2*Average_hourly_wage_cad
""")
check("wages: median not > 2x average", n == 0, f"{n} rows" if n else "")

STRIP = r"\s*\[[^\]]*\]\s*$"   # drops trailing " [21, 113-114, ...]"

# employment Total row per GEO must equal labour_force_total employment (same source table)
n = scalar(f"""
  SELECT COUNT(*) FROM labour_force_total l
  FULL JOIN (
    SELECT REF_DATE, GEO, Employment_thousands AS emp_tbl FROM employment
    WHERE trim(regexp_replace(NAICS, '{STRIP}', '')) = 'Total, all industries'
  ) e USING (REF_DATE, GEO)
  WHERE l.Employment_thousands IS NULL OR e.emp_tbl IS NULL
     OR ABS(l.Employment_thousands - e.emp_tbl) > 1e-6
""")
check("employment Total row == labour_force_total.Employment_thousands (per GEO, month)",
      n == 0, f"{n} rows differ or unmatched" if n else "")

# provinces vs Canada: informational only (rounding, suppression). Never derive Canada from provinces.
gap = q(f"""
  SELECT MAX(ABS(c.Employment_thousands - p.s)) FROM
    (SELECT REF_DATE, Employment_thousands FROM labour_force_total WHERE GEO = '{NATIONAL_GEO}') c
    JOIN (SELECT REF_DATE, SUM(Employment_thousands) s FROM labour_force_total
          WHERE GEO <> '{NATIONAL_GEO}' GROUP BY 1) p USING (REF_DATE)
""")[0][0]
log(f"   INFO: max |Canada - sum of provinces| (employment, thousands): {gap}")

# ---- NAICS mapping coverage ----
log("\n-- NAICS mapping coverage --")
SRC = {"employment": 14100022, "wages": 14100063, "vacancies": 14100372}

for t, src in SRC.items():
  missing = q(f"""
    SELECT DISTINCT trim(regexp_replace(NAICS, '{STRIP}', '')) AS name
    FROM {t}
    WHERE trim(regexp_replace(NAICS, '{STRIP}', '')) NOT IN (
      SELECT trim(naics_original) FROM naics_mapping WHERE source_table = {src}
    )
  """)
  check(f"{t}: all NAICS names mapped (source_table {src})",
        len(missing) == 0,
        f"unmapped: {[m[0] for m in missing]}" if missing else "")

  # informational: mapping rows with no matching data (expected for AGG rows)
  unused = q(f"""
    SELECT naics_original, mapping_type FROM naics_mapping
    WHERE source_table = {src}
      AND trim(naics_original) NOT IN (
        SELECT DISTINCT trim(regexp_replace(NAICS, '{STRIP}', '')) FROM {t})
  """)
  if unused:
    log(f"   {t}: mapping rows not present in data: {unused}")

n = scalar("SELECT COUNT(*) FROM naics_mapping WHERE naics_harmonized IS NULL OR mapping_type IS NULL")
check("naics_mapping: harmonized + mapping_type populated", n == 0, f"{n} rows" if n else "")

n = scalar("""SELECT COUNT(*) FROM (SELECT source_table, naics_original FROM naics_mapping
              GROUP BY 1,2 HAVING COUNT(*)>1)""")
check("naics_mapping: unique (source_table, naics_original)", n == 0, f"{n} dups" if n else "")

n = scalar("""SELECT COUNT(*) FROM naics_mapping
              WHERE source_table NOT IN (14100022, 14100063, 14100372)""")
check("naics_mapping: source_table values are the 3 known tables", n == 0, f"{n} rows" if n else "")

log("\n   mapping_type distribution:")
for mt, c in q("SELECT mapping_type, COUNT(*) FROM naics_mapping GROUP BY 1 ORDER BY 2 DESC"):
  log(f"     {mt}: {c}")

# ---- result ----
log("\n" + "=" * 80)
log("VALIDATION RESULT")
log("=" * 80)
fails = results.count(False)
log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails}")
log("Status: " + ("PASSED" if fails == 0 else "FAILED"))

OUT.write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if fails == 0 else 1)