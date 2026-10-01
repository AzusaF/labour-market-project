"""
09 — Data Warehouse
00 - RUN ALL
Runs the stage-09 scripts in order (scripts/09_01_*.py ... 09_04_*.py) from the project root.
Stops at the first non-zero exit code.
"""
import subprocess
import sys
import time
from pathlib import Path

steps = sorted(Path("scripts").glob("09_0[1-4]_*.py"))
if not steps:
    sys.exit("No scripts/09_0[1-4]_*.py found. Run from the project root.")

summary = []
for s in steps:
    print(f"\n>>> {s.name}")
    t0 = time.time()
    rc = subprocess.run([sys.executable, str(s)]).returncode
    summary.append((s.name, rc, time.time() - t0))
    if rc != 0:
        break

print("\n" + "=" * 60)
for name, rc, dt in summary:
    print(f"{'OK  ' if rc == 0 else 'FAIL'} {name} ({dt:.1f}s)")
failed = any(rc != 0 for _, rc, _ in summary)
print("PIPELINE " + ("FAILED" if failed else "PASSED"))
sys.exit(1 if failed else 0)
