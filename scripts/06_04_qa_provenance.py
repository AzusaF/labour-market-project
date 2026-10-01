"""
06 — Data Warehouse
04 - QA + PROVENANCE

Read-only against data/warehouse.duckdb. Writes:
  outputs/06_04_qa_report.txt
  outputs/06_04_null_vacancies.csv

Sections:
  1. Row lineage: every source row is kept (direct/component) or dropped for a named reason
  2. aggregate_qa reconciliation (employment table): aggregate rows vs sum of harmonized components
  3. NULL vacancy audit: which rows, which quality flags

Exit 1 on FAIL. WARN does not fail.
"""
import sys
from pathlib import Path
import duckdb

DB = "data/warehouse.duckdb"
OUT = Path("outputs/06_04_qa_report.txt")
CSV = Path("outputs/06_04_null_vacancies.csv")
OUT.parent.mkdir(exist_ok=True)

SRC = {"employment": 14100022, "wages": 14100063, "vacancies": 14100372}
STRIP = r"\s*\[[^\]]*\]\s*$"
CLEAN = f"trim(regexp_replace(d.NAICS, '{STRIP}', ''))"
EMP_TOL = 2.0  # thousands; rounding tolerance for sum-of-components vs aggregate

con = duckdb.connect(DB, read_only=True)
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
log("QA + PROVENANCE")
log("=" * 80)

# ---------------------------------------------------------------- 1. lineage
log("\n-- 1. Row lineage (source rows by mapping_type) --")
for t, src in SRC.items():
    rows = q(f"""
        SELECT coalesce(m.mapping_type, 'UNMAPPED') AS mt, COUNT(*)
        FROM {t} d
        LEFT JOIN naics_mapping m
          ON m.source_table = {src} AND trim(m.naics_original) = {CLEAN}
        GROUP BY 1 ORDER BY 2 DESC
    """)
    total = sum(r[1] for r in rows)
    kept = sum(r[1] for r in rows if r[0] in ("direct", "component"))
    log(f"   {t}: {total} source rows, {kept} kept")
    for mt, c in rows:
        log(f"     {mt}: {c}")
    check(f"{t}: no UNMAPPED source rows", all(r[0] != "UNMAPPED" for r in rows))

    h = {"employment": "employment_h", "wages": "wages_h", "vacancies": "vacancies_h"}[t]
    n_comp = q(f"SELECT SUM(n_components) FROM {h}")[0][0]
    check(f"{t}: kept rows ({kept}) == components feeding {h} ({n_comp})", kept == n_comp)

# ------------------------------------------------- 2. aggregate_qa reconciliation
log("\n-- 2. aggregate_qa rows in mapping --")
agg = q("""
    SELECT source_table, naics_original, naics_code, naics_harmonized, notes
    FROM naics_mapping WHERE mapping_type = 'aggregate_qa' ORDER BY 1, 2
""")
for r in agg:
    log(f"   {r}")

log("\n-- 2b. Reconciliation (employment table) --")
all_h = [r[0] for r in q("SELECT DISTINCT naics_harmonized FROM employment_h")]
goods = [h for h in all_h if h in (
    "Agriculture, forestry, fishing, mining, quarrying, oil and gas",
    "Utilities", "Construction", "Manufacturing")]
services = [h for h in all_h if h not in goods]


def rule_for(name):
    n = name.lower()
    if n.startswith("goods"):
        return goods
    if n.startswith("services"):
        return services
    if n.startswith("total"):
        return all_h
    return None


emp_aggs = [r for r in agg if r[0] == SRC["employment"]]
if not emp_aggs:
    warn("no aggregate_qa rows for the employment table; nothing to reconcile")
for _, name, *_ in emp_aggs:
    comps = rule_for(name)
    if comps is None:
        warn(f"employment aggregate '{name}': no reconciliation rule defined (add one in rule_for)")
        continue
    comp_list = ", ".join("'" + c.replace("'", "''") + "'" for c in comps)
    rows = q(f"""
        WITH a AS (
            SELECT d.REF_DATE, SUM(d.Employment_thousands) AS agg_val
            FROM employment d
            WHERE trim(regexp_replace(d.NAICS, '{STRIP}', '')) = '{name.replace("'", "''")}'
            GROUP BY 1),
        c AS (
            SELECT REF_DATE, SUM(employment_thousands) AS comp_val
            FROM employment_h WHERE naics_harmonized IN ({comp_list}) GROUP BY 1)
        SELECT a.REF_DATE, a.agg_val, c.comp_val, abs(a.agg_val - c.comp_val) AS diff
        FROM a JOIN c USING (REF_DATE)
    """)
    if not rows:
        warn(f"'{name}': aggregate not found in employment data, skipped")
        continue
    max_diff = max(r[3] for r in rows)
    ok = max_diff <= EMP_TOL
    check(f"'{name}' == sum of {len(comps)} harmonized industries (tol {EMP_TOL}k)",
          ok, f"max abs diff {max_diff:.2f}k over {len(rows)} months")

# ------------------------------------------------------ 3. NULL vacancy audit
log("\n-- 3. NULL vacancy audit --")
nulls = q("""
    SELECT REF_DATE, NAICS, Job_vacancies, Payroll_employees, Job_vacancy_rate_pct,
           Job_vacancies_quality, Payroll_employees_quality, Job_vacancy_rate_quality
    FROM vacancies WHERE Job_vacancies IS NULL ORDER BY NAICS, REF_DATE
""")
log(f"   rows with NULL Job_vacancies: {len(nulls)}")
for r in nulls:
    log(f"     {r[0]} | {r[1]} | quality: vac={r[5]}, payroll={r[6]}, rate={r[7]}")

con.execute(f"""
    COPY (SELECT * FROM vacancies WHERE Job_vacancies IS NULL ORDER BY NAICS, REF_DATE)
    TO '{CSV.as_posix()}' (HEADER, DELIMITER ',')
""")
log(f"   written: {CSV}")

log("\n   Job_vacancies_quality distribution (all rows):")
for qv, c in q("SELECT Job_vacancies_quality, COUNT(*) FROM vacancies GROUP BY 1 ORDER BY 2 DESC"):
    log(f"     {qv}: {c}")

log("\n   industries affected (source level):")
for nm, c in q("SELECT NAICS, COUNT(*) FROM vacancies WHERE Job_vacancies IS NULL GROUP BY 1 ORDER BY 2 DESC"):
    log(f"     {nm}: {c} months")

unflagged = [r for r in nulls if r[5] is None or str(r[5]).strip() == ""]
check("every NULL vacancy row has a Job_vacancies_quality flag (documented missingness)",
      len(unflagged) == 0, f"{len(unflagged)} unflagged" if unflagged else "")

n = q("SELECT COUNT(*) FROM vacancies WHERE Job_vacancies IS NULL AND Job_vacancy_rate_pct IS NOT NULL")[0][0]
check("NULL vacancies never have a populated rate", n == 0, f"{n} rows" if n else "")

n = q("SELECT COUNT(*) FROM vacancies_h WHERE job_vacancies IS NULL")[0][0]
log(f"\n   harmonized industry-months set to NULL (propagated): {n}")

# ---------------------------------------------------------------------- result
log("\n" + "=" * 80)
log("QA RESULT")
log("=" * 80)
fails = results.count(False)
log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails} | Warnings: {len(warns)}")
log("Status: " + ("PASSED" if fails == 0 else "FAILED"))

OUT.write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if fails == 0 else 1)