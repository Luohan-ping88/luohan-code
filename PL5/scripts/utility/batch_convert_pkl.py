import pickle
import json
from pathlib import Path

LOGS_DIR = Path("e:/PL5/logs")

# 查找所有.pkl文件
pkl_files = list(LOGS_DIR.glob("*.pkl"))

print(f"找到 {len(pkl_files)} 个.pkl文件\n")

# 逐个转换
for i, pkl_path in enumerate(pkl_files, 1):
    try:
        with open(pkl_path, "rb") as f:
            data = pickle.load(f)
        
        json_path = pkl_path.with_suffix(".json")
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"✅ [{i}/{len(pkl_files)}] {pkl_path.name} -> {json_path.name}")
        
    except Exception as e:
        print(f"❌ [{i}/{len(pkl_files)}] {pkl_path.name} 转换失败: {str(e)}")

print("\n✅ 所有.pkl文件转换完成！")