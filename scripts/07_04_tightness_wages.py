"""
07 — Analysis
04 - TIGHTNESS, CPI AND WAGES

Asks what moves nominal wage growth in 2022-2025: labour market tightness
(vacancies per unemployed person, vacancy rate, unemployment rate) or
inflation (CPI pass-through).

Input (read-only): data/warehouse.duckdb
  analysis_national_monthly   Canada x month, all industries (from 07_01)
  analysis_industry_chain     Canada x harmonized industry x month (from 07_01)

Why nominal wages:
  07_02 showed that real wage growth is mostly the mirror image of CPI
  inflation in this window (correlation about -0.9). Nominal wage growth is
  the outcome to explain; CPI is then tested as one of the drivers.

Parts:
  A. National, Phillips-type. Nominal wage growth (12-month % change) in month
     t+lag against tightness in month t, lags 0..6, for V/U, vacancy rate and
     unemployment rate (Pearson and Spearman). Then a small regression with
     standardized variables:
         wage_{t+lag} ~ CPI inflation_t + V/U_t     (and CPI inflation alone,
         on the same rows) so R^2 shows what tightness adds beyond CPI.
  B. CPI pass-through. Slope of nominal wage growth_{t+lag} on CPI inflation_t
     (percentage points of wage growth per point of inflation), lags 0..6:
     national, each industry, and pooled within industries. A slope below 1
     means wages rise less than prices (real wages fall when inflation rises).
  C. Cross-industry tightness. Month by month, rank correlation across
     industries between the industry vacancy rate (level) in month t and
     nominal wage growth in month t+lag. CPI is common to all industries, so
     it cancels out of this comparison.

Read the results as descriptive, not causal:
  - 12-month changes overlap, so the effective sample is far smaller than the
    number of rows. No p-values or standard errors are reported.
  - One inflation cycle in four years. CPI inflation and tightness are
    correlated with each other, so their separate effects are hard to tell
    apart; the collinearity is printed.
  - The tightness series are not seasonally adjusted.
  - National only; vacancies exist for Canada only.

Output:
  outputs/07_04_tightness_wages_report.txt
  outputs/07_04_national_lags.csv
  outputs/07_04_passthrough.csv
  outputs/07_04_tightness_cross_section.csv
  outputs/07_04_tightness_wages.png   (skipped with a WARN if matplotlib is missing)
"""
import sys
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

DB = "data/warehouse.duckdb"
OUT = Path("outputs/07_04_tightness_wages_report.txt")
CSV_NATIONAL = Path("outputs/07_04_national_lags.csv")
CSV_PASS = Path("outputs/07_04_passthrough.csv")
CSV_CROSS = Path("outputs/07_04_tightness_cross_section.csv")
PNG = Path("outputs/07_04_tightness_wages.png")
OUT.parent.mkdir(exist_ok=True)

FIRST_MONTH = "2022-01-01"
LAST_MONTH = "2025-12-01"
MONTHS = pd.date_range(FIRST_MONTH, LAST_MONTH, freq="MS")

MAX_LAG = 6
MIN_PAIRS = 24
MIN_CHAIN_MONTHS = 24     # same cutoff as 07_01
MIN_INDUSTRIES = 8
CS_MEAN_THRESHOLD = 0.2   # part C: clear link
WEAK_MEAN = 0.1           # part C: weak but consistent
CS_SHARE_THRESHOLD = 0.6
COLLINEARITY_WARN = 0.6
NATIONAL_NAME = "ALL INDUSTRIES (national)"

WAGE = "nominal_wage_yoy_pct"
TIGHT_VARS = [
  ("vacancies_per_unemployed", "V/U"),
  ("job_vacancy_rate_pct", "vacancy rate"),
  ("unemployment_rate_pct", "unemployment rate"),
]

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
  log("TIGHTNESS, CPI AND WAGES RESULT")
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


