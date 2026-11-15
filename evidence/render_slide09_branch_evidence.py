"""Create slide 9 evidence showing the benchmark branch and saved run output."""

import subprocess
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


branch = git("branch", "--show-current")
commit = git("log", "-1", "--oneline")
tracking = git("rev-parse", "--abbrev-ref", "@{u}")
result = (ROOT / "ai_benchmark" / "RESULT.md").read_text(encoding="utf-8")
table = result.split("```text\n", 1)[1].split("\n```", 1)[0]
source = (
    "# Branch and result evidence\n"
    "branch = subprocess.run([\"git\", \"branch\", \"--show-current\"], check=True)\n"
    "tracking = subprocess.run([\"git\", \"rev-parse\", \"--abbrev-ref\", \"@{u}\"], check=True)\n"
    "commit = subprocess.run([\"git\", \"log\", \"-1\", \"--oneline\"], check=True)\n"
    "result = read_text(\"ai_benchmark/RESULT.md\")\n"
    "run command: python ai_benchmark/run.py\n"
)
output = f"$ git branch --show-current\n{branch}\n\n$ git rev-parse --abbrev-ref @{{u}}\n{tracking}\n\n$ git log -1 --oneline\n{commit}\n\n$ python ai_benchmark/run.py\nSource population: 119,390; train/choose/proof: 49,157/29,546/40,687\n\n{table}"

fig, axes = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [0.55, 1]})
fig.patch.set_facecolor("#0b1220")
for ax in axes:
    ax.set_facecolor("#111827")
    ax.axis("off")
axes[0].set_title("BRANCH CHECK · source", color="#93c5fd", loc="left", fontsize=13, pad=6)
axes[0].text(0.02, 0.98, source, va="top", ha="left", family="monospace", fontsize=11,
             color="#e5e7eb", linespacing=1.5, transform=axes[0].transAxes)
axes[1].set_title("OUTPUT · ai-benchmark branch and saved proof result", color="#86efac", loc="left", fontsize=13, pad=6)
axes[1].text(0.02, 0.98, output, va="top", ha="left", family="monospace", fontsize=10.5,
             color="#f9fafb", linespacing=1.4, transform=axes[1].transAxes)
fig.suptitle("Slide 9 evidence · AI benchmark branch", color="white", fontsize=18, x=0.05, ha="left")
fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.93])
out = ROOT / "evidence" / "slide09_ai_benchmark_branch.png"
fig.savefig(out, dpi=170, facecolor=fig.get_facecolor(), bbox_inches="tight")
print(out)
