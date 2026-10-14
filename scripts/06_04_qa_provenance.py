"""
06 — Data Warehouse
04 - QA + PROVENANCE

Read-only against data/warehouse.duckdb. Writes:
  outputs/06_04_qa_report.txt
  outputs/06_04_null_vacancies.csv

Sections:
  1. Row lineage: every source row is kept (direct/component) or dropped for a named reason
  2. aggregate_qa reconciliation (employment table), per GEO and month
  3. NULL vacancy audit: which rows, which quality flags
  4. CPI coverage and GEO coverage of the harmonized tables

Geography: reconciliations run within each GEO. Provinces are never summed
to derive Canada; the Canada-vs-provinces gap is reported for information only.

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
NATIONAL_GEO = "Canada"
N_GEOS = 11
N_MONTHS = 60

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

  by_geo = q(f"""
    SELECT d.GEO, COUNT(*) FILTER (WHERE m.mapping_type IN ('direct','component')), COUNT(*)
    FROM {t} d
    LEFT JOIN naics_mapping m
      ON m.source_table = {src} AND trim(m.naics_original) = {CLEAN}
    GROUP BY 1 ORDER BY 1
  """)
  log("   kept/total by GEO: " + ", ".join(f"{g}={k}/{n}" for g, k, n in by_geo))

# ------------------------------------------------- 2. aggregate_qa reconciliation
log("\n-- 2. aggregate_qa rows in mapping --")
agg = q("""
  SELECT source_table, naics_original, naics_code, naics_harmonized, notes
  FROM naics_mapping WHERE mapping_type = 'aggregate_qa' ORDER BY 1, 2
""")
for r in agg:
  log(f"   {r}")

log("\n-- 2b. Reconciliation (employment table, per GEO and month) --")
log("   only months where all components are present and complete are compared")
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
  esc = name.replace("'", "''")

  n_agg = q(f"""
    SELECT COUNT(*) FROM (
      SELECT REF_DATE, GEO FROM employment d
      WHERE trim(regexp_replace(d.NAICS, '{STRIP}', '')) = '{esc}'
      GROUP BY 1, 2)
  """)[0][0]

  rows = q(f"""
    WITH a AS (
      SELECT d.REF_DATE, d.GEO, SUM(d.Employment_thousands) AS agg_val
      FROM employment d
      WHERE trim(regexp_replace(d.NAICS, '{STRIP}', '')) = '{esc}'
      GROUP BY 1, 2),
    c AS (
      SELECT REF_DATE, GEO, SUM(employment_thousands) AS comp_val
      FROM employment_h
      WHERE naics_harmonized IN ({comp_list})
      GROUP BY 1, 2
      HAVING COUNT(*) = {len(comps)} AND COUNT(employment_thousands) = {len(comps)})
    SELECT a.GEO, a.REF_DATE, a.agg_val, c.comp_val, abs(a.agg_val - c.comp_val) AS diff
    FROM a JOIN c USING (REF_DATE, GEO)
  """)
  if not rows:
    warn(f"'{name}': no comparable (GEO, month) found (aggregate missing or components incomplete)")
    continue

  skipped = n_agg - len(rows)
  worst = {}
  for geo, _, _, _, diff in rows:
    worst[geo] = max(worst.get(geo, 0.0), diff)
  max_diff = max(worst.values())
  bad_geos = sorted(g for g, d in worst.items() if d > EMP_TOL)

  check(f"'{name}' == sum of {len(comps)} harmonized industries (tol {EMP_TOL}k, every GEO)",
        not bad_geos,
        f"max abs diff {max_diff:.2f}k over {len(rows)} (GEO, month) pairs; "
        f"{skipped} skipped as incomplete" +
        (f"; over tolerance: {bad_geos}" if bad_geos else ""))
  log("     max diff by GEO: " + ", ".join(f"{g}={d:.2f}" for g, d in sorted(worst.items())))

# Canada vs sum of provinces: informational only
gap = q(f"""
  SELECT MAX(ABS(c.employment_thousands - p.s)), COUNT(*) FROM
    (SELECT REF_DATE, employment_thousands FROM employment_h
     WHERE GEO = '{NATIONAL_GEO}' AND naics_harmonized = 'Utilities') c
  JOIN (SELECT REF_DATE, SUM(employment_thousands) s FROM employment_h
        WHERE GEO <> '{NATIONAL_GEO}' AND naics_harmonized = 'Utilities' GROUP BY 1) p USING (REF_DATE)