def slope_r2(x, y):
  """Simple OLS slope of y on x (raw units) and R^2, on complete pairs."""
  pair = pd.concat([x, y], axis=1).dropna()
  n = len(pair)
  if n < MIN_PAIRS:
    return None
  xs = pair.iloc[:, 0].to_numpy(dtype=float)
  ys = pair.iloc[:, 1].to_numpy(dtype=float)
  var = ((xs - xs.mean()) ** 2).sum()
  if var == 0:
    return None
  slope = float(((xs - xs.mean()) * (ys - ys.mean())).sum() / var)
  r = float(np.corrcoef(xs, ys)[0, 1])
  return {"slope": slope, "corr": r, "r2": r * r, "n": n}


def fit_standardized(data, y, xs):
  """OLS on z-scored columns (no intercept needed). Returns betas by name and R^2."""
  z = (data - data.mean()) / data.std(ddof=0)
  Y = z[y].to_numpy(dtype=float)
  X = z[xs].to_numpy(dtype=float)
  beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
  resid = Y - X @ beta
  r2 = 1.0 - float((resid ** 2).sum()) / float((Y ** 2).sum())
  return dict(zip(xs, [float(b) for b in beta])), r2


def reading(mean, share):
  if mean >= CS_MEAN_THRESHOLD and share >= CS_SHARE_THRESHOLD:
    return "clear positive link across industries"
  if mean <= -CS_MEAN_THRESHOLD and share <= 1 - CS_SHARE_THRESHOLD:
    return "clear negative link across industries"
  if mean >= WEAK_MEAN and share >= CS_SHARE_THRESHOLD:
    return "weak but consistent positive link"
  if mean <= -WEAK_MEAN and share <= 1 - CS_SHARE_THRESHOLD:
    return "weak but consistent negative link"
  return "no consistent link"


def grid(df):
  df = df.copy()
  df["REF_DATE"] = pd.to_datetime(df["REF_DATE"])
  df = df.set_index("REF_DATE").sort_index()
  return df.reindex(pd.date_range(df.index.min(), df.index.max(), freq="MS"))


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


def pooled_within_slope(wage_wide, cpi, lag):
  """Pass-through slope after removing each industry's own mean (within estimator)."""
  y = wage_wide.shift(-lag)
  x = pd.DataFrame({c: cpi for c in wage_wide.columns})
  valid = y.notna() & x.notna()
  y = y.where(valid)
  x = x.where(valid)
  n = int(valid.to_numpy().sum())
  if n < MIN_PAIRS:
    return None
  yd = (y - y.mean()).to_numpy(dtype=float)
  xd = (x - x.mean()).to_numpy(dtype=float)
  mask = ~(np.isnan(xd) | np.isnan(yd))
  denom = float((xd[mask] ** 2).sum())
  if denom == 0:
    return None
  return {"slope": float((xd[mask] * yd[mask]).sum() / denom), "n": n}


log("=" * 80)
log("TIGHTNESS, CPI AND WAGES")
log("=" * 80)
log(f"   months {FIRST_MONTH[:7]} to {LAST_MONTH[:7]} ({len(MONTHS)}), lags 0..{MAX_LAG}, "
    f"min pairs {MIN_PAIRS}")

columns = {r[0] for r in con.execute("DESCRIBE analysis_industry_chain").fetchall()}
if WAGE not in columns:
  check("analysis_industry_chain has nominal_wage_yoy_pct", False,
        "rerun 07_01_analysis_base.py first")
  finish()

# ------------------------------------------------------------ national frame
raw = grid(con.execute("""
  SELECT REF_DATE, avg_hourly_wage_cad, vacancies_per_unemployed,
         job_vacancy_rate_pct, unemployment_rate_pct, cpi_yoy_pct
  FROM analysis_national_monthly
""").fetchdf())
nat = pd.DataFrame(index=raw.index)
nat[WAGE] = 100.0 * raw["avg_hourly_wage_cad"].pct_change(12, fill_method=None)
nat["cpi_yoy_pct"] = raw["cpi_yoy_pct"]
for var, _ in TIGHT_VARS:
  nat[var] = raw[var]
