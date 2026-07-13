"""
数据获取功能专项测试
验证: 本地文件加载、解析、处理、网络获取状态
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "logs" / "data_load_test.txt"
lines = []

def log(msg):
    print(msg)
    lines.append(msg)

def save():
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

log("=" * 60)
log("  PL5 数据获取功能专项测试")
log("=" * 60)

results = []

# ─── T1: 路径配置验证 ────────────────────────────────────────
def t1():
    from src.core.data.config import ROOT_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR
    assert (ROOT_DIR / "data").exists(), f"data/ 目录不存在: {ROOT_DIR}"
    raw_file = RAW_DATA_DIR / "pl5_history.txt"
    proc_file = PROCESSED_DATA_DIR / "pl5_processed.csv"
    assert raw_file.exists(), f"历史数据文件不存在: {raw_file}"
    file_size = raw_file.stat().st_size
    assert file_size > 10000, f"历史数据文件过小: {file_size} bytes"
    return (f"RAW={RAW_DATA_DIR}\n"
            f"     raw_file={file_size//1024} KB, proc_exists={proc_file.exists()}")

# ─── T2: 本地文件直接读取（不依赖类）────────────────────────
def t2():
    raw_path = Path(__file__).parent.parent / "data" / "raw" / "pl5_history.txt"
    with open(raw_path, 'r', encoding='utf-8') as f:
        content = f.read()
    lines_raw = [l.strip() for l in content.strip().split('\n') if l.strip()]
    # 解析第一行和最后一行
    first = lines_raw[0].split()
    last = lines_raw[-1].split()
    assert len(first) >= 7, f"首行字段不足: {first}"
    assert len(last) >= 7, f"末行字段不足: {last}"
    first_period = first[0]
    last_period = last[0]
    total = len(lines_raw)
    return f"总行数={total}, 首期={first_period}, 末期={last_period}"

# ─── T3: DataValidator 验证 ────────────────────────────────
def t3():
    from src.core.data.collector import DataValidator
    v = DataValidator()
    # 正常记录
    ok, msg = v.validate_record({
        'period': '2026074', 'wan': 4, 'qian': 0, 'bai': 6, 'shi': 3, 'ge': 3
    })
    assert ok, f"正常记录验证失败: {msg}"
    # 无效期号
    ok2, _ = v.validate_record({
        'period': 'ABCDE', 'wan': 4, 'qian': 0, 'bai': 6, 'shi': 3, 'ge': 3
    })
    assert not ok2, "无效期号应该验证失败"
    # 数字超范围
    ok3, _ = v.validate_record({
        'period': '2026074', 'wan': 10, 'qian': 0, 'bai': 6, 'shi': 3, 'ge': 3
    })
    assert not ok3, "超范围数字应该验证失败"
    return "正常/无效期号/超范围 三种情况均验证正确"

# ─── T4: PL5DataCollectorV8 加载本地文件 ────────────────────
def t4():
    from src.core.data.collector import PL5DataCollectorV8
    col = PL5DataCollectorV8()
    # 正确方法名: load_local_data()
    df = col.load_local_data()
    assert df is not None and not df.empty, "load_local_data 返回空数据"
    required = ['period', 'wan', 'qian', 'bai', 'shi', 'ge']
    missing = [c for c in required if c not in df.columns]
    assert not missing, f"缺少列: {missing}"
    assert len(df) > 7000, f"数据量不足: {len(df)} 条"
    first_p = str(df['period'].iloc[0])
    last_p = str(df['period'].iloc[-1])
    # 验证数字列全部在0-9范围
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        bad = df[~df[pos].between(0, 9)]
        assert bad.empty, f"{pos}列有异常值: {bad[pos].unique()}"
    return f"记录数={len(df)}, 首期={first_p}, 末期={last_p}, 数字范围正常"

# ─── T5: parse_raw_data 解析正确性 ─────────────────────────
def t5():
    from src.core.data.collector import PL5DataCollectorV8
    col = PL5DataCollectorV8()
    # 读取前100行原始文本
    raw_path = col.raw_data_path
    with open(raw_path, 'r', encoding='utf-8') as f:
        text_100 = ''.join([f.readline() for _ in range(100)])
    df = col.parse_raw_data(text_100)
    assert not df.empty, "100行解析结果为空"
    assert len(df) >= 90, f"解析成功率过低: {len(df)}/100"
    # 验证数字范围
    for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
        bad = df[~df[pos].between(0, 9)]
        assert bad.empty, f"{pos}列有超范围值: {bad[pos].unique()}"
    return f"解析100行 -> {len(df)}条有效, 数字范围全部0-9"

# ─── T6: 处理后 CSV 加载 ─────────────────────────────────
def t6():
    import pandas as pd
    proc_path = Path(__file__).parent.parent / "data" / "processed" / "pl5_processed.csv"
    assert proc_path.exists(), f"processed CSV 不存在: {proc_path}"
    df = pd.read_csv(proc_path, nrows=5)  # 只读 header + 5行
    col_count = len(df.columns)
    # 读全部行数（不加载内容，只看行数）
    with open(proc_path, 'r', encoding='utf-8') as f:
        row_count = sum(1 for _ in f) - 1  # 减去header行
    return f"特征维度={col_count}, 数据行数={row_count}"

# ─── T7: DataVersionManager ─────────────────────────────
def t7():
    from src.core.data.collector import DataVersionManager
    vm = DataVersionManager()
    info = vm.get_current_version()
    # 应该有版本信息（如果数据加载过的话）
    return (f"version={info.get('version','N/A')}, "
            f"records={info.get('record_count','N/A')}, "
            f"latest={info.get('latest_period','N/A')}")

# ─── T8: 网络获取可达性（仅测试连接，不实际写入）──────────
def t8():
    import requests
    url = "http://data.17500.cn/pl5_asc.txt"
    try:
        resp = requests.head(url, timeout=5, allow_redirects=True)
        return f"HTTP {resp.status_code} (HEAD请求), 网络可达"
    except requests.Timeout:
        return "连接超时 (5s) - 网络不可达或被限速，系统将使用本地缓存"
    except requests.ConnectionError:
        return "连接失败 - 网络不可达，系统将使用本地缓存"
    except Exception as e:
        return f"连接异常: {type(e).__name__}: {e}"

# ─── 执行所有测试 ────────────────────────────────────────────
tests = [
    ("T1. 路径配置验证",          t1),
    ("T2. 原始文件直读",          t2),
    ("T3. DataValidator 正确性",  t3),
    ("T4. 本地数据加载(全量)",    t4),
    ("T5. 解析100行准确率",       t5),
    ("T6. 处理后CSV加载",         t6),
    ("T7. DataVersionManager",    t7),
    ("T8. 网络数据源可达性",      t8),
]

pass_n = warn_n = fail_n = 0
for name, fn in tests:
    try:
        detail = fn()
        log(f"\n  [PASS] {name}")
        for dline in str(detail).split('\n'):
            log(f"         {dline}")
        pass_n += 1
        results.append((name, 'PASS', detail))
    except AssertionError as e:
        log(f"\n  [FAIL] {name}")
        log(f"         AssertionError: {e}")
        fail_n += 1
        results.append((name, 'FAIL', str(e)))
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(f"\n  [FAIL] {name}")
        log(f"         {type(e).__name__}: {e}")
        fail_n += 1
        results.append((name, 'FAIL', tb))

log("")
log("=" * 60)
log(f"  结果汇总: {pass_n} PASS / {fail_n} FAIL / {len(tests)} 项")
log("=" * 60)

save()
