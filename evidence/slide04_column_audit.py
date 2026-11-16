"""Print the timing-bin counts used on Data Lead slide 4."""

import ast
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
columns_text = (ROOT / "docs" / "COLUMNS.md").read_text(encoding="utf-8")
timing_rows = re.findall(r"^\| `([^`]+)` \| ([123]) \|", columns_text, flags=re.M)
timing_by_column = {name: int(bin_id) for name, bin_id in timing_rows}
bin_counts = Counter(timing_by_column.values())

features_text = (ROOT / "src" / "features.py").read_text(encoding="utf-8")
feature_literal = re.search(
    r"MODEL_FEATURES\s*=\s*(\[[\s\S]*?\])", features_text
).group(1)
model_features = ast.literal_eval(feature_literal)
selected_counts = Counter(timing_by_column[name] for name in model_features)

print(f"Audited source columns: {len(timing_rows)}")
print(
    "Timing bins: "
    f"Bin 1 fixed={bin_counts[1]}, "
    f"Bin 2 amendable={bin_counts[2]}, "
    f"Bin 3 after-the-fact={bin_counts[3]}"
)
print(f"Team-approved feature count: {len(model_features)}")
print(
    "Selected features by timing bin: "
    f"Bin 1={selected_counts[1]}, "
    f"Bin 2={selected_counts[2]}, "
    f"Bin 3={selected_counts[3]}"
)
