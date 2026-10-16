"""
07 — Analysis
02 - CHAIN

Tests, industry by industry, whether the chain
    employment growth -> job vacancy growth -> real wage growth
shows up in the data.

Input (read-only): data/warehouse.duckdb
  analysis_industry_chain   Canada x harmonized industry x month (from 07_01)
  analysis_national_monthly Canada x month, all industries (from 07_01)

Method:
  - Variables are 12-month % changes (employment_yoy_pct, vacancies_yoy_pct,
    real_wage_yoy_pct). They are available from 2022-01 to 2025-12.
  - Each industry is placed on the full monthly grid first, so a lag is always
    a calendar lag even when a month is missing.
  - Lagged correlation: corr(x_t, y_{t+lag}). Three links:
      emp_to_vac   lags 0..6   employment change leads vacancy change
      vac_to_wage  lags 0..12  vacancy change leads real wage change
      emp_to_wage  lags 0..12  employment change leads real wage change
  - Pearson and Spearman are both reported. Pairs with fewer than MIN_PAIRS
    observations are not computed.
  - A link "holds" when its best-lag Pearson correlation is >= LINK_THRESHOLD.
    The chain holds when emp_to_vac and vac_to_wage both hold.

Read the results as descriptive, not causal:
  - 12-month changes overlap, so neighbouring months are strongly
    autocorrelated and the effective sample is much smaller than the row
    count. No p-values are reported for that reason.
  - Taking the best of several lags is optimistic; lag 0 is shown next to it.
  - Provinces are not used. Vacancies exist for Canada only.

Output:
  outputs/07_02_chain_report.txt
  outputs/07_02_chain_correlations.csv   every (industry, link, lag)
  outputs/07_02_chain_summary.csv        one row per industry
"""
import sys
from pathlib import Path
import duckdb
import pandas as pd

DB = "data/warehouse.duckdb"
OUT = Path("outputs/07_02_chain_report.txt")
CSV_LONG = Path("outputs/07_02_chain_correlations.csv")
CSV_SUMMARY = Path("outputs/07_02_chain_summary.csv")
OUT.parent.mkdir(exist_ok=True)

FIRST_MONTH = "2022-01-01"
LAST_MONTH = "2025-12-01"
MONTHS = pd.date_range(FIRST_MONTH, LAST_MONTH, freq="MS")

MIN_PAIRS = 24
LINK_THRESHOLD = 0.3
MIN_CHAIN_MONTHS = 24   # same cutoff as 07_01
NATIONAL_NAME = "ALL INDUSTRIES (national)"

