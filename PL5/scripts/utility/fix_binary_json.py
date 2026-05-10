import pickle
import json
from pathlib import Path

LOGS_DIR = Path("e:/PL5/logs")

# 找到所有可能是二进制JSON的文件
BINARY_FILES = [
    "workflow_state (2).json",
    "workflow_state (3).json",
    "workflow_state_backup_20260428_112113 (2).json",
    "workflow_state_backup_20260428_112544 (2).json"
]

print("开始修复二进制JSON文件...\n")
count = 0
for fname in BINARY_FILES:
    path = LOGS_DIR / fname
    if not path.exists():
        continue
    
    try:
        # 尝试读取为pickle
        with open(path, 'rb') as f:
            data = pickle.load(f)
        print(f"✅ {fname}: 成功解析为pickle")
        
        # 保存为真正的JSON
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        count += 1
        print(f"✅ {fname}: 已重写为标准JSON格式\n")
    
    except Exception as e:
        print(f"⚠️ {fname}: 无法解析为pickle: {str(e)}\n")

print(f"✅ 完成！共修复 {count} 个二进制JSON文件")