nat = nat.reindex(MONTHS)

check("national frame covers every month", len(nat) == len(MONTHS), f"{len(nat)} months")
check("national wage growth, CPI inflation and V/U present every month",
      int(nat[[WAGE, "cpi_yoy_pct", "vacancies_per_unemployed"]].isna().sum().sum()) == 0)

collinearity = float(nat["vacancies_per_unemployed"].corr(nat["cpi_yoy_pct"]))
log(f"   corr(V/U, CPI inflation) at lag 0: {collinearity:.3f}")
if abs(collinearity) >= COLLINEARITY_WARN:
  warn(f"V/U and CPI inflation are strongly correlated ({collinearity:.2f}); "
       "their separate effects on wages cannot be reliably separated")

# ---------------------------------------------------------------------- A
log("\n-- A. National: tightness_t vs nominal wage growth_{t+lag} --")
rows = []
for var, label in TIGHT_VARS:
  for lag in range(MAX_LAG + 1):
    y = nat[WAGE].shift(-lag)
    x = nat[var]
    n = int((x.notna() & y.notna()).sum())
    if n < MIN_PAIRS:
      continue
    rows.append({"measure": label, "lag_months": lag, "n_pairs": n,
                 "pearson": x.corr(y), "spearman": spearman(x, y)})
lags_df = pd.DataFrame(rows)
check("national lag correlations computed", not lags_df.empty, f"{len(lags_df)} rows")
if lags_df.empty:
  finish()
bad = lags_df["pearson"].dropna()
check("pearson values within [-1, 1]", bool(((bad >= -1) & (bad <= 1)).all()))
log(lags_df.round(3).to_string(index=False))

log("\n   Regression on standardized variables (coefficients are in standard deviations):")
log("   wage_{t+lag} ~ CPI inflation_t + V/U_t  vs  CPI inflation_t alone, same rows")
reg_rows = []
for lag in range(MAX_LAG + 1):
  data = pd.DataFrame({
    "wage": nat[WAGE].shift(-lag),
    "cpi": nat["cpi_yoy_pct"],
    "tight": nat["vacancies_per_unemployed"],
  }).dropna()
  if len(data) < MIN_PAIRS:
    continue
  both, r2_both = fit_standardized(data, "wage", ["cpi", "tight"])
  only, r2_cpi = fit_standardized(data, "wage", ["cpi"])
  reg_rows.append({
    "lag_months": lag, "n": len(data),
    "beta_cpi_with_tight": both["cpi"], "beta_tight": both["tight"],
    "r2_cpi_and_tight": r2_both, "beta_cpi_alone": only["cpi"],
    "r2_cpi_alone": r2_cpi, "r2_added_by_tight": r2_both - r2_cpi,
  })
reg = pd.DataFrame(reg_rows)
log(reg.round(3).to_string(index=False))
if not reg.empty:
  best = reg.loc[reg["r2_added_by_tight"].idxmax()]
  log(f"   largest R^2 added by V/U: {best['r2_added_by_tight']:.3f} at lag {int(best['lag_months'])} "
      f"(CPI alone R^2 {best['r2_cpi_alone']:.3f})")

# ---------------------------------------------------------------------- B
log("\n-- B. CPI pass-through: slope of nominal wage growth_{t+lag} on CPI inflation_t --")
log("   slope = percentage points of wage growth per 1 point of inflation; 1.0 = full pass-through")

chain = con.execute(f"""
  SELECT REF_DATE, naics_harmonized, {WAGE}, job_vacancy_rate_pct, full_chain
  FROM analysis_industry_chain
""").fetchdf()
chain["REF_DATE"] = pd.to_datetime(chain["REF_DATE"])
check("industry chain table is not empty", len(chain) > 0, f"{len(chain)} rows")

