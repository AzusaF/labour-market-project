"""
07 — Analysis
02 - CHAIN 

Tests whether the chain
    employment growth -> job vacancy growth -> wage growth
shows up, industry by industry and across industries.

Input (read-only): data/warehouse.duckdb
  analysis_industry_chain     Canada x harmonized industry x month (from 07_01)
  analysis_national_monthly   Canada x month, all industries (from 07_01)

Why v2:
  v1 found a negative vacancies -> real wage correlation in every series,
  including the national total. In 2022-2025 inflation spikes and then falls,
  so real wage growth is mostly the mirror image of the inflation cycle and
  every industry moves with it. v2 separates that common cycle from
  industry-specific behaviour.

Parts:
  A. Time series within each industry, two versions of the variables:
       raw       12-month % changes as published
       relative  each industry minus the cross-industry mean of the same month
                 (removes the cycle shared by all industries, including CPI)
     Wage is tested both real and nominal. Links and lags (months):
       emp_to_vac 0..6, vac_to_real_wage 0..6, vac_to_nominal_wage 0..6,
       emp_to_real_wage 0..6
  B. Cross-industry, month by month: rank correlation across industries of
     x in month t with y in month t+lag, then the mean over months and the
     share of months with a positive value. Rank correlation inside one month
     is unaffected by anything common to all industries. A pooled Pearson
     over all industry-months of the relative series is added.
  C. National: how much of the vacancy -> wage correlation is the CPI cycle.

Verdict rule (parts A, per industry): a link holds when
  best-lag Pearson >= LINK_THRESHOLD, lag-0 Pearson >= 0 (same sign), and the
  best lag is not the last lag of the range (a best lag at the edge means
  the peak is outside the window and is not trusted).
  The chain holds when emp_to_vac and vac_to_real_wage both hold.

Read the results as descriptive, not causal:
  - 12-month changes overlap, so the effective sample is far smaller than the
    number of rows. No p-values are reported.
  - Choosing the best of several lags is optimistic; lag 0 is shown next to it.
  - Four years contain one inflation cycle.
  - National only; vacancies exist for Canada only.

Output:
  outputs/07_02_chain_report.txt
  outputs/07_02_chain_correlations.csv   every (series, industry, link, lag)
  outputs/07_02_chain_summary.csv        one row per (series, industry)
  outputs/07_02_chain_cross_section.csv  part B, one row per (link, lag)
"""
import sys
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

DB = "data/warehouse.duckdb"
OUT = Path("outputs/07_02_chain_report.txt")
CSV_LONG = Path("outputs/07_02_chain_correlations.csv")
CSV_SUMMARY = Path("outputs/07_02_chain_summary.csv")
CSV_CROSS = Path("outputs/07_02_chain_cross_section.csv")
OUT.parent.mkdir(exist_ok=True)

FIRST_MONTH = "2022-01-01"
LAST_MONTH = "2025-12-01"
MONTHS = pd.date_range(FIRST_MONTH, LAST_MONTH, freq="MS")

MIN_PAIRS = 24
LINK_THRESHOLD = 0.3
MIN_CHAIN_MONTHS = 24     # same cutoff as 07_01
MIN_INDUSTRIES = 8        # industries needed in a month for relative / cross-section
CS_MEAN_THRESHOLD = 0.2   # part B: mean rank correlation regarded as a link
CS_SHARE_THRESHOLD = 0.6  # part B: share of months with positive correlation
NATIONAL_NAME = "ALL INDUSTRIES (national)"

VARS = ["employment_yoy_pct", "vacancies_yoy_pct",
        "real_wage_yoy_pct", "nominal_wage_yoy_pct"]

# link name -> (x column, y column, max lag in months)
LINKS = {
  "emp_to_vac": ("employment_yoy_pct", "vacancies_yoy_pct", 6),
  "vac_to_real_wage": ("vacancies_yoy_pct", "real_wage_yoy_pct", 6),
  "vac_to_nominal_wage": ("vacancies_yoy_pct", "nominal_wage_yoy_pct", 6),
  "emp_to_real_wage": ("employment_yoy_pct", "real_wage_yoy_pct", 6),
}

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


