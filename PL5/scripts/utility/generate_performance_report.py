#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能报告生成器 - PL5系统性能监控报告
功能：
1. 读取性能指标数据
2. 生成文本/HTML格式的性能报告
3. 性能趋势分析
4. 告警统计
5. 性能优化建议
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import statistics

# 添加项目根目录到路径
_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.config import BASE_DIR, LOGS_DIR

logger = logging.getLogger(__name__)


class PerformanceReportGenerator:
    """性能报告生成器"""
    
    # 性能目标
    PERFORMANCE_TARGETS = {
        'training_duration_sec': {'max': 300, 'unit': 's', 'name': '训练耗时'},
        'prediction_duration_sec': {'max': 30, 'unit': 's', 'name': '预测耗时'},
        'cpu_percent': {'max': 80, 'unit': '%', 'name': 'CPU使用率'},
        'memory_used_mb': {'max': 2048, 'unit': 'MB', 'name': '内存使用'},
        'cache_hit_rate': {'min': 30, 'unit': '%', 'name': '缓存命中率'},
    }
    
    def __init__(self, 
                 metrics_file: Optional[Path] = None,
                 alerts_file: Optional[Path] = None,
                 output_dir: Optional[Path] = None):
        """
        初始化报告生成器
        
        Args:
            metrics_file: 性能指标文件路径
            alerts_file: 告警记录文件路径
            output_dir: 报告输出目录
        """
        self.metrics_file = metrics_file or LOGS_DIR / "performance_metrics.jsonl"
        self.alerts_file = alerts_file or LOGS_DIR / "alerts.jsonl"
        self.output_dir = output_dir or BASE_DIR / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_data: List[Dict] = []
        self.alerts_data: List[Dict] = []
        
        logger.info(f"报告生成器初始化完成")
    
    def load_data(self, hours: int = 24) -> bool:
        """
        加载性能数据
        
        Args:
            hours: 加载最近多少小时的数据
        
        Returns:
            是否成功加载数据
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 加载性能指标
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            record_time = datetime.fromisoformat(record.get('timestamp', ''))
                            if record_time >= cutoff_time:
                                self.metrics_data.append(record)
                        except:
                            continue
                logger.info(f"已加载 {len(self.metrics_data)} 条性能指标记录")
            except Exception as e:
                logger.error(f"加载性能指标失败: {e}")
                return False
        else:
            logger.warning(f"性能指标文件不存在: {self.metrics_file}")
        
        # 加载告警记录
        if self.alerts_file.exists():
            try:
                with open(self.alerts_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            record_time = datetime.fromisoformat(record.get('created_at', ''))
                            if record_time >= cutoff_time:
                                self.alerts_data.append(record)
                        except:
                            continue
                logger.info(f"已加载 {len(self.alerts_data)} 条告警记录")
            except Exception as e:
                logger.error(f"加载告警记录失败: {e}")
        
        return len(self.metrics_data) > 0
    
    def analyze_metrics(self) -> Dict[str, Any]:
        """分析性能指标"""
        if not self.metrics_data:
            return {}
        
        analysis = {
            'period': {
                'start': self.metrics_data[0].get('timestamp'),
                'end': self.metrics_data[-1].get('timestamp'),
                'data_points': len(self.metrics_data)
            },
            'system': {},
            'training': {},
            'prediction': {},
            'cache': {},
            'trends': {}
        }
        
        # 系统指标分析
        cpu_values = [m.get('cpu_percent', 0) for m in self.metrics_data if m.get('cpu_percent') is not None]
        memory_values = [m.get('memory_used_mb', 0) for m in self.metrics_data if m.get('memory_used_mb') is not None]
        disk_values = [m.get('disk_percent', 0) for m in self.metrics_data if m.get('disk_percent') is not None]
        
        if cpu_values:
            analysis['system']['cpu'] = {
                'avg': round(statistics.mean(cpu_values), 2),
                'max': round(max(cpu_values), 2),
                'min': round(min(cpu_values), 2),
                'p95': round(self._percentile(cpu_values, 95), 2),
                'target_exceeded': sum(1 for v in cpu_values if v > self.PERFORMANCE_TARGETS['cpu_percent']['max']),
                'target_exceeded_pct': round(sum(1 for v in cpu_values if v > self.PERFORMANCE_TARGETS['cpu_percent']['max']) / len(cpu_values) * 100, 2)
            }
        
        if memory_values:
            analysis['system']['memory'] = {
                'avg_mb': round(statistics.mean(memory_values), 2),
                'max_mb': round(max(memory_values), 2),
                'min_mb': round(min(memory_values), 2),
                'p95_mb': round(self._percentile(memory_values, 95), 2),
                'target_exceeded': sum(1 for v in memory_values if v > self.PERFORMANCE_TARGETS['memory_used_mb']['max']),
                'target_exceeded_pct': round(sum(1 for v in memory_values if v > self.PERFORMANCE_TARGETS['memory_used_mb']['max']) / len(memory_values) * 100, 2)
            }
        
        if disk_values:
            analysis['system']['disk'] = {
                'avg': round(statistics.mean(disk_values), 2),
                'max': round(max(disk_values), 2)
            }
        
        # 训练性能分析
        training_times = [m.get('training_duration_sec') for m in self.metrics_data 
                         if m.get('training_duration_sec') is not None]
        if training_times:
            analysis['training'] = {
                'count': len(training_times),
                'avg_sec': round(statistics.mean(training_times), 2),
                'max_sec': round(max(training_times), 2),
                'min_sec': round(min(training_times), 2),
                'total_sec': round(sum(training_times), 2),
                'target_exceeded': sum(1 for v in training_times if v > self.PERFORMANCE_TARGETS['training_duration_sec']['max']),
                'target_met_pct': round(sum(1 for v in training_times if v <= self.PERFORMANCE_TARGETS['training_duration_sec']['max']) / len(training_times) * 100, 2)
            }
        
        # 预测性能分析
        prediction_times = [m.get('prediction_duration_sec') for m in self.metrics_data 
                           if m.get('prediction_duration_sec') is not None]
        if prediction_times:
            analysis['prediction'] = {
                'count': len(prediction_times),
                'avg_sec': round(statistics.mean(prediction_times), 3),
                'max_sec': round(max(prediction_times), 3),
                'min_sec': round(min(prediction_times), 3),
                'target_exceeded': sum(1 for v in prediction_times if v > self.PERFORMANCE_TARGETS['prediction_duration_sec']['max']),
                'target_met_pct': round(sum(1 for v in prediction_times if v <= self.PERFORMANCE_TARGETS['prediction_duration_sec']['max']) / len(prediction_times) * 100, 2)
            }
        
        # 缓存分析
        cache_rates = [m.get('cache_hit_rate') for m in self.metrics_data 
                      if m.get('cache_hit_rate') is not None]
        if cache_rates:
            analysis['cache'] = {
                'avg_rate': round(statistics.mean(cache_rates), 2),
                'min_rate': round(min(cache_rates), 2),
                'target_missed': sum(1 for v in cache_rates if v < self.PERFORMANCE_TARGETS['cache_hit_rate']['min']),
                'target_met_pct': round(sum(1 for v in cache_rates if v >= self.PERFORMANCE_TARGETS['cache_hit_rate']['min']) / len(cache_rates) * 100, 2)
            }
        
        # 计算趋势（简单线性趋势）
        if len(cpu_values) >= 10:
            analysis['trends']['cpu'] = self._calculate_trend(cpu_values)
        if len(memory_values) >= 10:
            analysis['trends']['memory'] = self._calculate_trend(memory_values)
        
        return analysis
    
    def analyze_alerts(self) -> Dict[str, Any]:
        """分析告警数据"""
        if not self.alerts_data:
            return {'count': 0}
        
        analysis = {
            'count': len(self.alerts_data),
            'by_severity': defaultdict(int),
            'by_rule': defaultdict(int),
            'by_status': defaultdict(int),
            'active': 0,
            'resolved': 0
        }
        
        for alert in self.alerts_data:
            analysis['by_severity'][alert.get('severity', 'unknown')] += 1
            analysis['by_rule'][alert.get('rule_id', 'unknown')] += 1
            analysis['by_status'][alert.get('status', 'unknown')] += 1
            
            if alert.get('status') == 'active':
                analysis['active'] += 1
            elif alert.get('status') == 'resolved':
                analysis['resolved'] += 1
        
        # 转换为普通dict
        analysis['by_severity'] = dict(analysis['by_severity'])
        analysis['by_rule'] = dict(analysis['by_rule'])
        analysis['by_status'] = dict(analysis['by_status'])
        
        return analysis
    
    def generate_recommendations(self, metrics_analysis: Dict, alerts_analysis: Dict) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # CPU相关建议
        if 'cpu' in metrics_analysis.get('system', {}):
            cpu_data = metrics_analysis['system']['cpu']
            if cpu_data.get('target_exceeded_pct', 0) > 20:
                recommendations.append(
                    f"⚠️ CPU使用率超过阈值的时间占比 {cpu_data['target_exceeded_pct']}%，"
                    f"建议优化特征工程并行度或降低模型复杂度"
                )
            if cpu_data.get('avg', 0) > 70:
                recommendations.append(
                    f"📊 平均CPU使用率 {cpu_data['avg']}% 较高，"
                    f"建议检查是否有不必要的后台任务"
                )
        
        # 内存相关建议
        if 'memory' in metrics_analysis.get('system', {}):
            memory_data = metrics_analysis['system']['memory']
            if memory_data.get('target_exceeded_pct', 0) > 10:
                recommendations.append(
                    f"⚠️ 内存使用超过1.8GB的时间占比 {memory_data['target_exceeded_pct']}%，"
                    f"建议优化数据加载策略或增加内存清理频率"
                )
            if memory_data.get('p95_mb', 0) > 1900:
                recommendations.append(
                    f"🚨 内存使用P95值达到 {memory_data['p95_mb']}MB，"
                    f"接近2GB上限，建议立即优化内存使用"
                )
        
        # 训练性能建议
        if 'training' in metrics_analysis:
            training_data = metrics_analysis['training']
            if training_data.get('target_met_pct', 100) < 90:
                recommendations.append(
                    f"⏱️ 仅 {training_data['target_met_pct']}% 的训练在5分钟内完成，"
                    f"建议启用快速训练模式或减少特征数量"
                )
            if training_data.get('avg_sec', 0) > 240:
                recommendations.append(
                    f"📈 平均训练耗时 {training_data['avg_sec']}秒 接近阈值，"
                    f"建议检查特征工程性能"
                )
        
        # 预测性能建议
        if 'prediction' in metrics_analysis:
            prediction_data = metrics_analysis['prediction']
            if prediction_data.get('target_met_pct', 100) < 95:
                recommendations.append(
                    f"⏱️ 仅 {prediction_data['target_met_pct']}% 的预测在30秒内完成，"
                    f"建议优化模型推理速度或启用预测缓存"
                )
        
        # 缓存建议
        if 'cache' in metrics_analysis:
            cache_data = metrics_analysis['cache']
            if cache_data.get('target_met_pct', 100) < 50:
                recommendations.append(
                    f"💾 缓存命中率仅 {cache_data['avg_rate']}%，"
                    f"建议增加缓存预热或调整缓存策略"
                )
        
        # 告警相关建议
        if alerts_analysis.get('count', 0) > 10:
            recommendations.append(
                f"🚨 最近24小时内产生 {alerts_analysis['count']} 条告警，"
                f"建议检查系统稳定性"
            )
        
        if not recommendations:
            recommendations.append("✅ 系统性能良好，暂无优化建议")
        
        return recommendations
    
    def generate_text_report(self, hours: int = 24) -> str:
        """生成文本格式报告"""
        if not self.load_data(hours):
            return "错误: 无法加载性能数据"
        
        metrics_analysis = self.analyze_metrics()
        alerts_analysis = self.analyze_alerts()
        recommendations = self.generate_recommendations(metrics_analysis, alerts_analysis)
        
        lines = []
        lines.append("=" * 80)
        lines.append("PL5系统性能监控报告")
        lines.append("=" * 80)
        lines.append(f"生成时间: {datetime.now().isoformat()}")
        lines.append(f"数据周期: 最近{hours}小时")
        lines.append("")
        
        # 系统资源
        lines.append("【系统资源】")
        if 'cpu' in metrics_analysis.get('system', {}):
            cpu = metrics_analysis['system']['cpu']
            lines.append(f"  CPU使用率:")
            lines.append(f"    - 平均: {cpu['avg']}% (目标: <{self.PERFORMANCE_TARGETS['cpu_percent']['max']}%)")
            lines.append(f"    - 峰值: {cpu['max']}%")
            lines.append(f"    - P95: {cpu['p95']}%")
            lines.append(f"    - 超标次数: {cpu['target_exceeded']} ({cpu['target_exceeded_pct']}%)")
        
        if 'memory' in metrics_analysis.get('system', {}):
            memory = metrics_analysis['system']['memory']
            lines.append(f"  内存使用:")
            lines.append(f"    - 平均: {memory['avg_mb']} MB (目标: <{self.PERFORMANCE_TARGETS['memory_used_mb']['max']}MB)")
            lines.append(f"    - 峰值: {memory['max_mb']} MB")
            lines.append(f"    - P95: {memory['p95_mb']} MB")
            lines.append(f"    - 超标次数: {memory['target_exceeded']} ({memory['target_exceeded_pct']}%)")
        
        lines.append("")
        
        # 训练性能
        if 'training' in metrics_analysis:
            training = metrics_analysis['training']
            lines.append("【训练性能】")
            lines.append(f"  训练次数: {training['count']}")
            lines.append(f"  平均耗时: {training['avg_sec']}秒 (目标: <{self.PERFORMANCE_TARGETS['training_duration_sec']['max']}秒)")
            lines.append(f"  最大耗时: {training['max_sec']}秒")
            lines.append(f"  达标率: {training['target_met_pct']}%")
            lines.append("")
        
        # 预测性能
        if 'prediction' in metrics_analysis:
            prediction = metrics_analysis['prediction']
            lines.append("【预测性能】")
            lines.append(f"  预测次数: {prediction['count']}")
            lines.append(f"  平均耗时: {prediction['avg_sec']}秒 (目标: <{self.PERFORMANCE_TARGETS['prediction_duration_sec']['max']}秒)")
            lines.append(f"  最大耗时: {prediction['max_sec']}秒")
            lines.append(f"  达标率: {prediction['target_met_pct']}%")
            lines.append("")
        
        # 缓存性能
        if 'cache' in metrics_analysis:
            cache = metrics_analysis['cache']
            lines.append("【缓存性能】")
            lines.append(f"  平均命中率: {cache['avg_rate']}% (目标: >{self.PERFORMANCE_TARGETS['cache_hit_rate']['min']}%)")
            lines.append(f"  最低命中率: {cache['min_rate']}%")
            lines.append(f"  达标率: {cache['target_met_pct']}%")
            lines.append("")
        
        # 告警统计
        lines.append("【告警统计】")
        lines.append(f"  告警总数: {alerts_analysis['count']}")
        if alerts_analysis['count'] > 0:
            lines.append(f"  活跃告警: {alerts_analysis['active']}")
            lines.append(f"  已解决: {alerts_analysis['resolved']}")
            lines.append("  按级别分布:")
            for severity, count in alerts_analysis.get('by_severity', {}).items():
                lines.append(f"    - {severity}: {count}")
        lines.append("")
        
        # 优化建议
        lines.append("【优化建议】")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")
        
        # 趋势分析
        if 'trends' in metrics_analysis and metrics_analysis['trends']:
            lines.append("【趋势分析】")
            for metric, trend in metrics_analysis['trends'].items():
                trend_str = "上升" if trend > 0.01 else ("下降" if trend < -0.01 else "平稳")
                lines.append(f"  {metric}: {trend_str} (趋势值: {trend:+.4f})")
            lines.append("")
        
        lines.append("=" * 80)
        lines.append("报告生成完成")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def generate_html_report(self, hours: int = 24) -> str:
        """生成HTML格式报告"""
        if not self.load_data(hours):
            return "<html><body><h1>错误: 无法加载性能数据</h1></body></html>"
        
        metrics_analysis = self.analyze_metrics()
        alerts_analysis = self.analyze_alerts()
        recommendations = self.generate_recommendations(metrics_analysis, alerts_analysis)
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PL5系统性能监控报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header .meta {{
            opacity: 0.9;
            margin-top: 10px;
        }}
        .card {{
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .card h2 {{
            margin-top: 0;
            color: #667eea;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 10px;
        }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .metric-box {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .metric-box.warning {{
            border-left-color: #ffc107;
        }}
        .metric-box.danger {{
            border-left-color: #dc3545;
        }}
        .metric-box.success {{
            border-left-color: #28a745;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        .metric-label {{
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .recommendations {{
            list-style: none;
            padding: 0;
        }}
        .recommendations li {{
            padding: 15px;
            margin-bottom: 10px;
            background: #f8f9fa;
            border-radius: 5px;
            border-left: 4px solid #ffc107;
        }}
        .recommendations li.success {{
            border-left-color: #28a745;
            background: #d4edda;
        }}
        .recommendations li.warning {{
            border-left-color: #ffc107;
            background: #fff3cd;
        }}
        .recommendations li.danger {{
            border-left-color: #dc3545;
            background: #f8d7da;
        }}
        .alert-badge {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
        }}
        .alert-badge.critical {{
            background: #dc3545;
            color: white;
        }}
        .alert-badge.warning {{
            background: #ffc107;
            color: #333;
        }}
        .alert-badge.info {{
            background: #17a2b8;
            color: white;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 PL5系统性能监控报告</h1>
        <div class="meta">
            生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
            数据周期: 最近{hours}小时
        </div>
    </div>
"""
        
        # 系统资源卡片
        html += """
    <div class="card">
        <h2>🖥️ 系统资源</h2>
        <div class="metric-grid">
"""
        
        if 'cpu' in metrics_analysis.get('system', {}):
            cpu = metrics_analysis['system']['cpu']
            cpu_status = 'danger' if cpu['avg'] > 80 else ('warning' if cpu['avg'] > 60 else 'success')
            html += f"""
            <div class="metric-box {cpu_status}">
                <div class="metric-value">{cpu['avg']}%</div>
                <div class="metric-label">平均CPU使用率</div>
                <div style="margin-top:10px;font-size:0.85em;color:#666;">
                    峰值: {cpu['max']}% | 超标: {cpu['target_exceeded_pct']}%
                </div>
            </div>
"""
        
        if 'memory' in metrics_analysis.get('system', {}):
            memory = metrics_analysis['system']['memory']
            mem_status = 'danger' if memory['avg_mb'] > 1800 else ('warning' if memory['avg_mb'] > 1500 else 'success')
            html += f"""
            <div class="metric-box {mem_status}">
                <div class="metric-value">{memory['avg_mb']:.0f}</div>
                <div class="metric-label">平均内存使用 (MB)</div>
                <div style="margin-top:10px;font-size:0.85em;color:#666;">
                    峰值: {memory['max_mb']:.0f}MB | 超标: {memory['target_exceeded_pct']}%
                </div>
            </div>
"""
        
        html += """
        </div>
    </div>
"""
        
        # 性能指标卡片
        html += """
    <div class="card">
        <h2>⚡ 性能指标</h2>
        <div class="metric-grid">
"""
        
        if 'training' in metrics_analysis:
            training = metrics_analysis['training']
            train_status = 'danger' if training['target_met_pct'] < 70 else ('warning' if training['target_met_pct'] < 90 else 'success')
            html += f"""
            <div class="metric-box {train_status}">
                <div class="metric-value">{training['avg_sec']:.1f}s</div>
                <div class="metric-label">平均训练耗时</div>
                <div style="margin-top:10px;font-size:0.85em;color:#666;">
                    次数: {training['count']} | 达标率: {training['target_met_pct']}%
                </div>
            </div>
"""
        
        if 'prediction' in metrics_analysis:
            prediction = metrics_analysis['prediction']
            pred_status = 'danger' if prediction['target_met_pct'] < 90 else ('warning' if prediction['target_met_pct'] < 95 else 'success')
            html += f"""
            <div class="metric-box {pred_status}">
                <div class="metric-value">{prediction['avg_sec']:.2f}s</div>
                <div class="metric-label">平均预测耗时</div>
                <div style="margin-top:10px;font-size:0.85em;color:#666;">
                    次数: {prediction['count']} | 达标率: {prediction['target_met_pct']}%
                </div>
            </div>
"""
        
        if 'cache' in metrics_analysis:
            cache = metrics_analysis['cache']
            cache_status = 'danger' if cache['avg_rate'] < 30 else ('warning' if cache['avg_rate'] < 50 else 'success')
            html += f"""
            <div class="metric-box {cache_status}">
                <div class="metric-value">{cache['avg_rate']:.1f}%</div>
                <div class="metric-label">缓存命中率</div>
                <div style="margin-top:10px;font-size:0.85em;color:#666;">
                    最低: {cache['min_rate']:.1f}% | 达标率: {cache['target_met_pct']}%
                </div>
            </div>
"""
        
        html += """
        </div>
    </div>
"""
        
        # 告警统计
        html += f"""
    <div class="card">
        <h2>🚨 告警统计</h2>
        <div style="font-size:1.2em;margin-bottom:20px;">
            总告警数: <strong>{alerts_analysis['count']}</strong>
            {"| 活跃: " + str(alerts_analysis['active']) if alerts_analysis['active'] > 0 else ""}
        </div>
"""
        
        if alerts_analysis.get('by_severity'):
            html += """
        <table>
            <thead>
                <tr>
                    <th>级别</th>
                    <th>数量</th>
                    <th>占比</th>
                </tr>
            </thead>
            <tbody>
"""
            for severity, count in alerts_analysis['by_severity'].items():
                pct = count / alerts_analysis['count'] * 100
                badge_class = 'critical' if severity == 'critical' else ('warning' if severity == 'warning' else 'info')
                html += f"""
                <tr>
                    <td><span class="alert-badge {badge_class}">{severity.upper()}</span></td>
                    <td>{count}</td>
                    <td>{pct:.1f}%</td>
                </tr>
"""
            html += """
            </tbody>
        </table>
"""
        
        html += """
    </div>
"""
        
        # 优化建议
        html += """
    <div class="card">
        <h2>💡 优化建议</h2>
        <ul class="recommendations">
"""
        
        for rec in recommendations:
            rec_class = 'success' if '✅' in rec else ('danger' if '🚨' in rec else 'warning')
            html += f"""
            <li class="{rec_class}">{rec}</li>
"""
        
        html += """
        </ul>
    </div>
"""
        
        # 页脚
        html += f"""
    <div class="footer">
        <p>PL5智能预测系统 | 性能监控报告</p>
        <p>报告路径: {self.output_dir}</p>
    </div>
</body>
</html>
"""
        
        return html
    
    def save_report(self, hours: int = 24, format: str = 'both') -> Dict[str, Path]:
        """
        生成并保存报告
        
        Args:
            hours: 数据时间范围
            format: 报告格式 ('text', 'html', 'both')
        
        Returns:
            生成的文件路径字典
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_files = {}
        
        if format in ('text', 'both'):
            text_report = self.generate_text_report(hours)
            text_path = self.output_dir / f"performance_report_{timestamp}.txt"
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text_report)
            saved_files['text'] = text_path
            logger.info(f"文本报告已保存: {text_path}")
        
        if format in ('html', 'both'):
            html_report = self.generate_html_report(hours)
            html_path = self.output_dir / f"performance_report_{timestamp}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_report)
            saved_files['html'] = html_path
            logger.info(f"HTML报告已保存: {html_path}")
        
        return saved_files
    
    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """计算百分位数"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    @staticmethod
    def _calculate_trend(values: List[float]) -> float:
        """计算简单线性趋势"""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)
        
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator


def main():
    """主函数 - 命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PL5系统性能报告生成器')
    parser.add_argument('--hours', type=int, default=24, help='数据时间范围（小时）')
    parser.add_argument('--format', choices=['text', 'html', 'both'], default='both', help='报告格式')
    parser.add_argument('--output', type=str, help='输出目录')
    parser.add_argument('--print', action='store_true', help='打印文本报告到控制台')
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建生成器
    output_dir = Path(args.output) if args.output else None
    generator = PerformanceReportGenerator(output_dir=output_dir)
    
    # 生成报告
    if args.print:
        text_report = generator.generate_text_report(args.hours)
        print(text_report)
    else:
        saved_files = generator.save_report(args.hours, args.format)
        print("\n报告生成完成:")
        for format_type, file_path in saved_files.items():
            print(f"  [{format_type.upper()}] {file_path}")


if __name__ == "__main__":
    main()
