"""
09 — Data Warehouse
02 - VALIDATION
Reads data/warehouse.duckdb, runs integrity checks, writes outputs/09_02_validation_report.txt.
Exit code 1 if any FAIL.
"""

import sys
from pathlib import Path
import duckdb

DB = "data/warehouse.duckdb"
OUT = Path("outputs/09_02_validation_report.txt")
OUT.parent.mkdir(exist_ok=True)

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

# ---- expected row counts (from load report) ----
expected = {"employment": 1680, "wages": 1140, "vacancies": 1260,
            "labour_force_total": 60, "naics_mapping": 69}
for t, n in expected.items():
    check(f"{t}: row count == {n}", scalar(f"SELECT COUNT(*) FROM {t}") == n)

# ---- null checks on keys ----
keys = {
    "employment": ["REF_DATE", "GEO", "NAICS"],
    "wages": ["REF_DATE", "GEO", "NAICS"],
    "vacancies": ["REF_DATE", "GEO", "NAICS"],
    "labour_force_total": ["REF_DATE", "GEO"],
}
for t, ks in keys.items():
    for k in ks:
        n = scalar(f'SELECT COUNT(*) FROM {t} WHERE "{k}" IS NULL')
        check(f"{t}.{k}: no NULLs", n == 0, f"{n} nulls" if n else "")

# ---- duplicate keys ----
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
]
for t, c, cond in ranges:
    bad = scalar(f'SELECT COUNT(*) FROM {t} WHERE "{c}" IS NOT NULL AND NOT ("{c}" {cond})')
    check(f"{t}.{c} {cond}", bad == 0, f"{bad} out-of-range" if bad else "")

# ---- date coverage ----
log("\n-- Date coverage --")
for t in keys:
    mn, mx, nd = q(f"SELECT MIN(REF_DATE), MAX(REF_DATE), COUNT(DISTINCT REF_DATE) FROM {t}")[0]
    log(f"   {t}: {mn} -> {mx}, {nd} distinct periods")
gaps = scalar("""
    SELECT COUNT(*) FROM (
      SELECT REF_DATE, LAG(REF_DATE) OVER (ORDER BY REF_DATE) prev
      FROM (SELECT DISTINCT REF_DATE FROM labour_force_total)
    ) WHERE prev IS NOT NULL AND date_diff('month', prev, REF_DATE) <> 1
""")
check("labour_force_total: monthly series has no gaps", gaps == 0, f"{gaps} gaps" if gaps else "")

# ---- cross-field consistency ----
log("\n-- Consistency --")
n = scalar("""
    SELECT COUNT(*) FROM labour_force_total
    WHERE ABS(Labour_force_thousands - (Employment_thousands + Unemployment_thousands)) > 1.0
""")
check("labour_force_total: LF = Employment + Unemployment (tol 1k)", n == 0, f"{n} rows off" if n else "")

n = scalar("""
    SELECT COUNT(*) FROM labour_force_total
    WHERE ABS(Unemployment_rate_pct - 100.0*Unemployment_thousands/Labour_force_thousands) > 0.15
""")
check("labour_force_total: unemployment rate recomputes (tol 0.15pp)", n == 0, f"{n} rows off" if n else "")

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

# ---- NAICS mapping coverage ----
log("\n-- NAICS mapping coverage --")
SRC = {"employment": 14100022, "wages": 14100063, "vacancies": 14100372}
STRIP = r"\s*\[[^\]]*\]\s*$"   # drops trailing " [21, 113-114, ...]"

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

# ---- GEO ----
log("\n-- GEO values --")
for t in keys:
    geos = [g[0] for g in q(f"SELECT DISTINCT GEO FROM {t} ORDER BY 1")]
    log(f"   {t}: {geos}")

# ---- result ----
log("\n" + "=" * 80)
log("VALIDATION RESULT")
log("=" * 80)
fails = results.count(False)
log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails}")
log("Status: " + ("PASSED" if fails == 0 else "FAILED"))

OUT.write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if fails == 0 else 1)