# (link name, x column, y column, max lag in months)
LINKS = [
  ("emp_to_vac", "employment_yoy_pct", "vacancies_yoy_pct", 6),
  ("vac_to_wage", "vacancies_yoy_pct", "real_wage_yoy_pct", 12),
  ("emp_to_wage", "employment_yoy_pct", "real_wage_yoy_pct", 12),
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


def on_full_grid(frame):
  """Index one series set by month on the complete monthly grid."""
  frame = frame.copy()
  frame["REF_DATE"] = pd.to_datetime(frame["REF_DATE"])
  return frame.set_index("REF_DATE").reindex(MONTHS)


def national_frame():
  """12-month changes of the all-industries series (reference row)."""
  df = con.execute("""
    SELECT REF_DATE, employment_thousands, job_vacancies,
           real_avg_hourly_wage_cad
    FROM analysis_national_monthly
  """).fetchdf()
  df = on_full_grid_all(df)
  out = pd.DataFrame(index=df.index)
  out["employment_yoy_pct"] = 100.0 * df["employment_thousands"].pct_change(12, fill_method=None)
  out["vacancies_yoy_pct"] = 100.0 * df["job_vacancies"].pct_change(12, fill_method=None)
  out["real_wage_yoy_pct"] = 100.0 * df["real_avg_hourly_wage_cad"].pct_change(12, fill_method=None)
  return out.reindex(MONTHS)


def on_full_grid_all(df):
  """Full grid from the first source month, so pct_change(12) is a calendar change."""
  df = df.copy()
  df["REF_DATE"] = pd.to_datetime(df["REF_DATE"])
  df = df.set_index("REF_DATE").sort_index()
  grid = pd.date_range(df.index.min(), df.index.max(), freq="MS")
  return df.reindex(grid)


def spearman(x, y):
  """Spearman = Pearson on ranks of the complete pairs (pandas needs scipy for method='spearman')."""
  pair = pd.concat([x, y], axis=1).dropna()
  if len(pair) < 2:
    return float("nan")
  return pair.iloc[:, 0].rank().corr(pair.iloc[:, 1].rank())


def correlate(name, frame):
  """All lagged correlations for one industry."""
  rows = []
  for link, xcol, ycol, max_lag in LINKS:
    x = frame[xcol]
    y = frame[ycol]
    for lag in range(max_lag + 1):
      y_lead = y.shift(-lag)
      n = int((x.notna() & y_lead.notna()).sum())
      if n < MIN_PAIRS:
        continue
      rows.append({
        "industry": name,
        "link": link,
        "lag_months": lag,
        "n_pairs": n,
        "pearson": x.corr(y_lead, method="pearson"),
        "spearman": spearman(x, y_lead),
      })
  return rows


def verdict(emp_vac, vac_wage):
  if emp_vac is None or vac_wage is None:
    return "insufficient data"
  a = emp_vac >= LINK_THRESHOLD
  b = vac_wage >= LINK_THRESHOLD
  if a and b:
    return "chain holds"
  if a:
    return "breaks at vacancies -> wages"
  if b:
    return "breaks at employment -> vacancies"
  return "no link"


def summarize(long_df, name, n_chain_months):
  """One summary row per industry from the long table."""
  row = {"industry": name, "full_chain_months": n_chain_months}
  best = {}
  for link, _, _, _ in LINKS:
    sub = long_df[(long_df["industry"] == name) & (long_df["link"] == link)]
    sub = sub.dropna(subset=["pearson"])
    if sub.empty:
      row[f"{link}_lag0"] = None
      row[f"{link}_best_lag"] = None
      row[f"{link}_best"] = None
      best[link] = None
      continue
    lag0 = sub[sub["lag_months"] == 0]
    top = sub.loc[sub["pearson"].idxmax()]
    row[f"{link}_lag0"] = round(float(lag0["pearson"].iloc[0]), 3) if not lag0.empty else None
    row[f"{link}_best_lag"] = int(top["lag_months"])
    row[f"{link}_best"] = round(float(top["pearson"]), 3)
    best[link] = float(top["pearson"])
  row["verdict"] = verdict(best.get("emp_to_vac"), best.get("vac_to_wage"))
  return row


log("=" * 80)
log("CHAIN: employment -> vacancies -> real wages")
log("=" * 80)
log(f"   months {FIRST_MONTH[:7]} to {LAST_MONTH[:7]} ({len(MONTHS)}), "
    f"min pairs {MIN_PAIRS}, link threshold {LINK_THRESHOLD}")

chain = con.execute("""
  SELECT REF_DATE, naics_harmonized,
         employment_yoy_pct, vacancies_yoy_pct, real_wage_yoy_pct, full_chain
  FROM analysis_industry_chain
""").fetchdf()
check("chain table is not empty", len(chain) > 0, f"{len(chain)} rows")

all_rows = []
summary_rows = []
skipped = []

counts = chain.groupby("naics_harmonized")["full_chain"].sum().astype(int)

for name in sorted(chain["naics_harmonized"].unique()):
  n_chain = int(counts[name])
  if n_chain < MIN_CHAIN_MONTHS:
    skipped.append((name, n_chain))
    continue
  sub = chain[chain["naics_harmonized"] == name]
  frame = on_full_grid(sub[["REF_DATE", "employment_yoy_pct",
                            "vacancies_yoy_pct", "real_wage_yoy_pct"]])
  rows = correlate(name, frame)
  all_rows.extend(rows)

for name, n_chain in skipped:
  warn(f"'{name}' skipped: {n_chain} full-chain months (< {MIN_CHAIN_MONTHS})")

# national reference row
nat = national_frame()
all_rows.extend(correlate(NATIONAL_NAME, nat))
n_nat = int(nat.dropna().shape[0])

long_df = pd.DataFrame(all_rows)
check("correlations computed for at least one industry", not long_df.empty,
      f"{long_df['industry'].nunique() if not long_df.empty else 0} series")

if long_df.empty:
  OUT.write_text("\n".join(lines), encoding="utf-8")
  sys.exit(1)

for name in sorted(long_df["industry"].unique()):
  n_chain = n_nat if name == NATIONAL_NAME else int(counts[name])
  summary_rows.append(summarize(long_df, name, n_chain))

summary = pd.DataFrame(summary_rows)

# ------------------------------------------------------------------- checks
bad = long_df["pearson"].dropna()
check("pearson values within [-1, 1]", bool(((bad >= -1) & (bad <= 1)).all()))

dups = long_df.duplicated(subset=["industry", "link", "lag_months"]).sum()
check("one row per (industry, link, lag)", dups == 0, f"{dups} dups" if dups else "")

check("national reference row present", NATIONAL_NAME in set(long_df["industry"]))

n_nan = int(long_df["pearson"].isna().sum())
if n_nan:
  warn(f"{n_nan} correlation(s) are NaN (constant series in the window)")

# ------------------------------------------------------------------- output
log("\n-- Summary (Pearson; lag in months; best = highest over the lag range) --")
cols = ["industry", "full_chain_months",
        "emp_to_vac_lag0", "emp_to_vac_best_lag", "emp_to_vac_best",
        "vac_to_wage_lag0", "vac_to_wage_best_lag", "vac_to_wage_best",
        "emp_to_wage_best_lag", "emp_to_wage_best", "verdict"]
log(summary[cols].to_string(index=False))

log("\n-- Verdict counts (industries only, national row excluded) --")
ind_only = summary[summary["industry"] != NATIONAL_NAME]
for v, c in ind_only["verdict"].value_counts().items():
  log(f"   {v}: {c}")

log("\n-- Industries where the chain holds --")
holds = ind_only[ind_only["verdict"] == "chain holds"]["industry"].tolist()
for h in holds or ["(none)"]:
  log(f"   {h}")

log("\n   Notes: descriptive only. 12-month changes overlap, so the effective")
log("   sample is far below the number of pairs; best-lag selection is optimistic.")

CSV_LONG.write_text(long_df.round(4).to_csv(index=False), encoding="utf-8")
CSV_SUMMARY.write_text(summary.to_csv(index=False), encoding="utf-8")
log(f"\n   written: {CSV_LONG}")
log(f"   written: {CSV_SUMMARY}")

# ---------------------------------------------------------------------- result
log("\n" + "=" * 80)
log("CHAIN RESULT")
log("=" * 80)
fails = results.count(False)
log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails} | Warnings: {len(warns)}")
log("Status: " + ("PASSED" if fails == 0 else "FAILED"))

OUT.write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if fails == 0 else 1)