"""
08 — Dashboard
01 - EXPORT FOR TABLEAU

Writes flat CSV files for Tableau Public. Tableau Public cannot read DuckDB,
so every table the dashboard needs is exported once, with dates as real dates
(YYYY-MM-DD, first of the month) and the derived measures already computed.

Input (read-only):
  data/warehouse.duckdb
    analysis_national_monthly   (from 07_01)
    analysis_industry_chain     (from 07_01)
  outputs/07_02_chain_summary.csv
  outputs/07_02_chain_cross_section.csv
  outputs/07_03_beveridge_points.csv
  outputs/07_04_national_lags.csv
  outputs/07_04_passthrough.csv
  outputs/07_04_tightness_cross_section.csv

Output (outputs/bi/):
  national_monthly.csv        1 row per month (60). Levels + 12-month changes.
  industry_monthly.csv        1 row per (month, industry). From analysis_industry_chain.
  beveridge_points.csv        1 row per month. u, v, fit, residual, 3-month averages.
  national_lags.csv           tightness vs wage growth, by measure and lag
  passthrough.csv             CPI pass-through slope, by series and lag (+ series_type)
  tightness_cross_section.csv cross-industry vacancy rate vs wage growth, by lag
  chain_summary.csv           chain verdict per industry (raw and relative series)
  chain_cross_section.csv     cross-industry chain links, by link and lag
  outputs/08_01_export_report.txt

Scope: Canada only. Nothing is summed across GEO. The caveats of stage 07 apply
to every view built on these files: descriptive only, one inflation cycle,
not seasonally adjusted.

Exit 1 on FAIL. WARN does not fail.
"""
import sys
from pathlib import Path
import duckdb
import pandas as pd

DB = "data/warehouse.duckdb"
OUT_DIR = Path("outputs/bi")
REPORT = Path("outputs/08_01_export_report.txt")
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_MONTHS = 60
NATIONAL_NAME = "ALL INDUSTRIES (national)"
POOLED_NAME = "POOLED within industries"

COPIES = {
  "chain_summary": Path("outputs/07_02_chain_summary.csv"),
  "chain_cross_section": Path("outputs/07_02_chain_cross_section.csv"),
  "beveridge_points": Path("outputs/07_03_beveridge_points.csv"),
  "national_lags": Path("outputs/07_04_national_lags.csv"),
  "passthrough": Path("outputs/07_04_passthrough.csv"),
  "tightness_cross_section": Path("outputs/07_04_tightness_cross_section.csv"),
}

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


def finish():
  log("\n" + "=" * 80)
  log("EXPORT RESULT")
  log("=" * 80)
  fails = results.count(False)
  log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails} | Warnings: {len(warns)}")
  log("Status: " + ("PASSED" if fails == 0 else "FAILED"))
  REPORT.write_text("\n".join(lines), encoding="utf-8")
  sys.exit(0 if fails == 0 else 1)


def write(df, name):
  path = OUT_DIR / f"{name}.csv"
  df.to_csv(path, index=False)
  log(f"   written: {path}  ({len(df)} rows, {len(df.columns)} columns)")
  return path


log("=" * 80)
log("EXPORT FOR TABLEAU")
log("=" * 80)

missing = [str(p) for p in COPIES.values() if not p.exists()]
check("all stage-07 CSV outputs exist", not missing, f"missing: {missing}" if missing else "")
if missing or not Path(DB).exists():
  if not Path(DB).exists():
    check("warehouse exists", False, DB)
  finish()

con = duckdb.connect(DB, read_only=True)

# ------------------------------------------------------- national_monthly
nat = con.execute("""
  SELECT REF_DATE, labour_force_thousands, employment_thousands,
         unemployment_thousands, unemployment_rate_pct,
         job_vacancies, payroll_employees, job_vacancy_rate_pct,
         vacancies_per_unemployed,
         avg_hourly_wage_cad, median_hourly_wage_cad,
         real_avg_hourly_wage_cad, real_median_hourly_wage_cad,
         cpi, cpi_rebased, cpi_yoy_pct
  FROM analysis_national_monthly ORDER BY REF_DATE
""").fetchdf()
nat["REF_DATE"] = pd.to_datetime(nat["REF_DATE"])
check(f"national: {N_MONTHS} months, one row per month",
      len(nat) == N_MONTHS and nat["REF_DATE"].is_unique, f"{len(nat)} rows")

full_grid = pd.date_range(nat["REF_DATE"].min(), nat["REF_DATE"].max(), freq="MS")
check("national: no missing months in the span", len(full_grid) == len(nat))