counts = chain.groupby("naics_harmonized")["full_chain"].sum().astype(int)
usable = [n for n in sorted(counts.index) if counts[n] >= MIN_CHAIN_MONTHS]
for n in sorted(counts.index):
  if counts[n] < MIN_CHAIN_MONTHS:
    warn(f"'{n}' skipped: {counts[n]} full-chain months (< {MIN_CHAIN_MONTHS})")
check("enough industries for cross-industry analysis", len(usable) >= MIN_INDUSTRIES,
      f"{len(usable)} usable industries")
if len(usable) < MIN_INDUSTRIES:
  finish()

sub = chain[chain["naics_harmonized"].isin(usable)]
wage_wide = sub.pivot(index="REF_DATE", columns="naics_harmonized", values=WAGE).reindex(MONTHS)
vac_wide = sub.pivot(index="REF_DATE", columns="naics_harmonized",
                     values="job_vacancy_rate_pct").reindex(MONTHS)
cpi = nat["cpi_yoy_pct"]

pass_rows = []


def add_series(name, wage_series):
  for lag in range(MAX_LAG + 1):
    r = slope_r2(cpi, wage_series.shift(-lag))
    if r is not None:
      pass_rows.append({"series": name, "lag_months": lag, "slope": r["slope"],
                        "corr": r["corr"], "r2": r["r2"], "n": r["n"]})


add_series(NATIONAL_NAME, nat[WAGE])
for name in usable:
  add_series(name, wage_wide[name])
for lag in range(MAX_LAG + 1):
  r = pooled_within_slope(wage_wide, cpi, lag)
  if r is not None:
    pass_rows.append({"series": "POOLED within industries", "lag_months": lag,
                      "slope": r["slope"], "corr": np.nan, "r2": np.nan, "n": r["n"]})

passdf = pd.DataFrame(pass_rows)
check("pass-through computed", not passdf.empty, f"{passdf['series'].nunique() if not passdf.empty else 0} series")
if passdf.empty:
  finish()

summary_rows = []
for name, g in passdf.groupby("series"):
  g = g.sort_values("lag_months")
  lag0 = g[g["lag_months"] == 0]
  if g["corr"].notna().any():
    top = g.loc[g["corr"].idxmax()]
  else:
    top = g.loc[g["slope"].idxmax()]
  summary_rows.append({
    "series": name,
    "lag0_slope": float(lag0["slope"].iloc[0]) if not lag0.empty else np.nan,
    "lag0_corr": float(lag0["corr"].iloc[0]) if not lag0.empty else np.nan,
    "best_lag": int(top["lag_months"]),
    "best_slope": float(top["slope"]),
    "best_corr": float(top["corr"]),
    "best_lag_at_edge": int(top["lag_months"]) == MAX_LAG,
  })
pass_summary = pd.DataFrame(summary_rows)
order = [NATIONAL_NAME] + usable + ["POOLED within industries"]
pass_summary["order"] = pass_summary["series"].map({n: i for i, n in enumerate(order)})
pass_summary = pass_summary.sort_values("order").drop(columns="order")
log(pass_summary.round(3).to_string(index=False))

ind = pass_summary[pass_summary["series"].isin(usable)]
log(f"\n   industries, lag 0: median slope {ind['lag0_slope'].median():.2f}, "
    f"range {ind['lag0_slope'].min():.2f} to {ind['lag0_slope'].max():.2f}")
log(f"   slope > 0 in {int((ind['lag0_slope'] > 0).sum())} of {len(ind)}; "
    f"slope < 1 in {int((ind['lag0_slope'] < 1).sum())} of {len(ind)}")
n_edge = int(ind["best_lag_at_edge"].sum())
if n_edge:
  warn(f"{n_edge} industries have their best lag at the edge (lag {MAX_LAG}); "
       "the peak may lie outside the tested range")

