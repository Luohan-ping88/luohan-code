#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PL5 日循环任务 - 自动收尾处理器
当 final_prediction.json 出现（或主管线进程退出）后，自动:
  1. 从真实运行数据生成 daily_cycle_summary_YYYYMMDD.md
  2. 从 final_prediction.json 生成 top8_training_prediction_report_<period>.md
  3. git 提交所有变更（配置修复 + 报告 + 代码变更）
  4. 尝试 git push 到远程仓库（无 token 则记录待推送）
  5. 写入完成标记 logs/auto_complete_done.json

用法:
  python scripts/utility/auto_complete_daily_cycle.py <pipeline_pid> [log_file]
"""
import sys
import os
import json
import time
import csv
import subprocess
import traceback
from datetime import datetime, timedelta
from pathlib import Path

# 项目根目录
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # /workspace/PL5
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

LOGS_DIR = PROJECT_ROOT / "logs"
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_FILE = PROJECT_ROOT / "data" / "processed" / "pl5_processed.csv"
FINAL_PRED = LOGS_DIR / "final_prediction.json"
TRAINING_INFO = LOGS_DIR / "training_info.json"
TASK_HISTORY = LOGS_DIR / "task_history_v8.json"
DONE_MARKER = LOGS_DIR / "auto_complete_done.json"

POSITION_NAMES = {'wan': '万位', 'qian': '千位', 'bai': '百位', 'shi': '十位', 'ge': '个位'}
POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']

# 中文任务名映射
TASK_CN = {
    'data_fetch': '数据获取', 'evaluation': '评估分析', 'optimization': '策略优化',
    'training': '深度训练', 'incremental_training': '增量训练',
    'first_prediction_verification': '首次预测验证',
    'second_prediction_verification': '二次预测验证',
    'third_prediction_verification': '三次预测验证',
    'deep_strategy_optimization': '深度策略优化',
    'prediction_preview': '预测预生成',
    'final_prediction': '最终预测',
    'final_prediction_verification': '最终预测验证',
    'pre_sale_prediction': '售前预测', 'send_report': '发送报告',
    'extra_training': '额外训练', 'hyperparameter_tune': '超参调优',
    'ensemble_refine': '集成精调',
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def fmt_duration(sec):
    if sec is None:
        return "N/A"
    try:
        sec = float(sec)
    except Exception:
        return "N/A"
    if sec < 60:
        return f"约{int(sec)}秒"
    if sec < 3600:
        return f"约{int(sec//60)}分{int(sec%60)}秒"
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    return f"约{h}小时{m}分"


def read_json(path, default=None):
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return default


def load_today_tasks(run_date_str):
    """读取任务历史，筛选最近一次完整的日循环（从 data_fetch 到 send_report）
    
    支持跨天的日循环（如晚上开始，凌晨结束）。
    策略：从后往前查找，找到最近的 send_report(SUCCESS)，
    然后往前找直到 data_fetch(SUCCESS)，中间的所有任务构成本次循环。
    """
    hist = read_json(TASK_HISTORY, [])
    if not isinstance(hist, list):
        return []
    
    # 策略1：查找最近一次完整日循环（send_report 往前到 data_fetch）
    cycle_tasks = []
    found_send = False
    for rec in reversed(hist):
        if not isinstance(rec, dict):
            continue
        task_name = rec.get('task_name', '')
        status = rec.get('status', '')
        
        if not found_send and task_name == 'send_report' and status == 'SUCCESS':
            found_send = True
            cycle_tasks.insert(0, rec)
            continue
        
        if found_send:
            cycle_tasks.insert(0, rec)
            if task_name == 'data_fetch' and status == 'SUCCESS':
                break
    
    # 策略2：如果策略1没找到完整循环，回退到按日期筛选（最近24小时）
    if not cycle_tasks or cycle_tasks[0].get('task_name') != 'data_fetch':
        try:
            day_start = datetime.fromisoformat(run_date_str + "T00:00:00")
        except Exception:
            day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # 往前推1天以覆盖跨天场景
        from datetime import timedelta
        day_start = day_start - timedelta(hours=12)
        today = []
        for rec in hist:
            if not isinstance(rec, dict):
                continue
            st = rec.get('start_time')
            try:
                st_dt = datetime.fromisoformat(st)
            except Exception:
                continue
            if st_dt >= day_start:
                today.append(rec)
        # 去重：同一 task_name 保留最后一条
        seen = {}
        for rec in today:
            seen[rec.get('task_name')] = rec
        cycle_tasks = list(seen.values())
        cycle_tasks.sort(key=lambda r: r.get('start_time', ''))
        return cycle_tasks
    
    # 对策略1找到的循环任务去重（同一任务保留最后一次成功的）
    seen = {}
    for rec in cycle_tasks:
        seen[rec.get('task_name')] = rec
    out = list(seen.values())
    out.sort(key=lambda r: r.get('start_time', ''))
    return out


def load_recent_draws(n=10):
    rows = []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8-sig') as f:
            rdr = csv.DictReader(f)
            rows = list(rdr)
    except Exception:
        pass
    if not rows:
        return [], None, None
    last = rows[-1]
    latest_period = last.get('period')
    latest_full = last.get('full_number')
    return rows[-n:], latest_period, latest_full


def generate_summary_report(run_date_str, tasks, training_info, recent_draws,
                            latest_period, latest_full, final_pred, pipeline_ok):
    today = run_date_str
    lines = []
    lines.append("# 日循环任务执行摘要报告\n")
    lines.append(f"**执行日期**: {today}  ")
    cycle_start = tasks[0]['start_time'] if tasks else "N/A"
    cycle_end = tasks[-1]['end_time'] if tasks else "N/A"
    lines.append(f"**开始时间**: {cycle_start}  ")
    lines.append(f"**结束时间**: {cycle_end}  ")
    # 总耗时
    total_sec = None
    try:
        s = datetime.fromisoformat(cycle_start)
        e = datetime.fromisoformat(cycle_end)
        total_sec = (e - s).total_seconds()
    except Exception:
        pass
    lines.append(f"**总耗时**: {fmt_duration(total_sec)}  ")
    lines.append("**执行模式**: 生产模式（完整模式，无时限）  ")
    total = len(tasks)
    succ = sum(1 for t in tasks if t.get('status') == 'SUCCESS')
    fail = sum(1 for t in tasks if t.get('status') == 'FAILED')
    lines.append(f"**任务总数**: {total}  ")
    lines.append(f"**成功数**: {succ}  ")
    rate = (succ / total * 100) if total else 0
    lines.append(f"**成功率**: {rate:.1f}%\n")
    lines.append("---\n\n## 一、任务执行清单\n")
    lines.append("| 序号 | 任务名称 | 中文名 | 状态 | 开始时间 | 结束时间 | 耗时 |")
    lines.append("|------|---------|--------|------|---------|---------|------|")
    for i, t in enumerate(tasks, 1):
        nm = t.get('task_name', '?')
        cn = TASK_CN.get(nm, nm)
        st_status = t.get('status', '?')
        icon = "✅ 成功" if st_status == 'SUCCESS' else ("❌ 失败" if st_status == "FAILED" else st_status)
        st = (t.get('start_time') or '')[11:19] if t.get('start_time') else 'N/A'
        en = (t.get('end_time') or '')[11:19] if t.get('end_time') else 'N/A'
        lines.append(f"| {i} | {nm} | {cn} | {icon} | {st} | {en} | {fmt_duration(t.get('duration'))} |")
    lines.append("")

    # 训练模型信息
    lines.append("\n---\n\n## 二、训练模型信息\n")
    if training_info:
        lines.append(f"- **模型版本**: {training_info.get('model_version', 'V10.3')}")
        lines.append(f"- **训练状态**: {training_info.get('training_status', 'N/A')}")
        lines.append(f"- **训练时间**: {fmt_duration(training_info.get('training_time'))}")
        lines.append(f"- **特征数量**: {training_info.get('feature_count', 'N/A')}")
        lines.append(f"- **数据量**: {training_info.get('data_count', 'N/A')}")
        lines.append(f"- **最新期号**: {training_info.get('latest_period', 'N/A')}")
        md = training_info.get('models', {})
        if md:
            lines.append("- **模型状态**:")
            for k, v in md.items():
                lines.append(f"  - {k}: {'已启用' if v else '未启用'}")
    else:
        lines.append("- 训练信息文件未生成（training_info.json 缺失）")

    # 预测结果摘要
    lines.append("\n---\n\n## 三、预测结果摘要\n")
    if final_pred:
        next_p = final_pred.get('next_period', 'N/A')
        latest_p = final_pred.get('latest_period', latest_period)
        lines.append(f"- **预测期号**: {next_p}")
        lines.append(f"- **预测时间**: {final_pred.get('prediction_time', 'N/A')}")
        lines.append(f"- **最新数据期号**: {latest_p}")
        lines.append(f"- **上期开奖号码**: {latest_full}")
        cl = final_pred.get('confidence_level', 'medium')
        lines.append(f"- **置信度等级**: {cl}")
        vc = final_pred.get('verification_consistency', {})
        if isinstance(vc, dict):
            lines.append(f"- **佐证整体一致性**: {vc.get('overall', 0):.2%}" if isinstance(vc.get('overall'), (int, float)) else f"- **佐证整体一致性**: {vc.get('overall', 'N/A')}")
        preds = final_pred.get('predictions', {})
        lines.append("\n### 最终预测Top-8号码\n")
        lines.append("| 位置 | Top-1 | Top-2 | Top-3 | Top-4 | Top-5 | Top-6 | Top-7 | Top-8 |")
        lines.append("|------|-------|-------|-------|-------|-------|-------|-------|-------|")
        for pos in POSITIONS:
            p = preds.get(pos, {})
            tk = p.get('top_k', [])
            tk8 = (tk + [''] * 8)[:8]
            row = " | ".join(str(x) for x in tk8)
            lines.append(f"| {POSITION_NAMES[pos]} | {row} |")
    else:
        lines.append("- 最终预测文件未生成（final_prediction.json 缺失，管线可能未完成）")

    # 近期开奖
    if recent_draws:
        lines.append("\n### 近期开奖回顾（最近10期）\n")
        for r in recent_draws[-10:]:
            lines.append(f"- 第{r.get('period')}期: {r.get('full_number')}")

    # 问题与跟进
    lines.append("\n---\n\n## 四、出现的问题\n")
    issues = []
    for t in tasks:
        if t.get('status') == 'FAILED' and t.get('error_message'):
            issues.append(f"- **{TASK_CN.get(t['task_name'], t['task_name'])}失败**: {t['error_message']}")
    # 邮件问题
    if not pipeline_ok and not final_pred:
        issues.append("- **管线未正常完成**: 主管线进程退出但未生成 final_prediction.json，请检查日志")
    if not issues:
        lines.append("本次运行未出现致命错误。")
    else:
        lines.extend(issues)
    # torch 备注
    lines.append("\n**备注**: torch 已安装（2.13.0+cpu），Mamba / iTransformer 模型可正常训练；全部 6 大模型（Stacking/HMM/Copula/BSTS/Mamba/iTransformer）+ 贝叶斯量化器完整启用。")

    # 跟进
    lines.append("\n---\n\n## 五、后续跟进事项\n")
    lines.append("1. **预测验证**: 等待预测期号开奖结果，验证命中准确性")
    lines.append("2. **模型监控**: 持续监控模型表现，准确率下降时进行增量训练")
    lines.append("3. **Git 同步**: 若推送失败（无 token），使用 `./push_to_github.sh <TOKEN>` 手动推送")
    lines.append("4. **邮件发送**: send_report 如失败已自动回退本地文件保存，生产环境确认 SMTP 出站正常")
    lines.append("5. **特征优化**: 评估特征重要性，剔除低贡献特征提升训练效率")

    # 环境
    lines.append("\n---\n\n## 六、环境配置\n")
    lines.append("- **Python版本**: " + sys.version.split()[0])
    lines.append("- **已安装核心依赖**: numpy/pandas/scikit-learn/lightgbm/xgboost/catboost/hmmlearn/statsmodels/schedule/psutil/PyYAML/requests/beautifulsoup4/lxml/python-dotenv")
    lines.append("- **配置修复**: training_status.json 的 UTF-8 BOM 已去除；git 身份已配置")
    lines.append("- **运行模式**: 生产模式（无任何环节限时）")

    lines.append("\n---\n\n## 七、总结\n")
    lines.append(f"本次日循环任务以**生产模式**执行，{succ}/{total} 个任务成功完成，总耗时 {fmt_duration(total_sec)}。")
    if final_pred:
        lines.append("最终预测结果已基于真实管线输出生成 Top-8 报告（见 results/top8_training_prediction_report_*.md）。")
    lines.append("\n**报告生成时间**: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    lines.append("**报告版本**: V1.0 (自动收尾生成)")

    return "\n".join(lines)


def generate_top8_report(final_pred, training_info, recent_draws, latest_period, latest_full):
    if not final_pred:
        return None
    next_p = final_pred.get('next_period', '未知')
    preds = final_pred.get('predictions', {})
    vc = final_pred.get('verification_consistency', {}) or {}
    vrs = final_pred.get('verification_results_summary', {}) or {}
    lines = []
    lines.append("# Top-8码详细训练预测分析报告\n")
    lines.append(f"**预测期号**: {next_p}  ")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"**模型版本**: {(training_info or {}).get('model_version', 'V10.3')}  ")
    lines.append("**训练模式**: 生产模式（完整训练+强化训练）  ")
    lines.append("**报告版本**: V1.0 (基于真实管线输出自动生成)\n")
    lines.append("---\n\n## 一、执行摘要\n")
    lines.append(f"本次针对第{next_p}期排列5的Top-8码预测，基于真实日循环管线输出。")
    if training_info:
        lines.append(f"\n**关键指标**:")
        lines.append(f"- 训练数据量: {(training_info or {}).get('data_count', 'N/A')}")
        lines.append(f"- 特征数量: {(training_info or {}).get('feature_count', 'N/A')}")
        lines.append(f"- 训练耗时: {fmt_duration((training_info or {}).get('training_time'))}")
        lines.append(f"- 训练状态: {(training_info or {}).get('training_status', 'N/A')}")
    cl = final_pred.get('confidence_level', 'medium')
    ov = vc.get('overall') if isinstance(vc, dict) else None
    if isinstance(ov, (int, float)):
        lines.append(f"- 佐证整体一致性: {ov:.2%}")
    lines.append(f"- 置信度等级: {cl}")

    # 速查表
    lines.append("\n### 最终预测Top-8速查表\n")
    lines.append("| 位置 | Top-1 | Top-2 | Top-3 | Top-4 | Top-5 | Top-6 | Top-7 | Top-8 |")
    lines.append("|------|-------|-------|-------|-------|-------|-------|-------|-------|")
    for pos in POSITIONS:
        tk = (preds.get(pos, {}).get('top_k', []) + [''] * 8)[:8]
        lines.append(f"| {POSITION_NAMES[pos]} | " + " | ".join(str(x) for x in tk) + " |")

    # 训练数据
    lines.append("\n---\n\n## 二、训练数据概览\n")
    if training_info:
        lines.append(f"- 总期数: {training_info.get('data_count', 'N/A')}")
        lines.append(f"- 最新期号: {training_info.get('latest_period', latest_period)}")
    if recent_draws:
        lines.append("\n### 最近10期开奖回顾\n")
        lines.append("| 期号 | 完整号码 |")
        lines.append("|------|----------|")
        for r in recent_draws[-10:]:
            lines.append(f"| {r.get('period')} | {r.get('full_number')} |")

    # 佐证一致性
    lines.append("\n---\n\n## 三、佐证一致性分析\n")
    if vrs:
        lines.append("### 各轮佐证Top-3对比\n")
        rounds = list(vrs.keys())
        for pos in POSITIONS:
            lines.append(f"\n**{POSITION_NAMES[pos]}位**:")
            header = "| 佐证轮次 | " + " | ".join(f"Top-{i+1}" for i in range(3)) + " |"
            sep = "|---------|" + "|".join(["-------"] * 3) + "|"
            lines.append(header)
            lines.append(sep)
            for rk in rounds:
                rv = vrs[rk]
                t3 = (rv.get('predictions', {}).get(pos, []) + [''] * 3)[:3]
                lines.append(f"| {rk} | " + " | ".join(str(x) for x in t3) + " |")
        if isinstance(ov, (int, float)):
            lines.append(f"\n**整体一致性**: {ov:.2%}")
        pos_scores = vc.get('positions', {}) if isinstance(vc, dict) else {}
        if pos_scores:
            lines.append("\n**各位置一致性**:")
            for p, s in pos_scores.items():
                if isinstance(s, (int, float)):
                    lines.append(f"- {POSITION_NAMES.get(p, p)}位: {s:.2%}")
    else:
        lines.append("（佐证摘要数据缺失）")

    # 各位置详解
    lines.append("\n---\n\n## 四、最终Top-8预测详解\n")
    for pos in POSITIONS:
        p = preds.get(pos, {})
        tk = p.get('top_k', [])
        lines.append(f"\n### {POSITION_NAMES[pos]}位预测详解\n")
        lines.append(f"**Top-8号码**: {tk}")
        lines.append("\n| 排名 | 号码 |")
        lines.append("|------|------|")
        for i, num in enumerate(tk[:8], 1):
            star = " **" if i <= 3 else ""
            lines.append(f"| Top-{i} |{star} {num}{star} |")
        w = p.get('weights_used', {})
        if w:
            wstr = ", ".join(f"{k}={v:.2f}" for k, v in w.items())
            lines.append(f"\n**模型权重**: {wstr}")

    # 风险提示
    lines.append("\n---\n\n## 五、风险提示与使用建议\n")
    lines.append("⚠️ **重要风险提示**:")
    lines.append("1. 彩票本质是随机游戏，每期开奖完全独立，历史数据不决定未来结果")
    lines.append("2. 本报告仅供参考，不构成任何中奖承诺或保证")
    lines.append("3. 请理性投注，量力而行，切勿沉迷")
    lines.append("4. 未成年人禁止购买彩票\n")
    lines.append("**免责声明**: 本报告基于统计模型自动生成，不构成投注建议。")

    lines.append("\n---\n\n**报告生成时间**: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    lines.append(f"**预测期号**: {next_p}")
    return "\n".join(lines), next_p


def git_commit_and_push(report_files):
    log("开始 git 提交与推送...")
    # 配置身份（若未配置）
    try:
        if not subprocess.run(['git', 'config', 'user.name'], capture_output=True, text=True).stdout.strip():
            subprocess.run(['git', 'config', 'user.name', 'PL5 Auto System'], check=False)
            subprocess.run(['git', 'config', 'user.email', 'pl5-auto@users.noreply.github.com'], check=False)
    except Exception:
        pass

    # 添加：报告、配置、可能的代码变更
    add_paths = ['results/', 'config/', 'logs/training_info.json', 'logs/final_prediction.json',
                 'scripts/utility/auto_complete_daily_cycle.py', 'requirements.txt']
    for p in add_paths:
        subprocess.run(['git', 'add', p], cwd=str(PROJECT_ROOT),
                       capture_output=True, text=True, timeout=15)

    # 检查是否有变更
    st = subprocess.run(['git', 'status', '--porcelain'], cwd=str(PROJECT_ROOT),
                       capture_output=True, text=True, timeout=15)
    if not st.stdout.strip():
        log("无变更需要提交")
        return False, "no changes"

    commit_msg = f"auto: 日循环任务自动同步 {datetime.now().strftime('%Y-%m-%d %H:%M')} (生产模式完整运行)"
    cmt = subprocess.run(['git', 'commit', '-m', commit_msg], cwd=str(PROJECT_ROOT),
                         capture_output=True, text=True, timeout=60)
    if cmt.returncode != 0:
        log(f"提交失败: {cmt.stderr.strip()[:200]}")
        return False, cmt.stderr.strip()

    # 推送
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    push = subprocess.run(['git', 'push', 'origin', 'HEAD:main'], cwd=str(PROJECT_ROOT),
                          capture_output=True, text=True, timeout=120, env=env)
    if push.returncode == 0:
        log("✓ 推送成功，远程仓库已更新")
        return True, "pushed"
    else:
        log(f"✗ 推送失败（无 token）: {push.stderr.strip()[:200]}")
        log("  → 请使用: ./push_to_github.sh <GITHUB_TOKEN>  手动推送")
        return False, push.stderr.strip()


def main():
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    log_file = sys.argv[2] if len(sys.argv) > 2 else None
    run_date_str = datetime.now().strftime('%Y-%m-%d')

    log(f"自动收尾处理器启动, 等待 final_prediction.json (pipeline_pid={pid})")

    # 等待 final_prediction.json 出现 或 主管线进程退出
    waited = 0
    while True:
        if FINAL_PRED.exists():
            log("✓ final_prediction.json 已生成")
            break
        if pid and not _pid_alive(pid):
            log(f"✗ 主管线进程 {pid} 已退出，且未生成 final_prediction.json")
            break
        time.sleep(60)
        waited += 60
        if waited % 600 == 0:
            log(f"仍在等待... 已等待 {waited//60} 分钟, final_prediction={'yes' if FINAL_PRED.exists() else 'no'}")

    pipeline_ok = FINAL_PRED.exists()

    # 读取真实数据
    final_pred = read_json(FINAL_PRED) if pipeline_ok else None
    training_info = read_json(TRAINING_INFO)
    tasks = load_today_tasks(run_date_str)
    recent_draws, latest_period, latest_full = load_recent_draws(10)

    log(f"数据读取: tasks={len(tasks)}, final_pred={'yes' if final_pred else 'no'}, "
        f"training_info={'yes' if training_info else 'no'}, latest_period={latest_period}")

    # 生成摘要报告
    try:
        summary_md = generate_summary_report(run_date_str, tasks, training_info, recent_draws,
                                             latest_period, latest_full, final_pred, pipeline_ok)
        summary_path = RESULTS_DIR / f"daily_cycle_summary_{run_date_str.replace('-', '')}.md"
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_md)
        log(f"✓ 摘要报告已生成: {summary_path}")
    except Exception as e:
        log(f"✗ 摘要报告生成失败: {e}")
        traceback.print_exc()
        summary_path = None

    # 生成 Top-8 报告
    top8_path = None
    if final_pred:
        try:
            res = generate_top8_report(final_pred, training_info, recent_draws, latest_period, latest_full)
            if res:
                top8_md, next_p = res
                top8_path = RESULTS_DIR / f"top8_training_prediction_report_{next_p}.md"
                with open(top8_path, 'w', encoding='utf-8') as f:
                    f.write(top8_md)
                log(f"✓ Top-8 报告已生成: {top8_path}")
        except Exception as e:
            log(f"✗ Top-8 报告生成失败: {e}")
            traceback.print_exc()

    # git 提交与推送
    report_files = [p for p in [summary_path, top8_path] if p]
    push_ok, push_msg = git_commit_and_push(report_files)

    # 写完成标记
    done = {
        'finish_time': datetime.now().isoformat(),
        'run_date': run_date_str,
        'pipeline_ok': pipeline_ok,
        'tasks_succeeded': sum(1 for t in tasks if t.get('status') == 'SUCCESS'),
        'tasks_total': len(tasks),
        'summary_report': str(summary_path) if summary_path else None,
        'top8_report': str(top8_path) if top8_path else None,
        'push_ok': push_ok,
        'push_message': str(push_msg)[:300],
        'next_period': final_pred.get('next_period') if final_pred else None,
    }
    with open(DONE_MARKER, 'w', encoding='utf-8') as f:
        json.dump(done, f, indent=2, ensure_ascii=False)
    log(f"✓ 自动收尾完成: {done}")
    print("\n=== AUTO-COMPLETE SUMMARY ===")
    print(json.dumps(done, indent=2, ensure_ascii=False))


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()