""")
log(f"   INFO: example gap Canada vs sum of provinces (Utilities): {gap[0][0]} thousand over {gap[0][1]} months "
    "(provinces do not add up to Canada; never derive Canada by summing provinces)")

# ------------------------------------------------------ 3. NULL vacancy audit
log("\n-- 3. NULL vacancy audit --")
nulls = q("""
  SELECT REF_DATE, GEO, NAICS, Job_vacancies, Payroll_employees, Job_vacancy_rate_pct,
         Job_vacancies_quality, Payroll_employees_quality, Job_vacancy_rate_quality
  FROM vacancies WHERE Job_vacancies IS NULL ORDER BY GEO, NAICS, REF_DATE
""")
log(f"   rows with NULL Job_vacancies: {len(nulls)}")
for r in nulls:
  log(f"     {r[0]} | {r[1]} | {r[2]} | quality: vac={r[6]}, payroll={r[7]}, rate={r[8]}")

con.execute(f"""
  COPY (SELECT * FROM vacancies WHERE Job_vacancies IS NULL ORDER BY GEO, NAICS, REF_DATE)
  TO '{CSV.as_posix()}' (HEADER, DELIMITER ',')
""")
log(f"   written: {CSV}")

log("\n   Job_vacancies_quality distribution (all rows):")
for qv, c in q("SELECT Job_vacancies_quality, COUNT(*) FROM vacancies GROUP BY 1 ORDER BY 2 DESC"):
  log(f"     {qv}: {c}")

log("\n   industries affected (source level):")
for geo, nm, c in q("""
  SELECT GEO, NAICS, COUNT(*) FROM vacancies
  WHERE Job_vacancies IS NULL GROUP BY 1, 2 ORDER BY 3 DESC
"""):
  log(f"     {geo} | {nm}: {c} months")

unflagged = [r for r in nulls if r[6] is None or str(r[6]).strip() == ""]
check("every NULL vacancy row has a Job_vacancies_quality flag (documented missingness)",
      len(unflagged) == 0, f"{len(unflagged)} unflagged" if unflagged else "")

n = q("SELECT COUNT(*) FROM vacancies WHERE Job_vacancies IS NULL AND Job_vacancy_rate_pct IS NOT NULL")[0][0]
check("NULL vacancies never have a populated rate", n == 0, f"{n} rows" if n else "")

n = q("SELECT COUNT(*) FROM vacancies_h WHERE job_vacancies IS NULL")[0][0]
log(f"\n   harmonized industry-months set to NULL (propagated): {n}")

# ------------------------------------------------------ 4. CPI + GEO coverage
log("\n-- 4. CPI and GEO coverage --")
rows = q("SELECT GEO, COUNT(*), MIN(REF_DATE), MAX(REF_DATE) FROM cpi GROUP BY 1 ORDER BY 1")
for geo, n, mn, mx in rows:
  log(f"   cpi {geo}: {n} months, {mn} -> {mx}")
check(f"cpi: {N_GEOS} GEO x {N_MONTHS} months", len(rows) == N_GEOS and all(r[1] == N_MONTHS for r in rows),
      str([(r[0], r[1]) for r in rows if r[1] != N_MONTHS]) if rows else "empty")

n = q("SELECT COUNT(*) FROM cpi WHERE CPI IS NULL")[0][0]
check("cpi: no NULL index values", n == 0, f"{n} rows" if n else "")

n = q("""
  SELECT COUNT(*) FROM geo_monthly
  WHERE cpi IS NULL OR unemployment_rate_pct IS NULL
""")[0][0]
check("geo_monthly: CPI and unemployment rate present for every GEO and month", n == 0,
      f"{n} rows" if n else "")

log("\n   industry_monthly coverage by GEO (rows with value / total rows):")
for geo, tot, emp, wage, vac in q("""
  SELECT GEO, COUNT(*), COUNT(employment_thousands), COUNT(avg_hourly_wage_cad), COUNT(job_vacancies)
  FROM industry_monthly GROUP BY 1 ORDER BY 1
"""):
  log(f"     {geo}: total {tot}, employment {emp}, avg wage {wage}, vacancies {vac}")

n = q(f"SELECT COUNT(*) FROM industry_monthly WHERE GEO <> '{NATIONAL_GEO}' AND job_vacancies IS NOT NULL")[0][0]
check("vacancies are Canada only: no provincial vacancy values in industry_monthly", n == 0,
      f"{n} rows" if n else "")

# ---------------------------------------------------------------------- result
log("\n" + "=" * 80)
log("QA RESULT")
log("=" * 80)
fails = results.count(False)
log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails} | Warnings: {len(warns)}")
log("Status: " + ("PASSED" if fails == 0 else "FAILED"))

OUT.write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if fails == 0 else 1)