nat = nat.set_index("REF_DATE").reindex(full_grid)
# same definition as 07_02 / 07_04: 12-month % change on the complete monthly grid
nat["employment_yoy_pct"] = 100.0 * nat["employment_thousands"].pct_change(12, fill_method=None)
nat["vacancies_yoy_pct"] = 100.0 * nat["job_vacancies"].pct_change(12, fill_method=None)
nat["nominal_wage_yoy_pct"] = 100.0 * nat["avg_hourly_wage_cad"].pct_change(12, fill_method=None)
nat["real_wage_yoy_pct"] = 100.0 * nat["real_avg_hourly_wage_cad"].pct_change(12, fill_method=None)
nat = nat.rename_axis("month").reset_index()
nat["year"] = nat["month"].dt.year
nat["month"] = nat["month"].dt.strftime("%Y-%m-%d")

first_yoy = nat.dropna(subset=["nominal_wage_yoy_pct"])["month"].min()
log(f"   12-month changes start: {first_yoy[:7]}")
check("national: 12-month changes start in 2022-01", first_yoy.startswith("2022-01"), first_yoy)
write(nat.round(4), "national_monthly")

# ------------------------------------------------------- industry_monthly
ind = con.execute("SELECT * FROM analysis_industry_chain ORDER BY naics_harmonized, REF_DATE").fetchdf()
con.close()
ind["REF_DATE"] = pd.to_datetime(ind["REF_DATE"])
check("industry: not empty", len(ind) > 0, f"{len(ind)} rows, {ind['naics_harmonized'].nunique()} industries")
dups = int(ind.duplicated(subset=["REF_DATE", "naics_harmonized"]).sum())
check("industry: unique on (month, industry)", dups == 0, f"{dups} dups" if dups else "")
ind["year"] = ind["REF_DATE"].dt.year
ind["month"] = ind["REF_DATE"].dt.strftime("%Y-%m-%d")
ind = ind.drop(columns="REF_DATE")
ind["full_chain"] = ind["full_chain"].astype(int)
ind = ind.rename(columns={"naics_harmonized": "industry"})
write(ind.round(4), "industry_monthly")

# ------------------------------------------------------- copies, made Tableau-friendly
frames = {name: pd.read_csv(path) for name, path in COPIES.items()}
for name, df in frames.items():
  check(f"{name}: not empty", len(df) > 0, f"{len(df)} rows")

bev = frames["beveridge_points"]
bev["REF_DATE"] = pd.to_datetime(bev["REF_DATE"], format="%Y-%m")
bev["year"] = bev["REF_DATE"].dt.year
bev["month"] = bev["REF_DATE"].dt.strftime("%Y-%m-%d")
bev = bev.drop(columns="REF_DATE").rename(columns={
  "u": "unemployment_rate_pct", "v": "job_vacancy_rate_pct", "v_per_u": "vacancies_per_unemployed",
  "v_fit": "vacancy_rate_fit_pct", "u_ma": "unemployment_rate_3m_avg", "v_ma": "vacancy_rate_3m_avg"})
check("beveridge: one row per month", len(bev) == N_MONTHS and bev["month"].is_unique, f"{len(bev)} rows")
write(bev, "beveridge_points")

pt = frames["passthrough"]
pt["series_type"] = pt["series"].map(
  lambda s: "National" if s == NATIONAL_NAME else "Pooled" if s == POOLED_NAME else "Industry")
check("passthrough: one national and one pooled series",
      (pt.drop_duplicates("series")["series_type"].value_counts().reindex(["National", "Pooled"]) == 1).all())
write(pt, "passthrough")

cs = frames["chain_summary"]
cs["is_national"] = (cs["industry"] == NATIONAL_NAME).astype(int)
check("chain_summary: has a verdict for every row", cs["verdict"].notna().all())
write(cs, "chain_summary")

write(frames["national_lags"], "national_lags")
write(frames["tightness_cross_section"], "tightness_cross_section")
write(frames["chain_cross_section"], "chain_cross_section")

# ------------------------------------------------------- cross-file consistency
months_ind = set(ind["month"])
months_nat = set(nat["month"])
check("every industry month exists in national_monthly", months_ind <= months_nat,
      f"{len(months_ind - months_nat)} unmatched" if not months_ind <= months_nat else "")
industries_cs = set(cs.loc[cs["is_national"] == 0, "industry"])
industries_ind = set(ind["industry"])
only_cs = industries_cs - industries_ind
check("every industry in chain_summary exists in industry_monthly", not only_cs,
      f"unmatched: {sorted(only_cs)}" if only_cs else "")

log("\n   Tableau: connect each CSV as a text file. Relate national_monthly and")
log("   industry_monthly on month. Keep the other files as separate data sources.")
finish()