def finish():
  log("\n" + "=" * 80)
  log("CHAIN RESULT")
  log("=" * 80)
  fails = results.count(False)
  log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails} | Warnings: {len(warns)}")
  log("Status: " + ("PASSED" if fails == 0 else "FAILED"))
  OUT.write_text("\n".join(lines), encoding="utf-8")
  sys.exit(0 if fails == 0 else 1)


def spearman(x, y):
  """Spearman = Pearson on ranks of the complete pairs (pandas needs scipy for method='spearman')."""
  pair = pd.concat([x, y], axis=1).dropna()
  if len(pair) < 2:
    return float("nan")
  return pair.iloc[:, 0].rank().corr(pair.iloc[:, 1].rank())


def demean(wide):
  """Subtract the cross-industry mean of each month; months with too few industries become NaN."""
  counts = wide.notna().sum(axis=1)
  out = wide.sub(wide.mean(axis=1), axis=0)
  out[counts < MIN_INDUSTRIES] = np.nan
  return out


def grid(df):
  """Put a table indexed by REF_DATE on the complete monthly grid of its own span."""
  df = df.copy()
  df["REF_DATE"] = pd.to_datetime(df["REF_DATE"])
  df = df.set_index("REF_DATE").sort_index()
  return df.reindex(pd.date_range(df.index.min(), df.index.max(), freq="MS"))


def national_frame():
  """12-month changes of the all-industries series, plus CPI inflation."""
  df = grid(con.execute("""
    SELECT REF_DATE, employment_thousands, job_vacancies,
           real_avg_hourly_wage_cad, avg_hourly_wage_cad, cpi_yoy_pct
    FROM analysis_national_monthly
  """).fetchdf())
  out = pd.DataFrame(index=df.index)
  out["employment_yoy_pct"] = 100.0 * df["employment_thousands"].pct_change(12, fill_method=None)
  out["vacancies_yoy_pct"] = 100.0 * df["job_vacancies"].pct_change(12, fill_method=None)
  out["real_wage_yoy_pct"] = 100.0 * df["real_avg_hourly_wage_cad"].pct_change(12, fill_method=None)
  out["nominal_wage_yoy_pct"] = 100.0 * df["avg_hourly_wage_cad"].pct_change(12, fill_method=None)
  out["cpi_yoy_pct"] = df["cpi_yoy_pct"]
  return out.reindex(MONTHS)


def correlate(series, name, frame):
  """All lagged correlations for one series set: corr(x_t, y_{t+lag})."""
  rows = []
  for link, (xcol, ycol, max_lag) in LINKS.items():
    x = frame[xcol]
    y = frame[ycol]
    for lag in range(max_lag + 1):
      y_lead = y.shift(-lag)
      n = int((x.notna() & y_lead.notna()).sum())
      if n < MIN_PAIRS:
        continue
      rows.append({
        "series": series,
        "industry": name,
        "link": link,
        "lag_months": lag,
        "n_pairs": n,
        "pearson": x.corr(y_lead, method="pearson"),
        "spearman": spearman(x, y_lead),
      })
  return rows


def link_result(sub, max_lag):
  """Lag 0, best lag, best value and whether the link holds."""
  sub = sub.dropna(subset=["pearson"])
  if sub.empty:
    return None
  lag0 = sub[sub["lag_months"] == 0]
  top = sub.loc[sub["pearson"].idxmax()]
  lag0_value = float(lag0["pearson"].iloc[0]) if not lag0.empty else None
  best_lag = int(top["lag_months"])
  best = float(top["pearson"])
  at_edge = best_lag == max_lag
  holds = (best >= LINK_THRESHOLD and lag0_value is not None
           and lag0_value >= 0 and not at_edge)
  return {"lag0": lag0_value, "best_lag": best_lag, "best": best,
          "edge": at_edge, "holds": holds}


