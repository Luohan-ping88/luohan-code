#!/usr/bin/env python3
"""快速训练脚本 - 直接执行模型训练，跳过所有慢速流水线步骤"""
import sys
import time
import logging
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.monitoring.performance_monitor import PerformanceMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
    handlers=[
        logging.FileHandler('logs/quick_train.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('quick_train')

def main():
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("快速训练开始")
    logger.info("=" * 60)
    
    # Step 1: 加载数据
    logger.info("[1/3] 加载数据...")
    collector = PL5DataCollector()
    df = collector.load_processed_data()
    if df is None:
        df = collector.update_data()
    logger.info(f"  数据加载完成: {len(df)} 条记录")
    
    # Step 2: 特征工程
    logger.info("[2/3] 特征工程...")
    engineer = FeatureEngineer()
    
    # 使用缓存的特征配置
    config_path = Path('logs/best_feature_config.json')
    if config_path.exists():
        import json
        with open(config_path) as f:
            config_data = json.load(f)
        best_config = config_data.get('best_config', {})
        select_top = best_config.get('select_top', 50)  # 默认为50避免超时
        method = best_config.get('feature_selection_method', 'model_based')
        logger.info(f"  使用缓存特征配置: select_top={select_top}, method={method}")
    else:
        select_top = 50
        method = 'model_based'
        logger.info("  使用默认特征配置(select_top=50, model_based)")
    
    df_features = engineer.extract_all_features(
        df,
        select_top=select_top,
        feature_selection_method=method
    )
    
    feature_cols = [col for col in df_features.columns 
                   if col not in ['period', 'date', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge']]
    logger.info(f"  特征提取完成: {len(feature_cols)} 个特征")
    
    # Step 3: 训练模型
    logger.info("[3/3] 训练模型...")
    predictor = EnhancedPL5Predictor()
    
    # 监控性能
    perf_mon = PerformanceMonitor()
    
    predictor.fit(df_features, feature_cols)
    
    elapsed_total = time.time() - start_time
    logger.info("  保存模型...")
    predictor.save_models(
        performance_metrics={"training_time": elapsed_total, "feature_count": len(feature_cols)},
        training_samples=len(df_features)
    )
    logger.info(f"  模型已保存: models/enhanced_predictor_v10.pkl")
    
    logger.info("=" * 60)
    logger.info(f"训练完成！总耗时: {elapsed_total:.1f} 秒")
    logger.info("=" * 60)
    
    # 性能摘要
    perf_summary = perf_mon.get_performance_summary()
    if perf_summary:
        logger.info(f"CPU: {perf_summary.get('cpu_percent', 'N/A')}")
        logger.info(f"内存: {perf_summary.get('memory_percent', 'N/A')}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
