"""
07 — Analysis
03 - BEVERIDGE CURVE

National Beveridge curve: unemployment rate (x) against job vacancy rate (y),
one point per month, all industries, Canada.

Input (read-only): data/warehouse.duckdb
  analysis_national_monthly   (from 07_01)

What it does:
  - Draws the monthly path (colour = time) with a 3-month moving average line.
  - Fits ln(v) = a + b * ln(u) by least squares (numpy only) and reports
    slope, intercept and R^2. A negative slope is the Beveridge relationship.
  - Reports the fit residual by calendar year. Residuals that rise or fall
    over time mean the curve has shifted outward or inward (changes in
    matching efficiency), as opposed to movement along the curve.
  - Compares the first 12 months with the last 12 months (change in u and v).
  - Reports V/U (vacancies per unemployed person) as the tightness measure
    used later for the wage analysis.

Read the results as descriptive:
  - 60 monthly points from a short window; consecutive months are strongly
    autocorrelated, so the fit is an illustration, not an estimate with a
    reliable standard error. No p-values are reported.
  - The series are not seasonally adjusted, so month-to-month wiggles include
    seasonality. The moving average dampens it; it does not remove it.

Output:
  outputs/07_03_beveridge_report.txt
  outputs/07_03_beveridge_points.csv    monthly points, fitted value, residual
  outputs/07_03_beveridge.png           (skipped with a WARN if matplotlib is missing)
"""
import sys
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

DB = "data/warehouse.duckdb"
OUT = Path("outputs/07_03_beveridge_report.txt")
CSV = Path("outputs/07_03_beveridge_points.csv")
PNG = Path("outputs/07_03_beveridge.png")
OUT.parent.mkdir(exist_ok=True)

N_MONTHS = 60
SMOOTH_MONTHS = 3
WINDOW = 12            # months compared at the start and at the end
BAD_QUALITY = ("E", "F")

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


def fit_loglog(u, v):
  """Least squares for ln(v) = a + b ln(u). Returns a, b, r2."""
  x = np.log(u.to_numpy(dtype=float))
  y = np.log(v.to_numpy(dtype=float))
  b, a = np.polyfit(x, y, 1)
  pred = a + b * x
  ss_res = float(((y - pred) ** 2).sum())
  ss_tot = float(((y - y.mean()) ** 2).sum())
  return float(a), float(b), 1.0 - ss_res / ss_tot


def draw(df, a, b):
  """Scatter path coloured by time, moving average line, fitted curve."""
  try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
  except ImportError:
    warn("matplotlib not installed; figure skipped (pip install matplotlib)")
    return False

  fig, ax = plt.subplots(figsize=(8, 6))

  t = np.arange(len(df))
  ax.plot(df["u_ma"], df["v_ma"], color="grey", linewidth=1, alpha=0.7,
          label=f"{SMOOTH_MONTHS}-month moving average")
  points = ax.scatter(df["u"], df["v"], c=t, cmap="viridis", s=28, zorder=3)

  grid = np.linspace(df["u"].min(), df["u"].max(), 100)
  ax.plot(grid, np.exp(a + b * np.log(grid)), color="crimson", linewidth=1.5,
          label=f"fit: ln v = {a:.2f} + {b:.2f} ln u")

  for label, idx in [("first", 0), ("last", len(df) - 1),
                     ("peak vacancy rate", int(df["v"].idxmax()))]:
    row = df.loc[idx]
    ax.annotate(f"{label}\n{row['REF_DATE']:%Y-%m}", (row["u"], row["v"]),
                textcoords="offset points", xytext=(8, 8), fontsize=8)

  cbar = fig.colorbar(points, ax=ax)
  ticks = np.linspace(0, len(df) - 1, 5).astype(int)
  cbar.set_ticks(ticks)
  cbar.set_ticklabels([f"{df.loc[i, 'REF_DATE']:%Y-%m}" for i in ticks])

  ax.set_xlabel("Unemployment rate (%)")
  ax.set_ylabel("Job vacancy rate (%)")
  ax.set_title("Beveridge curve, Canada, all industries (monthly, not seasonally adjusted)")
  ax.legend(loc="upper right", fontsize=8)
  ax.grid(alpha=0.3)

  fig.tight_layout()
  fig.savefig(PNG, dpi=150)
  plt.close(fig)
  return True


log("=" * 80)
log("BEVERIDGE CURVE")
log("=" * 80)

df = con.execute("""
  SELECT REF_DATE,
         unemployment_rate_pct    AS u,
         job_vacancy_rate_pct     AS v,
         vacancies_per_unemployed AS v_per_u,
         job_vacancies_quality    AS quality
  FROM analysis_national_monthly
  ORDER BY REF_DATE
""").fetchdf()
df["REF_DATE"] = pd.to_datetime(df["REF_DATE"])