def summarize(long_df, series, name, n_months):
  row = {"series": series, "industry": name, "full_chain_months": n_months}
  holds = {}
  for link, (_, _, max_lag) in LINKS.items():
    sub = long_df[(long_df["series"] == series) & (long_df["industry"] == name)
                  & (long_df["link"] == link)]
    r = link_result(sub, max_lag)
    if r is None:
      row[f"{link}_lag0"] = None
      row[f"{link}_best_lag"] = None
      row[f"{link}_best"] = None
      row[f"{link}_edge"] = None
      holds[link] = None
      continue
    row[f"{link}_lag0"] = round(r["lag0"], 3) if r["lag0"] is not None else None
    row[f"{link}_best_lag"] = r["best_lag"]
    row[f"{link}_best"] = round(r["best"], 3)
    row[f"{link}_edge"] = r["edge"]
    holds[link] = r["holds"]
  a, b = holds.get("emp_to_vac"), holds.get("vac_to_real_wage")
  if a is None or b is None:
    verdict = "insufficient data"
  elif a and b:
    verdict = "chain holds"
  elif a:
    verdict = "breaks at vacancies -> wages"
  elif b:
    verdict = "breaks at employment -> vacancies"
  else:
    verdict = "no link"
  row["verdict"] = verdict
  return row


def cross_section(x_wide, y_wide, lag):
  """Rank correlation across industries within each month, x_t vs y_{t+lag}."""
  y_lead = y_wide.shift(-lag)
  values = []
  for month in x_wide.index:
    pair = pd.concat([x_wide.loc[month], y_lead.loc[month]], axis=1).dropna()
    if len(pair) < MIN_INDUSTRIES:
      continue
    values.append(spearman(pair.iloc[:, 0], pair.iloc[:, 1]))
  return pd.Series(values, dtype=float).dropna()


def pooled(x_dm, y_dm, lag):
  """Pearson over all industry-months of the relative series, x_t vs y_{t+lag}."""
  xs = x_dm.to_numpy(dtype=float).ravel()
  ys = y_dm.shift(-lag).to_numpy(dtype=float).ravel()
  mask = ~(np.isnan(xs) | np.isnan(ys))
  if mask.sum() < MIN_PAIRS:
    return float("nan"), int(mask.sum())
  return float(np.corrcoef(xs[mask], ys[mask])[0, 1]), int(mask.sum())


log("=" * 80)
log("CHAIN v2: employment -> vacancies -> wages")
log("=" * 80)
log(f"   months {FIRST_MONTH[:7]} to {LAST_MONTH[:7]} ({len(MONTHS)}), min pairs {MIN_PAIRS}, "
    f"link threshold {LINK_THRESHOLD}, min industries per month {MIN_INDUSTRIES}")

columns = {r[0] for r in con.execute("DESCRIBE analysis_industry_chain").fetchall()}
if "nominal_wage_yoy_pct" not in columns:
  check("analysis_industry_chain has nominal_wage_yoy_pct", False,
        "rerun 07_01_analysis_base.py first")
  finish()

chain = con.execute("""
  SELECT REF_DATE, naics_harmonized, employment_yoy_pct, vacancies_yoy_pct,
         real_wage_yoy_pct, nominal_wage_yoy_pct, full_chain
  FROM analysis_industry_chain
""").fetchdf()
chain["REF_DATE"] = pd.to_datetime(chain["REF_DATE"])
check("chain table is not empty", len(chain) > 0, f"{len(chain)} rows")

counts = chain.groupby("naics_harmonized")["full_chain"].sum().astype(int)
usable = [n for n in sorted(counts.index) if counts[n] >= MIN_CHAIN_MONTHS]
for n in sorted(counts.index):
  if counts[n] < MIN_CHAIN_MONTHS:
    warn(f"'{n}' skipped: {counts[n]} full-chain months (< {MIN_CHAIN_MONTHS})")
