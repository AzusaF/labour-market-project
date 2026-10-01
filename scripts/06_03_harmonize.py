"""
06 — Data Warehouse
03 - HARMONIZE

Builds NAICS-harmonized tables in data/warehouse.duckdb using naics_mapping:
  employment_h, wages_h, vacancies_h, industry_monthly

Rules:
  - keep mapping_type in ('direct','component'); drop aggregate_qa / exclude_redundant / residual_excluded
  - employment: SUM across components
  - wages: employment-weighted mean of average wage; median only when a single component (not additive)
  - vacancies: SUM vacancies and payroll; rate recomputed as V/(V+P);
               vacancies/rate are NULL if any component is NULL (no partial sums)

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
    return f"""
        SELECT d.*, m.naics_harmonized, m.mapping_type
        FROM {t} d
        JOIN naics_mapping m
          ON m.source_table = {SRC[t]}
         AND trim(m.naics_original) = trim(regexp_replace(d.NAICS, '{STRIP}', ''))
        WHERE m.mapping_type IN ('direct', 'component')
    """


log("=" * 80)
log("HARMONIZE")
log("=" * 80)

con.execute(f"""
    CREATE OR REPLACE TABLE employment_h AS
    SELECT REF_DATE, GEO, naics_harmonized,
           SUM(Employment_thousands) AS employment_thousands,
           COUNT(*)                  AS n_components
    FROM ({mapped('employment')})
    GROUP BY 1, 2, 3
""")

con.execute(f"""
    CREATE OR REPLACE TABLE wages_h AS
    SELECT REF_DATE, GEO, naics_harmonized,
           SUM(Total_employees_thousands) AS employees_thousands,
           SUM(Average_hourly_wage_cad * Total_employees_thousands)
               / NULLIF(SUM(Total_employees_thousands), 0) AS avg_hourly_wage_cad,
           CASE WHEN COUNT(*) = 1 THEN MAX(Median_hourly_wage_cad) END AS median_hourly_wage_cad,
           COUNT(*) AS n_components
    FROM ({mapped('wages')})
    GROUP BY 1, 2, 3
""")

con.execute(f"""
    CREATE OR REPLACE TABLE vacancies_h AS
    SELECT REF_DATE, GEO, naics_harmonized,
           CASE WHEN COUNT(*) FILTER (WHERE Job_vacancies IS NULL) = 0
                THEN SUM(Job_vacancies) END AS job_vacancies,
           SUM(Payroll_employees) AS payroll_employees,
           CASE WHEN COUNT(*) FILTER (WHERE Job_vacancies IS NULL) = 0
                THEN 100.0 * SUM(Job_vacancies) / (SUM(Job_vacancies) + SUM(Payroll_employees))
           END AS job_vacancy_rate_pct,
           COUNT(*) AS n_components,
           COUNT(*) FILTER (WHERE Job_vacancies IS NULL) AS n_null_components,
           MAX(Job_vacancies_quality) AS worst_vacancy_quality  -- A best ... F worst
    FROM ({mapped('vacancies')})
    GROUP BY 1, 2, 3
""")

con.execute("""
    CREATE OR REPLACE TABLE industry_monthly AS
    SELECT REF_DATE, GEO, naics_harmonized,
           e.employment_thousands,
           w.employees_thousands, w.avg_hourly_wage_cad, w.median_hourly_wage_cad,
           v.job_vacancies, v.payroll_employees, v.job_vacancy_rate_pct,
           v.worst_vacancy_quality,
           e.n_components AS emp_components,
           w.n_components AS wage_components,
           v.n_components AS vac_components
    FROM employment_h e
    FULL JOIN wages_h w     USING (REF_DATE, GEO, naics_harmonized)
    FULL JOIN vacancies_h v USING (REF_DATE, GEO, naics_harmonized)
""")

# ---- row counts ----
log("\n-- Output tables --")
for t in ["employment_h", "wages_h", "vacancies_h", "industry_monthly"]:
    n, k = q(f"SELECT COUNT(*), COUNT(DISTINCT naics_harmonized) FROM {t}")[0]
    log(f"   {t}: {n} rows, {k} harmonized industries")
    check(f"{t}: not empty", n > 0)

# ---- component count stable over time (no partial sums) ----
log("\n-- Component stability --")
for t in ["employment_h", "wages_h", "vacancies_h"]:
    bad = q(f"""
        SELECT naics_harmonized, MIN(n_components), MAX(n_components)
        FROM {t} GROUP BY 1 HAVING MIN(n_components) <> MAX(n_components)
    """)
    check(f"{t}: n_components constant across months", not bad, str(bad) if bad else "")

# ---- one row per period per industry ----
for t in ["employment_h", "wages_h", "vacancies_h", "industry_monthly"]:
    n = q(f"""SELECT COUNT(*) FROM (SELECT REF_DATE, GEO, naics_harmonized FROM {t}
              GROUP BY 1,2,3 HAVING COUNT(*) > 1)""")[0][0]
    check(f"{t}: unique on (REF_DATE, GEO, naics_harmonized)", n == 0, f"{n} dups" if n else "")

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

# ---- reconciliation vs labour force total (informational) ----
log("\n-- Harmonized employment vs labour_force_total.Employment_thousands --")
lo, hi = q("""
    SELECT MIN(r), MAX(r) FROM (
        SELECT SUM(e.employment_thousands) / l.Employment_thousands AS r
        FROM employment_h e JOIN labour_force_total l USING (REF_DATE)
        GROUP BY e.REF_DATE, l.Employment_thousands)
""")[0]
log(f"   sum(harmonized) / total employment: min {lo:.3f}, max {hi:.3f}")
log("   (should be close to 1; if not, check for aggregate rows kept as direct)")

# ---- quality flag carried through ----
log("\n-- worst_vacancy_quality in industry_monthly --")
for qv, c in q("SELECT worst_vacancy_quality, COUNT(*) FROM industry_monthly GROUP BY 1 ORDER BY 1"):
    log(f"   {qv}: {c}")
n = q("SELECT COUNT(*) FROM industry_monthly WHERE worst_vacancy_quality IS NULL")[0][0]
check("worst_vacancy_quality populated for every industry-month", n == 0, f"{n} NULL" if n else "")

# ---- vacancy NULL propagation ----
n = q("SELECT COUNT(*) FROM vacancies_h WHERE job_vacancies IS NULL")[0][0]
log(f"\n-- vacancies_h rows with NULL vacancies (suppressed component): {n}")

log("\n" + "=" * 80)
log("HARMONIZE RESULT")
log("=" * 80)
fails = results.count(False)
log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails}")
log("Status: " + ("PASSED" if fails == 0 else "FAILED"))

OUT.write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if fails == 0 else 1)