# ---------------------------------------------------------------------- C
log("\n-- C. Cross-industry: industry vacancy rate_t vs nominal wage growth_{t+lag} --")
log("   rank correlation across industries within each month; CPI cancels out")
cs_rows = []
for lag in range(MAX_LAG + 1):
  rho = cross_section(vac_wide, wage_wide, lag)
  cs_rows.append({
    "lag_months": lag,
    "n_months": int(len(rho)),
    "mean_rho": float(rho.mean()) if len(rho) else np.nan,
    "median_rho": float(rho.median()) if len(rho) else np.nan,
    "share_positive": float((rho > 0).mean()) if len(rho) else np.nan,
  })
cs = pd.DataFrame(cs_rows)
log(cs.round(3).to_string(index=False))
check("cross-section computed for every lag", cs["n_months"].min() >= 12,
      f"min months {int(cs['n_months'].min())}")

valid = cs.dropna(subset=["mean_rho"])
if not valid.empty:
  at0 = valid[valid["lag_months"] == 0].iloc[0]
  top = valid.loc[valid["mean_rho"].idxmax()]
  log(f"\n   lag 0: mean rho {at0['mean_rho']:.3f}, share positive {at0['share_positive']:.2f} -> "
      + reading(at0["mean_rho"], at0["share_positive"]))
  log(f"   best lag {int(top['lag_months'])}: mean rho {top['mean_rho']:.3f}, "
      f"share positive {top['share_positive']:.2f} -> "
      + reading(top["mean_rho"], top["share_positive"]))

# ------------------------------------------------------------------ figure


def draw():
  try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
  except ImportError:
    warn("matplotlib not installed; figure skipped (pip install matplotlib)")
    return False

  fig, axes = plt.subplots(1, 2, figsize=(13, 5))

  ax = axes[0]
  ax.plot(nat.index, nat[WAGE], color="tab:blue", label="Nominal wage growth (12m %)")
  ax.plot(nat.index, nat["cpi_yoy_pct"], color="tab:red", label="CPI inflation (12m %)")
  ax.set_ylabel("%")
  ax.grid(alpha=0.3)
  ax2 = ax.twinx()
  ax2.plot(nat.index, nat["vacancies_per_unemployed"], color="tab:green",
           linestyle="--", label="V/U (right axis)")
  ax2.set_ylabel("Vacancies per unemployed")
  h1, l1 = ax.get_legend_handles_labels()
  h2, l2 = ax2.get_legend_handles_labels()
  ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)
  ax.set_title("Wage growth, inflation and tightness (Canada, all industries)")

  ax = axes[1]
  t = np.arange(len(nat))
  sc = ax.scatter(nat["vacancies_per_unemployed"], nat[WAGE], c=t, cmap="viridis", s=28)
  ax.set_xlabel("Vacancies per unemployed (V/U)")
  ax.set_ylabel("Nominal wage growth (12m %)")
  ax.set_title("Tightness vs wage growth, lag 0")
  ax.grid(alpha=0.3)
  cbar = fig.colorbar(sc, ax=ax)
  ticks = np.linspace(0, len(nat) - 1, 5).astype(int)
  cbar.set_ticks(ticks)
  cbar.set_ticklabels([f"{nat.index[i]:%Y-%m}" for i in ticks])

  fig.tight_layout()
  fig.savefig(PNG, dpi=150)
  plt.close(fig)
  return True


# ------------------------------------------------------------------ output
log("\n   Notes: descriptive only. Overlapping 12-month changes, one inflation cycle,")
log("   collinear drivers and non-seasonally-adjusted tightness series.")

national_out = lags_df.merge(
  reg.add_prefix("reg_").rename(columns={"reg_lag_months": "lag_months"}),
  on="lag_months", how="left")
CSV_NATIONAL.write_text(national_out.round(4).to_csv(index=False), encoding="utf-8")
CSV_PASS.write_text(passdf.round(4).to_csv(index=False), encoding="utf-8")
CSV_CROSS.write_text(cs.round(4).to_csv(index=False), encoding="utf-8")
log(f"\n   written: {CSV_NATIONAL}")
log(f"   written: {CSV_PASS}")
log(f"   written: {CSV_CROSS}")
if draw():
  log(f"   written: {PNG}")

finish()