check("enough industries for cross-industry analysis", len(usable) >= MIN_INDUSTRIES,
      f"{len(usable)} usable industries")
if len(usable) < MIN_INDUSTRIES:
  finish()

wide = {}
for var in VARS:
  w = chain[chain["naics_harmonized"].isin(usable)].pivot(
    index="REF_DATE", columns="naics_harmonized", values=var)
  wide[var] = w.reindex(MONTHS)
relative = {var: demean(wide[var]) for var in VARS}

months_ok = int((wide["vacancies_yoy_pct"].notna().sum(axis=1) >= MIN_INDUSTRIES).sum())
check(f"at least {MIN_PAIRS} months have {MIN_INDUSTRIES}+ industries", months_ok >= MIN_PAIRS,
      f"{months_ok} months")

# ----------------------------------------------------------------- part A
all_rows = []
for name in usable:
  raw_frame = pd.DataFrame({var: wide[var][name] for var in VARS})
  rel_frame = pd.DataFrame({var: relative[var][name] for var in VARS})
  all_rows.extend(correlate("raw", name, raw_frame))
  all_rows.extend(correlate("relative", name, rel_frame))

nat = national_frame()
all_rows.extend(correlate("raw", NATIONAL_NAME, nat[VARS]))

long_df = pd.DataFrame(all_rows)
check("time-series correlations computed", not long_df.empty,
      f"{long_df['industry'].nunique() if not long_df.empty else 0} industries/series")
if long_df.empty:
  finish()

summary_rows = []
for name in usable:
  n_chain = int(counts[name])
  summary_rows.append(summarize(long_df, "raw", name, n_chain))
  summary_rows.append(summarize(long_df, "relative", name, n_chain))
summary_rows.append(summarize(long_df, "raw", NATIONAL_NAME, int(nat[VARS].dropna().shape[0])))
summary = pd.DataFrame(summary_rows)

bad = long_df["pearson"].dropna()
check("pearson values within [-1, 1]", bool(((bad >= -1) & (bad <= 1)).all()))
dups = long_df.duplicated(subset=["series", "industry", "link", "lag_months"]).sum()
check("one row per (series, industry, link, lag)", dups == 0, f"{dups} dups" if dups else "")
n_nan = int(long_df["pearson"].isna().sum())
if n_nan:
  warn(f"{n_nan} correlation(s) are NaN (constant series in the window)")

cols = ["industry", "full_chain_months",
        "emp_to_vac_lag0", "emp_to_vac_best_lag", "emp_to_vac_best",
        "vac_to_real_wage_lag0", "vac_to_real_wage_best_lag", "vac_to_real_wage_best",
        "vac_to_nominal_wage_lag0", "vac_to_nominal_wage_best", "verdict"]

for series, text in [("raw", "RAW 12-month changes"),
                     ("relative", "RELATIVE (industry minus cross-industry mean of the month)")]:
  log(f"\n-- A. Time series, {text} --")
  log("   Pearson; lag in months; best = highest over lags 0..6; edge lags are not trusted")
  log(summary[summary["series"] == series][cols].to_string(index=False))

  ind = summary[(summary["series"] == series) & (summary["industry"] != NATIONAL_NAME)]
  log(f"\n   verdict counts ({series}, industries only):")
  for v, c in ind["verdict"].value_counts().items():
    log(f"     {v}: {c}")
  log("   chain holds: " + (", ".join(ind[ind["verdict"] == "chain holds"]["industry"]) or "(none)"))

  for link in ["emp_to_vac", "vac_to_real_wage"]:
    n_lag0_pos = int((ind[f"{link}_lag0"].dropna() > 0).sum())
    n_all = int(ind[f"{link}_lag0"].notna().sum())
    log(f"   {link}: lag-0 correlation positive in {n_lag0_pos} of {n_all} industries")

