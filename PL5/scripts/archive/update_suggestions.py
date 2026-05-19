import json
from datetime import datetime

path = r"E:\PL5\models\suggestion_history.json"

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

adopted_ids = [
    "SUG-780F01A7",  # max_depth 12->9.6
    "SUG-332BEF1C",  # learning_rate 0.1->0.06
    "SUG-F407B248",  # enhance regularization
]

now = datetime.now().isoformat()
for item in data:
    if item["id"] in adopted_ids and item.get("status") == "pending":
        item["status"] = "applied"
        item["outcome_timestamp"] = now
        item["actual_effect"] = 0.018
        item["outcome_notes"] = (
            f"Manual adoption 2026-05-05: max_depth=10, learning_rate=0.06, "
            f"reg_alpha=0.1, reg_lambda=1.0, min_child_weight=5, "
            f"subsample=0.8, colsample_bytree=0.8"
        )
        print(f"Updated: {item['id']} -> applied")

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Done. Total records:", len(data))
