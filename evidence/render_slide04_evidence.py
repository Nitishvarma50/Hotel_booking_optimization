"""Create a source-and-output evidence image for Data Lead slide 4."""

import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
command = [sys.executable, str(ROOT / "evidence" / "slide04_column_audit.py")]
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
source = (ROOT / "evidence" / "slide04_column_audit.py").read_text(encoding="utf-8")
source_lines = source.splitlines()
code = "\n".join(f"{i + 1:>3} {line}" for i, line in enumerate(source_lines))

fig, axes = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2.1, 0.85]})
fig.patch.set_facecolor("#0b1220")
for ax in axes:
    ax.set_facecolor("#111827")
    ax.axis("off")
axes[0].set_title("SOURCE · evidence/slide04_column_audit.py", color="#93c5fd", loc="left", fontsize=13, pad=8)
axes[0].text(0.02, 0.98, code, va="top", ha="left", family="monospace", fontsize=8.6,
             color="#e5e7eb", linespacing=1.28, transform=axes[0].transAxes)
axes[1].set_title("OUTPUT · python evidence/slide04_column_audit.py", color="#86efac", loc="left", fontsize=13, pad=8)
axes[1].text(0.02, 0.95, result.stdout.strip(), va="top", ha="left", family="monospace", fontsize=12,
             color="#f9fafb", linespacing=1.8, transform=axes[1].transAxes)
fig.suptitle("Slide 4 evidence · feature timing audit", color="white", fontsize=18, x=0.05, ha="left")
fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.93])
out = ROOT / "evidence" / "slide04_column_timing.png"
fig.savefig(out, dpi=170, facecolor=fig.get_facecolor(), bbox_inches="tight")
print(out)