# ------------------------------------------------------------------- checks
check(f"{N_MONTHS} monthly points", len(df) == N_MONTHS, f"{len(df)} rows")
check("no NULLs in u, v, V/U", int(df[["u", "v", "v_per_u"]].isna().sum().sum()) == 0)
check("u and v strictly positive (needed for ln)", bool(((df["u"] > 0) & (df["v"] > 0)).all()))

if results.count(False):
  OUT.write_text("\n".join(lines), encoding="utf-8")
  sys.exit(1)

bad = df[df["quality"].isin(BAD_QUALITY)]
if len(bad):
  warn(f"{len(bad)} month(s) with vacancy quality in {BAD_QUALITY}: "
       + ", ".join(f"{d:%Y-%m}" for d in bad["REF_DATE"]))
log("   vacancy quality of the national total: "
    + ", ".join(f"{k} {c}" for k, c in df["quality"].value_counts().sort_index().items()))

# ---------------------------------------------------------------------- fit
a, b, r2 = fit_loglog(df["u"], df["v"])
df["v_fit"] = np.exp(a + b * np.log(df["u"]))
df["resid_ln"] = np.log(df["v"]) - np.log(df["v_fit"])
corr = float(df["u"].corr(df["v"]))

log("\n-- Fit: ln(v) = a + b * ln(u) --")
log(f"   a = {a:.3f}   b = {b:.3f}   R^2 = {r2:.3f}   n = {len(df)}")
log(f"   Pearson corr(u, v) = {corr:.3f}")
if b >= 0:
  warn("slope is not negative: the points do not show a Beveridge relationship in this window")
else:
  log("   slope is negative: higher unemployment goes with fewer vacancies")

# --------------------------------------------------------------- over time
log("\n-- Residual by calendar year (mean of ln v - fitted ln v) --")
log("   positive = more vacancies than the curve implies (curve shifted outward)")
df["year"] = df["REF_DATE"].dt.year
by_year = df.groupby("year").agg(
  months=("u", "size"), mean_u=("u", "mean"), mean_v=("v", "mean"),
  mean_v_per_u=("v_per_u", "mean"), mean_resid_ln=("resid_ln", "mean"),
).round(3)
log(by_year.to_string())

first = df.head(WINDOW)
last = df.tail(WINDOW)
du = float(last["u"].mean() - first["u"].mean())
dv = float(last["v"].mean() - first["v"].mean())
log(f"\n-- First {WINDOW} months vs last {WINDOW} months --")
log(f"   unemployment rate: {first['u'].mean():.2f} -> {last['u'].mean():.2f}  ({du:+.2f} pp)")
log(f"   job vacancy rate : {first['v'].mean():.2f} -> {last['v'].mean():.2f}  ({dv:+.2f} pp)")
if du * dv < 0:
  movement = "u and v moved in opposite directions: movement along the curve"
elif du > 0 and dv > 0:
  movement = "u and v both rose: outward shift (or a move along a shifted curve)"
else:
  movement = "u and v both fell: inward shift (or a move along a shifted curve)"
log(f"   reading: {movement}")

peak = df.loc[df["v"].idxmax()]
trough = df.loc[df["v"].idxmin()]
log(f"\n   peak vacancy rate  : {peak['v']:.2f}% in {peak['REF_DATE']:%Y-%m} (u = {peak['u']:.2f}%)")
log(f"   lowest vacancy rate: {trough['v']:.2f}% in {trough['REF_DATE']:%Y-%m} (u = {trough['u']:.2f}%)")
log(f"   V/U range: {df['v_per_u'].min():.3f} to {df['v_per_u'].max():.3f}")

# ------------------------------------------------------------------- output
df["u_ma"] = df["u"].rolling(SMOOTH_MONTHS, min_periods=1).mean()
df["v_ma"] = df["v"].rolling(SMOOTH_MONTHS, min_periods=1).mean()

out = df[["REF_DATE", "u", "v", "v_per_u", "v_fit", "resid_ln", "u_ma", "v_ma", "quality"]].copy()
out["REF_DATE"] = out["REF_DATE"].dt.strftime("%Y-%m")
CSV.write_text(out.round(4).to_csv(index=False), encoding="utf-8")
log(f"\n   written: {CSV}")

if draw(df, a, b):
  log(f"   written: {PNG}")

log("\n   Notes: descriptive only. Short window, autocorrelated months, no seasonal adjustment.")

# ---------------------------------------------------------------------- result
log("\n" + "=" * 80)
log("BEVERIDGE RESULT")
log("=" * 80)
fails = results.count(False)
log(f"Checks: {len(results)} | Passed: {results.count(True)} | Failed: {fails} | Warnings: {len(warns)}")
log("Status: " + ("PASSED" if fails == 0 else "FAILED"))

OUT.write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if fails == 0 else 1)