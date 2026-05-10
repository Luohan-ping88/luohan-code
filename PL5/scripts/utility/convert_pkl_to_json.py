import pickle
import json
from pathlib import Path

LOGS_DIR = Path("e:/PL5/logs")

pkl_files = [
    "workflow_state.pkl",
    "workflow_state_backup_20260428_112113.pkl",
    "workflow_state_backup_20260428_112544.pkl"
]

for fname in pkl_files:
    pkl_path = LOGS_DIR / fname
    if not pkl_path.exists():
        continue
    print(f"Reading: {fname}")
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    json_path = LOGS_DIR / f"{Path(fname).stem}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"Wrote: {json_path}")
