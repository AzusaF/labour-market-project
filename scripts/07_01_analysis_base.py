"""
07 — Analysis
01 - ANALYSIS BASE

Builds the two national-level tables that every later analysis script reads.
Reads data/warehouse.duckdb (stage 06) and writes two tables back into it:

  analysis_national_monthly   Canada x month, all industries
      labour force, unemployment, total job vacancies, total average wage
      (nominal and real), CPI, vacancies per unemployed person (V/U)
      -> Beveridge curve, tightness x wage (Phillips-type), lag correlation

  analysis_industry_chain     Canada x harmonized industry x month
      levels plus 12-month % change of employment, real average wage and
      job vacancies, and a full_chain flag (all three changes available)
      -> employment -> vacancies -> wages chain, clustering, pass-through

Scope:
  - National only (GEO = 'Canada'). Vacancies are published for Canada only.
  - Nothing is summed across GEO.
  - 12-month changes use a self-join on REF_DATE - 12 months (not LAG), so a
    missing month gives NULL instead of a wrong comparison. They start at
    2022-01.
  - Real wage = nominal wage * 100 / cpi_rebased (BASE_MONTH = 100).

Writes outputs/07_01_analysis_base_report.txt. Exit 1 on FAIL. WARN does not fail.
"""
import sys
from pathlib import Path
import duckdb

DB = "data/warehouse.duckdb"
OUT = Path("outputs/07_01_analysis_base_report.txt")
OUT.parent.mkdir(exist_ok=True)

NATIONAL_GEO = "Canada"
STRIP = r"\s*\[[^\]]*\]\s*$"
TOTAL_LABEL = "Total, all industries"            # vacancies source table
TOTAL_WAGE_LABEL = "Total employees, all industries"  # wages source table
N_MONTHS = 60
FIRST_YOY_MONTH = "2022-01-01"
MIN_CHAIN_MONTHS = 24   # industries with fewer full-chain months get a WARN

con = duckdb.connect(DB)
lines, results, warns = [], [], []


def log(s=""):
  print(s)
  lines.append(s)


