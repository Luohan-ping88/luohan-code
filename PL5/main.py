#!/usr/bin/env python
"""
PL5 V10.3 主程序 - 统一入口
整合传统编排器和Agent编排器，支持6模型融合预测

用法:
  python main.py train          # 执行训练流程
  python main.py predict        # 执行预测流程
  python main.py analyze        # 执行分析并发送邮件
  python main.py schedule       # 启动自动调度器
  python main.py schedule --once # 执行单次完整流程
  python main.py status         # 查看系统状态
  python main.py --help         # 显示帮助
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.utils.logger import logger


def check_environment():
    """检查运行环境"""
    checks = {
        'python_version': sys.version_info >= (3, 8),
        'data_dir': Path('data').exists(),
        'models_dir': Path('models').exists(),
        'logs_dir': Path('logs').exists(),
        'config_dir': Path('config').exists(),   # 【修复BUG-M02】src/config → config/
    }

    all_passed = all(checks.values())

    if not all_passed:
        logger.warning("环境检查未通过:")
        for name, passed in checks.items():
            if not passed:
                logger.warning(f"  {name}: FAIL")

        if not checks['data_dir']:
            Path('data/raw').mkdir(parents=True, exist_ok=True)
            Path('data/processed').mkdir(parents=True, exist_ok=True)
            logger.info("  已自动创建 data 目录")

        if not checks['models_dir']:
            Path('models').mkdir(parents=True, exist_ok=True)
            logger.info("  已自动创建 models 目录")

        if not checks['logs_dir']:
            Path('logs').mkdir(parents=True, exist_ok=True)
            logger.info("  已自动创建 logs 目录")

    return True


def cmd_train(args):
    """执行训练流程"""
    logger.info("=" * 60)
    logger.info("PL5 V10.3 训练流程")
    logger.info("=" * 60)

    from src.core.data.collector import PL5DataCollector
    from src.core.features.engineer import FeatureEngineer
    from src.core.models.enhanced_predictor import EnhancedPL5Predictor

    collector = PL5DataCollector()
    df = collector.update_data()
    if df is None or len(df) == 0:
        logger.error("无法加载数据")
        return False
    logger.info(f"数据加载完成: {len(df)} 条记录, 最新期号: {df['period'].iloc[-1]}")

    engineer = FeatureEngineer()
    # 与 scheduler 训练路径保持一致：不限制 select_top，确保模型的 76 个训练特征全部存在
    df_features = engineer.extract_all_features(df, select_top=None)
    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    # 确保排除所有非数值列，包括date
    feature_cols = [c for c in df_features.columns
                   if c not in ['period', 'full_number', 'date'] + positions]
    logger.info(f"特征工程完成: {len(feature_cols)} 个特征")

    predictor = EnhancedPL5Predictor()
    start = datetime.now()
    predictor.fit(df_features, feature_cols, parallel=not args.sequential)
    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"训练完成, 耗时: {elapsed:.1f}s")

    predictor.save_models()
    logger.info("模型已保存")

    import json
    training_info = {
        'model_version': 'V10.3',
        'training_time': elapsed,
        'feature_count': len(feature_cols),
        'data_count': len(df),
        'latest_period': str(df['period'].iloc[-1]),
        'training_status': 'SUCCESS',
        'models': {
            'stacking': True,
            'hmm': bool(predictor.hmm_models),
            'copula': predictor.copula_model is not None,
            'bsts': bool(predictor.bsts_models),
            'mamba': predictor.mamba_predictor is not None,
            'itransformer': predictor.itransformer_predictor is not None,
            'bayesian_quantifier': predictor.bayesian_quantifier is not None,
        }
    }
    from src.core.config import LOGS_DIR
    training_info_path = LOGS_DIR / 'training_info.json'
    with open(training_info_path, 'w', encoding='utf-8') as f:
        json.dump(training_info, f, indent=2, ensure_ascii=False)
    logger.info(f"训练信息已保存: {training_info_path}")

    return True


def cmd_predict(args):
    """执行预测流程"""
    logger.info("=" * 60)
    logger.info("PL5 V10.3 预测流程")
    logger.info("=" * 60)

    from src.core.data.collector import PL5DataCollector
    from src.core.features.engineer import FeatureEngineer
    from src.core.models.enhanced_predictor import EnhancedPL5Predictor

    collector = PL5DataCollector()
    df = collector.update_data()
    if df is None or len(df) == 0:
        logger.error("无法加载数据")
        return False

    engineer = FeatureEngineer()
    # 【关键修复】predict 时不限制 select_top，让 df_features 包含全量特征，
    # 保证模型的 76 个训练特征全部存在（避免 RFE 选出 top-100 而遗漏部分训练特征）
    df_features = engineer.extract_all_features(df, select_top=None)

    predictor = EnhancedPL5Predictor()
    model_loaded = predictor.load_models()

    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    if not model_loaded:
        logger.warning("未找到已训练模型，执行即时训练...")
        feature_cols = [c for c in df_features.columns
                       if c not in ['period', 'full_number'] + positions]
        predictor.fit(df_features, feature_cols, parallel=False)
        predictor.save_models()
        latest_features = df_features[feature_cols].iloc[-1].values
    else:
        # 【关键修复】使用模型训练时保存的 feature_cols，避免 RFE 漂移
        if predictor.feature_cols and len(predictor.feature_cols) > 0:
            missing = [c for c in predictor.feature_cols if c not in df_features.columns]
            if missing:
                logger.warning(f"模型特征列中有 {len(missing)} 个缺失，重新提取特征")
                feature_cols = [c for c in df_features.columns
                               if c not in ['period', 'full_number'] + positions]
            else:
                feature_cols = predictor.feature_cols
                logger.info(f"[cmd_predict] 使用模型训练时的 {len(feature_cols)} 个特征列（特征漂移已修复）")
            latest_features = df_features[feature_cols].iloc[-1].values
        else:
            feature_cols = [c for c in df_features.columns
                           if c not in ['period', 'full_number'] + positions]
            latest_features = df_features[feature_cols].iloc[-1].values
    recent_data = {pos: df[pos].values for pos in positions}
    predictions = predictor.predict(latest_features, recent_data, top_k=8)

    position_names = {'wan': '万位', 'qian': '千位', 'bai': '百位', 'shi': '十位', 'ge': '个位'}
    logger.info("\n预测结果:")
    for pos in positions:
        pred = predictions[pos]
        weights = pred.get('weights_used', {})
        logger.info(f"  {position_names[pos]}: Top-8={pred['top_k']}, Top-3={pred['top_k'][:3]}")
        if weights:
            w_str = ', '.join([f"{k}={v:.2f}" for k, v in weights.items()])
            logger.info(f"    权重: [{w_str}]")

    import json
    from src.core.config import RESULTS_DIR
    last_period = int(df['period'].iloc[-1])
    next_period = str(last_period + 1)
    result_path = RESULTS_DIR / f"prediction_{next_period}.json"
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump({
            'period': next_period,
            'predictions': {pos: predictions[pos] for pos in positions},
            'timestamp': datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"预测结果已保存: {result_path}")

    return True


def cmd_analyze(args):
    """执行分析并发送邮件"""
    logger.info("=" * 60)
    logger.info("PL5 V10.3 分析与邮件发送")
    logger.info("=" * 60)

    from src.app.analyze_and_send import analyze_and_send
    result = analyze_and_send()

    if result:
        logger.info("分析完成，邮件已发送")
        return True
    else:
        logger.error("分析失败")
        return False


def cmd_schedule(args):
    """启动自动调度器"""
    logger.info("=" * 60)
    logger.info("PL5 V10.3 自动调度器")
    logger.info("=" * 60)

    from src.app.auto_scheduler_v8 import AutoSchedulerV8

    scheduler = AutoSchedulerV8()
    logger.info("调度器已初始化")

    if args.once:
        logger.info("执行单次完整流程 (run_full_pipeline)...")
        # 【修复BUG-M01】原代码调用了不存在的 task_data_update/task_report 方法；
        # 正确做法是调用 run_full_pipeline()，它会依序执行完整的佐证链
        success = scheduler.run_full_pipeline()
        logger.info(f"单次流程执行{'成功' if success else '失败'}")
        return success

    logger.info("启动定时调度模式...")
    logger.info("按 Ctrl+C 停止调度器")

    try:
        # 调用AutoSchedulerV8的run()方法启动真正的调度器
        scheduler.run()
    except KeyboardInterrupt:
        logger.info("调度器已停止")

    return True


def cmd_status(args):
    """查看系统状态"""
    logger.info("=" * 60)
    logger.info("PL5 V10.3 系统状态")
    logger.info("=" * 60)

    import json

    data_version_path = Path('models/data_version.json')
    if data_version_path.exists():
        with open(data_version_path, 'r', encoding='utf-8') as f:
            dv = json.load(f)
        logger.info(f"数据版本: {dv.get('version', 'N/A')}")
        logger.info(f"  最新期号: {dv.get('latest_period', 'N/A')}")
        logger.info(f"  记录数量: {dv.get('record_count', 'N/A')}")
        logger.info(f"  更新时间: {dv.get('last_update', 'N/A')}")
    else:
        logger.warning("数据版本信息未找到")

    training_info_path = Path('logs/training_info.json')
    if training_info_path.exists():
        with open(training_info_path, 'r', encoding='utf-8') as f:
            ti = json.load(f)
        logger.info(f"\n训练信息:")
        logger.info(f"  模型版本: {ti.get('model_version', 'N/A')}")
        logger.info(f"  训练状态: {ti.get('training_status', 'N/A')}")
        logger.info(f"  训练时间: {ti.get('training_time', 0):.1f}s")
        logger.info(f"  特征数量: {ti.get('feature_count', 'N/A')}")
        logger.info(f"  数据数量: {ti.get('data_count', 'N/A')}")
        logger.info(f"  最新期号: {ti.get('latest_period', 'N/A')}")
        models = ti.get('models', {})
        if models:
            logger.info(f"  模型状态:")
            for name, active in models.items():
                logger.info(f"    {name}: {'已启用' if active else '未启用'}")
    else:
        logger.warning("训练信息未找到")

    model_files = list(Path('models').glob('*.pkl'))
    logger.info(f"\n模型文件: {len(model_files)} 个")
    for mf in sorted(model_files)[-5:]:
        size_mb = mf.stat().st_size / 1024 / 1024
        logger.info(f"  {mf.name} ({size_mb:.1f}MB)")

    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='PL5 V10.3 排列五智能预测系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py train              # 执行训练
  python main.py train --sequential # 顺序训练(不并行)
  python main.py predict            # 执行预测
  python main.py analyze            # 分析并发送邮件
  python main.py schedule           # 启动调度器
  python main.py schedule --once    # 执行单次完整流程
  python main.py status             # 查看系统状态
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    train_parser = subparsers.add_parser('train', help='执行训练流程')
    train_parser.add_argument('--sequential', action='store_true',
                             help='顺序训练(不使用并行)')

    subparsers.add_parser('predict', help='执行预测流程')
    subparsers.add_parser('analyze', help='分析并发送邮件')

    schedule_parser = subparsers.add_parser('schedule', help='启动自动调度器')
    schedule_parser.add_argument('--once', action='store_true',
                                help='执行单次完整流程后退出')

    subparsers.add_parser('status', help='查看系统状态')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    check_environment()

    commands = {
        'train': cmd_train,
        'predict': cmd_predict,
        'analyze': cmd_analyze,
        'schedule': cmd_schedule,
        'status': cmd_status,
    }

    try:
        result = commands[args.command](args)
        return 0 if result else 1
    except KeyboardInterrupt:
        logger.info("用户中断程序")
        return 0
    except Exception as e:
        logger.error(f"程序执行异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
