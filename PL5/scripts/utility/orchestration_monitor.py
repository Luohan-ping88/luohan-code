#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能编排系统 - 性能监控与可视化工具
提供编排系统的性能数据采集、分析和可视化功能
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class OrchestrationMonitor:
    """编排监控器"""
    
    def __init__(self, state_dir: Optional[str] = None):
        if state_dir:
            self.state_dir = Path(state_dir)
        else:
            self.state_dir = Path(__file__).parent.parent.parent / "logs"
        
        self.state_file = self.state_dir / "orchestration_state.json"
        self.history_file = self.state_dir / "orchestration_history.json"
    
    def load_state(self) -> Optional[Dict]:
        """加载状态数据"""
        if self.state_file.exists():
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    def load_history(self) -> List[Dict]:
        """加载历史记录"""
        if self.history_file.exists():
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def generate_text_report(self) -> str:
        """生成文本格式的报告"""
        state = self.load_state()
        history = self.load_history()
        
        report = []
        report.append("=" * 80)
        report.append("智能编排系统 - 性能监控报告")
        report.append("=" * 80)
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        if state:
            report.append("--- 系统状态 ---")
            report.append(f"训练窗口中: {'是' if state.get('in_training_window') else '否'}")
            if state.get('training_window_start'):
                report.append(f"窗口开始: {state['training_window_start']}")
            if state.get('training_window_end'):
                report.append(f"窗口结束: {state['training_window_end']}")
            report.append("")
            
            if 'performance_metrics' in state:
                metrics = state['performance_metrics']
                report.append("--- 性能指标 ---")
                report.append(f"总任务数: {metrics.get('total_tasks_executed', 0)}")
                report.append(f"成功任务: {metrics.get('tasks_success', 0)}")
                report.append(f"失败任务: {metrics.get('tasks_failed', 0)}")
                report.append(f"平均耗时: {metrics.get('avg_execution_time', 0):.4f} 秒")
                report.append(f"总耗时: {metrics.get('total_execution_time', 0):.4f} 秒")
                
                total = metrics.get('total_tasks_executed', 0)
                if total > 0:
                    success_rate = (metrics.get('tasks_success', 0) / total) * 100
                    report.append(f"成功率: {success_rate:.2f}%")
                report.append("")
        
        if history:
            report.append("--- 历史记录 (最近10条) ---")
            for i, record in enumerate(history[-10:], 1):
                report.append(f"{i}. {record.get('name', 'unknown')} - {record.get('status', 'unknown')}")
                if 'start_time' in record:
                    report.append(f"   开始: {record['start_time']}")
                if 'error' in record and record['error']:
                    report.append(f"   错误: {record['error']}")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def generate_html_report(self) -> str:
        """生成HTML格式的可视化报告"""
        state = self.load_state()
        history = self.load_history()
        
        html_parts = []
        
        html_parts.append("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能编排系统 - 监控报告</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 30px;
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        .status-card {
            background: #e8f5e9;
            border-left: 4px solid #4CAF50;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }
        .status-card.warning {
            background: #fff3e0;
            border-left-color: #ff9800;
        }
        .status-card.error {
            background: #ffebee;
            border-left-color: #f44336;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .metric-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #2196F3;
        }
        .metric-label {
            color: #666;
            margin-top: 5px;
        }
        .history-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .history-table th,
        .history-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .history-table th {
            background: #f5f5f5;
            font-weight: bold;
        }
        .status-completed { color: #4CAF50; }
        .status-failed { color: #f44336; }
        .status-pending { color: #ff9800; }
        .timestamp {
            color: #666;
            font-size: 0.9em;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 智能编排系统 - 监控报告</h1>
""")
        
        html_parts.append(f"<div class='timestamp'>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>")
        
        if state:
            in_window = state.get('in_training_window', False)
            status_class = "status-card" if in_window else "status-card warning"
            html_parts.append(f"""
        <div class='{status_class}'>
            <h3>系统状态</h3>
            <p>训练窗口中: <strong>{'是' if in_window else '否'}</strong></p>
""")
            if state.get('training_window_start'):
                html_parts.append(f"<p>窗口开始: {state['training_window_start']}</p>")
            if state.get('training_window_end'):
                html_parts.append(f"<p>窗口结束: {state['training_window_end']}</p>")
            html_parts.append("</div>")
            
            if 'performance_metrics' in state:
                metrics = state['performance_metrics']
                total = metrics.get('total_tasks_executed', 0)
                success_rate = 0.0
                if total > 0:
                    success_rate = (metrics.get('tasks_success', 0) / total) * 100
                
                html_parts.append("<h2>性能指标</h2>")
                html_parts.append("<div class='metrics-grid'>")
                
                html_parts.append(f"""
            <div class='metric-card'>
                <div class='metric-value'>{total}</div>
                <div class='metric-label'>总任务数</div>
            </div>
            <div class='metric-card'>
                <div class='metric-value' style='color: #4CAF50;'>{metrics.get('tasks_success', 0)}</div>
                <div class='metric-label'>成功任务</div>
            </div>
            <div class='metric-card'>
                <div class='metric-value' style='color: #f44336;'>{metrics.get('tasks_failed', 0)}</div>
                <div class='metric-label'>失败任务</div>
            </div>
            <div class='metric-card'>
                <div class='metric-value'>{success_rate:.1f}%</div>
                <div class='metric-label'>成功率</div>
            </div>
""")
                html_parts.append("</div>")
        
        if history:
            html_parts.append("<h2>历史记录</h2>")
            html_parts.append("<table class='history-table'>")
            html_parts.append("<tr><th>任务名称</th><th>状态</th><th>重试次数</th><th>错误信息</th></tr>")
            
            for record in reversed(history[-20:]):
                status_class = f"status-{record.get('status', 'pending')}"
                error_text = record.get('error', '-')
                html_parts.append(f"""
            <tr>
                <td>{record.get('name', 'unknown')}</td>
                <td class='{status_class}'>{record.get('status', 'unknown')}</td>
                <td>{record.get('retries', 0)}</td>
                <td>{error_text}</td></tr>""")
            
            html_parts.append("</table>")
        
        html_parts.append("""
    </div>
</body>
</html>""")
        
        return "".join(html_parts)
    
    def save_report(self, output_dir: Optional[str] = None, format: str = "both"):
        """保存报告"""
        if output_dir:
            output_path = Path(output_dir)
        else:
            output_path = self.state_dir
        
        output_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format in ["text", "both"]:
            text_report = self.generate_text_report()
            text_file = output_path / f"orchestration_report_{timestamp}.txt"
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(text_report)
            print(f"文本报告已保存: {text_file}")
        
        if format in ["html", "both"]:
            html_report = self.generate_html_report()
            html_file = output_path / f"orchestration_report_{timestamp}.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_report)
            print(f"HTML报告已保存: {html_file}")
        
        print(f"报告目录: {output_path}")


def main():
    """主函数"""
    print("=" * 80)
    print("智能编排系统 - 性能监控工具")
    print("=" * 80)
    
    import argparse
    parser = argparse.ArgumentParser(description="智能编排系统监控工具")
    parser.add_argument("--state-dir", help="状态文件目录", default=None)
    parser.add_argument("--output-dir", help="报告输出目录", default=None)
    parser.add_argument("--format", choices=["text", "html", "both"], 
                       default="both", help="报告格式")
    parser.add_argument("--show", action="store_true", help="显示文本报告到控制台")
    
    args = parser.parse_args()
    
    monitor = OrchestrationMonitor(state_dir=args.state_dir)
    
    if args.show:
        print("\n" + monitor.generate_text_report() + "\n")
    
    monitor.save_report(output_dir=args.output_dir, format=args.format)
    
    print("\n监控报告生成完成！")


if __name__ == "__main__":
    main()