def check(name, ok, detail=""):
  results.append(ok)
  log(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


def warn(msg):
  warns.append(msg)
  log(f"[WARN] {msg}")


def q(sql):
  return con.execute(sql).fetchall()


log("=" * 80)
log("ANALYSIS BASE")
log("=" * 80)

# ------------------------------------------------ national, all industries
con.execute(f"""
  CREATE OR REPLACE TABLE analysis_national_monthly AS
  WITH vac AS (
    SELECT REF_DATE,
           Job_vacancies             AS job_vacancies,
           Payroll_employees         AS payroll_employees,
           Job_vacancy_rate_pct      AS job_vacancy_rate_pct,
           Job_vacancies_quality     AS job_vacancies_quality
    FROM vacancies
    WHERE GEO = '{NATIONAL_GEO}'
      AND trim(regexp_replace(NAICS, '{STRIP}', '')) = '{TOTAL_LABEL}'
  ),
  wage AS (
    SELECT REF_DATE,
           Average_hourly_wage_cad   AS avg_hourly_wage_cad,
           Median_hourly_wage_cad    AS median_hourly_wage_cad
    FROM wages
    WHERE GEO = '{NATIONAL_GEO}'
      AND trim(regexp_replace(NAICS, '{STRIP}', '')) = '{TOTAL_WAGE_LABEL}'
  )
  SELECT g.REF_DATE,
         g.GEO,
         g.Labour_force_thousands  AS labour_force_thousands,
         g.Employment_thousands    AS employment_thousands,
         g.Unemployment_thousands  AS unemployment_thousands,
         g.Unemployment_rate_pct   AS unemployment_rate_pct,
         v.job_vacancies,
         v.payroll_employees,
         v.job_vacancy_rate_pct,
         v.job_vacancies_quality,
         v.job_vacancies / NULLIF(g.Unemployment_thousands * 1000.0, 0)
                                   AS vacancies_per_unemployed,
         w.avg_hourly_wage_cad,
         w.median_hourly_wage_cad,
         w.avg_hourly_wage_cad    * 100.0 / g.cpi_rebased AS real_avg_hourly_wage_cad,
         w.median_hourly_wage_cad * 100.0 / g.cpi_rebased AS real_median_hourly_wage_cad,
         g.cpi,
         g.cpi_rebased,
         g.cpi_yoy_pct
  FROM geo_monthly g
  LEFT JOIN vac  v USING (REF_DATE)
  LEFT JOIN wage w USING (REF_DATE)
  WHERE g.GEO = '{NATIONAL_GEO}'
  ORDER BY g.REF_DATE
""")

# ------------------------------------------------ industry chain (Canada)
con.execute(f"""
  CREATE OR REPLACE TABLE analysis_industry_chain AS
  WITH base AS (
    SELECT REF_DATE, naics_harmonized,
           employment_thousands,
           real_avg_hourly_wage_cad,
           job_vacancies,
           job_vacancy_rate_pct,
           worst_vacancy_quality
    FROM industry_monthly
    WHERE GEO = '{NATIONAL_GEO}'
  ),
  yoy AS (
    SELECT b.*,
           100.0 * (b.employment_thousands
                    / NULLIF(p.employment_thousands, 0) - 1)       AS employment_yoy_pct,
           100.0 * (b.real_avg_hourly_wage_cad
                    / NULLIF(p.real_avg_hourly_wage_cad, 0) - 1)   AS real_wage_yoy_pct,
           100.0 * (b.job_vacancies
                    / NULLIF(p.job_vacancies, 0) - 1)              AS vacancies_yoy_pct
    FROM base b
    LEFT JOIN base p
      ON p.naics_harmonized = b.naics_harmonized
     AND p.REF_DATE = b.REF_DATE - INTERVAL 12 MONTH
  )
  SELECT *,
         (employment_yoy_pct IS NOT NULL
          AND real_wage_yoy_pct IS NOT NULL
          AND vacancies_yoy_pct IS NOT NULL) AS full_chain
  FROM yoy
  ORDER BY naics_harmonized, REF_DATE
""")

# ------------------------------------------------ checks: national table
log("\n-- analysis_national_monthly --")
n, d, mn, mx = q("""
  SELECT COUNT(*), COUNT(DISTINCT REF_DATE), MIN(REF_DATE), MAX(REF_DATE)
  FROM analysis_national_monthly
""")[0]
log(f"   {n} rows, {d} distinct months, {mn} -> {mx}")
check(f"national: one row per month, {N_MONTHS} months", n == d == N_MONTHS)

for col in ["unemployment_thousands", "unemployment_rate_pct", "cpi", "cpi_rebased"]:
  k = q(f"SELECT COUNT(*) FROM analysis_national_monthly WHERE {col} IS NULL")[0][0]
  check(f"national.{col}: no NULLs", k == 0, f"{k} NULL" if k else "")

for col in ["job_vacancies", "job_vacancy_rate_pct", "vacancies_per_unemployed",
            "avg_hourly_wage_cad", "real_avg_hourly_wage_cad"]:
  k = q(f"SELECT COUNT(*) FROM analysis_national_monthly WHERE {col} IS NULL")[0][0]
  check(f"national.{col}: present for every month (needed for Beveridge / tightness)",
        k == 0, f"{k} NULL" if k else "")

k = q("SELECT COUNT(*) FROM analysis_national_monthly WHERE cpi_yoy_pct IS NULL "
      f"AND REF_DATE >= DATE '{FIRST_YOY_MONTH}'")[0][0]
check(f"national.cpi_yoy_pct: available from {FIRST_YOY_MONTH[:7]}", k == 0,
      f"{k} NULL" if k else "")

lo, hi = q("""
  SELECT MIN(vacancies_per_unemployed), MAX(vacancies_per_unemployed)
  FROM analysis_national_monthly
""")[0]
if lo is not None:
  log(f"   V/U range: {lo:.3f} to {hi:.3f}")
  check("national: V/U within plausible range (0 to 3)", 0 <= lo and hi <= 3)

lo, hi = q("""
  SELECT MIN(real_avg_hourly_wage_cad), MAX(real_avg_hourly_wage_cad)
  FROM analysis_national_monthly
""")[0]
if lo is not None:
  log(f"   real avg hourly wage (BASE_MONTH dollars): {lo:.2f} to {hi:.2f}")

# ------------------------------------------------ checks: industry chain
log("\n-- analysis_industry_chain --")
n, k = q("SELECT COUNT(*), COUNT(DISTINCT naics_harmonized) FROM analysis_industry_chain")[0]
log(f"   {n} rows, {k} harmonized industries")
check("chain: not empty", n > 0)

dups = q("""
  SELECT COUNT(*) FROM (
    SELECT REF_DATE, naics_harmonized FROM analysis_industry_chain
    GROUP BY 1, 2 HAVING COUNT(*) > 1)
""")[0][0]
check("chain: unique on (REF_DATE, naics_harmonized)", dups == 0,
      f"{dups} dups" if dups else "")

early = q(f"""
  SELECT COUNT(*) FROM analysis_industry_chain
  WHERE REF_DATE < DATE '{FIRST_YOY_MONTH}'
    AND (employment_yoy_pct IS NOT NULL OR real_wage_yoy_pct IS NOT NULL
         OR vacancies_yoy_pct IS NOT NULL)
""")[0][0]
check(f"chain: no 12-month change before {FIRST_YOY_MONTH[:7]}", early == 0,
      f"{early} rows" if early else "")

# the yoy self-join must not multiply or drop rows
src = q(f"SELECT COUNT(*) FROM industry_monthly WHERE GEO = '{NATIONAL_GEO}'")[0][0]
check("chain: same row count as industry_monthly (Canada)", src == n, f"{src} vs {n}")

log("\n   12-month changes available, by industry (employment / wage / vacancies / full chain):")
rows = q("""
  SELECT naics_harmonized,
         COUNT(*) FILTER (WHERE employment_yoy_pct IS NOT NULL),
         COUNT(*) FILTER (WHERE real_wage_yoy_pct  IS NOT NULL),
         COUNT(*) FILTER (WHERE vacancies_yoy_pct  IS NOT NULL),
         COUNT(*) FILTER (WHERE full_chain)
  FROM analysis_industry_chain GROUP BY 1 ORDER BY 5 DESC, 1
""")
for name, e, w, v, c in rows:
  log(f"     {name}: {e} / {w} / {v} / {c}")
  if c < MIN_CHAIN_MONTHS:
    warn(f"'{name}': only {c} full-chain months (< {MIN_CHAIN_MONTHS}); "
         "exclude or treat with care in cross-industry analysis")

usable = [r[0] for r in rows if r[4] >= MIN_CHAIN_MONTHS]
check("chain: at least one industry with enough full-chain months", len(usable) > 0,
      f"{len(usable)} usable industries")

log("\n   vacancy quality of rows in the chain (worst of components):")
for qv, c in q("""
  SELECT worst_vacancy_quality, COUNT(*) FROM analysis_industry_chain
  WHERE job_vacancies IS NOT NULL GROUP BY 1 ORDER BY 1
"""):
  log(f"     {qv}: {c}")

# ---------------------------------------------------------------------- result
log("\n" + "=" * 80)
log("ANALYSIS BASE RESULT")
log("=" * 80)
fails = results.count(False)
log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails} | Warnings: {len(warns)}")
log("Status: " + ("PASSED" if fails == 0 else "FAILED"))

OUT.write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if fails == 0 else 1)