# ----------------------------------------------------------------- part B
log("\n-- B. Cross-industry, month by month (rank correlation across industries) --")
log("   mean/median over months; share = months with a positive correlation; "
    "pooled = Pearson of relative series over all industry-months")
cs_rows = []
for link, (xcol, ycol, max_lag) in LINKS.items():
  for lag in range(max_lag + 1):
    rho = cross_section(wide[xcol], wide[ycol], lag)
    pooled_r, pooled_n = pooled(relative[xcol], relative[ycol], lag)
    cs_rows.append({
      "link": link,
      "lag_months": lag,
      "n_months": int(len(rho)),
      "mean_rho": float(rho.mean()) if len(rho) else np.nan,
      "median_rho": float(rho.median()) if len(rho) else np.nan,
      "share_positive": float((rho > 0).mean()) if len(rho) else np.nan,
      "pooled_pearson": pooled_r,
      "pooled_n": pooled_n,
    })
cs = pd.DataFrame(cs_rows)
log(cs.round(3).to_string(index=False))

check("cross-section computed for every link", cs["n_months"].min() >= 12,
      f"min months {int(cs['n_months'].min())}")

log("\n   Cross-industry reading (lag 0, and best lag by mean rho):")
for link in LINKS:
  sub = cs[cs["link"] == link].dropna(subset=["mean_rho"])
  if sub.empty:
    continue
  top = sub.loc[sub["mean_rho"].idxmax()]
  at0 = sub[sub["lag_months"] == 0].iloc[0]
  holds = (top["mean_rho"] >= CS_MEAN_THRESHOLD and top["share_positive"] >= CS_SHARE_THRESHOLD)
  log(f"     {link}: lag 0 mean rho {at0['mean_rho']:.3f} (share positive {at0['share_positive']:.2f}); "
      f"best lag {int(top['lag_months'])} mean rho {top['mean_rho']:.3f} "
      f"(share positive {top['share_positive']:.2f}) -> "
      + ("link visible across industries" if holds else "no consistent link across industries"))

# ----------------------------------------------------------------- part C
log("\n-- C. National: is the negative vacancies -> real wage correlation the CPI cycle? --")
pairs = [
  ("vacancies vs real wage", "vacancies_yoy_pct", "real_wage_yoy_pct"),
  ("vacancies vs nominal wage", "vacancies_yoy_pct", "nominal_wage_yoy_pct"),
  ("vacancies vs CPI inflation", "vacancies_yoy_pct", "cpi_yoy_pct"),
  ("real wage vs CPI inflation", "real_wage_yoy_pct", "cpi_yoy_pct"),
  ("nominal wage vs CPI inflation", "nominal_wage_yoy_pct", "cpi_yoy_pct"),
]
for label, a, b in pairs:
  pair = nat[[a, b]].dropna()
  r = float(pair[a].corr(pair[b])) if len(pair) >= MIN_PAIRS else float("nan")
  log(f"   lag 0, {label}: {r:.3f}  (n = {len(pair)})")
log("   If vacancies vs real wage is strongly negative while vacancies vs nominal wage is not,")
log("   and real wage tracks CPI inflation negatively, the sign comes from the CPI cycle.")

# ------------------------------------------------------------------ output
log("\n   Notes: descriptive only. Overlapping 12-month changes, one inflation cycle,")
log("   and best-lag selection mean these numbers are illustrations, not estimates.")

CSV_LONG.write_text(long_df.round(4).to_csv(index=False), encoding="utf-8")
CSV_SUMMARY.write_text(summary.to_csv(index=False), encoding="utf-8")
CSV_CROSS.write_text(cs.round(4).to_csv(index=False), encoding="utf-8")
log(f"\n   written: {CSV_LONG}")
log(f"   written: {CSV_SUMMARY}")
log(f"   written: {CSV_CROSS}")

finish()