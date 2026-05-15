#!/usr/bin/env python3
"""
PL5 日循环训练任务执行器
每天自动执行训练、推理和性能评估
"""

import os
import sys
import time
import json
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

PROJECT_ROOT = Path("/workspace/PL5")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

LOG_DIR = PROJECT_ROOT / "logs" / "daily_training"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class DailyTrainingExecutor:
    """日循环训练任务执行器"""

    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = LOG_DIR / f"training_{self.timestamp}.log"
        self.report_file = LOG_DIR / f"report_{self.timestamp}.json"
        self.setup_logging()
        self.results = {
            "start_time": datetime.now().isoformat(),
            "training_cycles": 0,
            "total_predictions": 0,
            "success": True,
            "errors": [],
            "performance_metrics": []
        }

    def setup_logging(self):
        """设置日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger("DailyTraining")

    def log_section(self, title: str):
        """记录章节"""
        line = "=" * 80
        self.logger.info(line)
        self.logger.info(f"  {title}")
        self.logger.info(line)

    def load_data(self) -> Any:
        """加载训练数据"""
        self.log_section("1. 加载数据")
        try:
            from src.core.data.collector import PL5DataCollectorV8
            collector = PL5DataCollectorV8()

            self.logger.info("检查新数据...")
            data = collector.update_data()
            if data is None:
                self.logger.info("没有新数据，使用现有数据")
                data = collector.load_processed_data()

            if data is None or len(data) == 0:
                raise ValueError("无法加载数据")

            self.logger.info(f"✓ 数据加载完成: {len(data)} 条记录")
            self.logger.info(f"  最新期号: {data['period'].iloc[-1]}")
            self.logger.info(f"  数据时间范围: {data['date'].min()} ~ {data['date'].max()}")
            return data
        except Exception as e:
            self.logger.error(f"✗ 数据加载失败: {e}")
            self.logger.error(traceback.format_exc())
            self.results["errors"].append(f"数据加载失败: {e}")
            return None

    def extract_features(self, data: Any) -> Any:
        """提取特征"""
        self.log_section("2. 特征工程")
        try:
            from src.core.features.engineer import FeatureEngineer
            engineer = FeatureEngineer()

            self.logger.info("提取特征中...")
            features = engineer.extract_all_features(data)

            non_feature_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date']
            feature_cols = [col for col in features.columns if col not in non_feature_cols]

            self.logger.info(f"✓ 特征提取完成: {len(features.columns)} 个特征列")
            self.logger.info(f"  有效特征列: {len(feature_cols)} 个")
            self.logger.info(f"  样本数: {len(features)}")
            return features, feature_cols
        except Exception as e:
            self.logger.error(f"✗ 特征提取失败: {e}")
            self.logger.error(traceback.format_exc())
            self.results["errors"].append(f"特征提取失败: {e}")
            return None, None

    def train_model(self, features: Any, feature_cols: List[str]) -> Any:
        """训练模型"""
        self.log_section("3. 模型训练")
        try:
            from src.core.models.predictor import PL5Predictor
            import time

            predictor = PL5Predictor()

            self.logger.info("开始训练模型...")
            start_time = time.time()

            predictor.train(features, feature_cols)

            elapsed = time.time() - start_time

            self.logger.info(f"✓ 训练完成! 耗时: {elapsed:.2f}秒")
            self.logger.info(f"  模型状态: 已训练 = {predictor.is_trained}")

            if hasattr(predictor, 'stacking') and predictor.stacking:
                self.logger.info("  Stacking集成模型已就绪")

            if hasattr(predictor, 'hmm_models') and predictor.hmm_models:
                self.logger.info(f"  HMM模型数量: {len(predictor.hmm_models)}")

            return predictor
        except Exception as e:
            self.logger.error(f"✗ 模型训练失败: {e}")
            self.logger.error(traceback.format_exc())
            self.results["errors"].append(f"模型训练失败: {e}")
            return None

    def evaluate_model(self, predictor: Any, features: Any, feature_cols: List[str]) -> Dict[str, Any]:
        """评估模型"""
        self.log_section("4. 模型评估")
        try:
            from src.core.models.model_evaluator import ModelEvaluator
            import time

            evaluator = ModelEvaluator()

            self.logger.info("评估模型性能...")

            metrics = {}
            if len(features) >= 10:
                train_size = int(len(features) * 0.8)
                train_data = features.iloc[:train_size]
                test_data = features.iloc[train_size:]

                self.logger.info(f"训练集: {train_size} 样本")
                self.logger.info(f"测试集: {len(test_data)} 样本")

                predictor.train(train_data, feature_cols)

                correct = 0
                total = 0
                for idx in range(len(test_data)):
                    sample = test_data.iloc[[idx]]
                    true_label = test_data.iloc[idx]['wan']

                    pred = predictor.predict(sample)
                    if pred and 'wan' in pred:
                        predicted_label = pred['wan']['top_k'][0]
                        if predicted_label == true_label:
                            correct += 1
                        total += 1

                accuracy = correct / total if total > 0 else 0
                metrics = {
                    "accuracy": accuracy,
                    "correct": correct,
                    "total": total
                }

                self.logger.info(f"✓ 评估完成")
                self.logger.info(f"  准确率: {accuracy * 100:.2f}%")
                self.logger.info(f"  正确预测: {correct}/{total}")

                self.results["performance_metrics"].append({
                    "timestamp": datetime.now().isoformat(),
                    "accuracy": accuracy,
                    "correct": correct,
                    "total": total
                })
            else:
                self.logger.warning("数据不足，跳过评估")

            return metrics
        except Exception as e:
            self.logger.error(f"✗ 模型评估失败: {e}")
            self.logger.error(traceback.format_exc())
            self.results["errors"].append(f"模型评估失败: {e}")
            return {}

    def make_predictions(self, predictor: Any, features: Any) -> Dict[str, Any]:
        """生成预测"""
        self.log_section("5. 生成预测")
        try:
            self.logger.info("生成最新预测...")

            latest = features.iloc[[-1]]
            predictions = predictor.predict(latest)

            self.logger.info("✓ 预测生成完成:")
            for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                if pos in predictions:
                    top_k = predictions[pos]['top_k'][:5]
                    self.logger.info(f"  {pos}: {top_k}")

            self.results["total_predictions"] += 1

            return predictions
        except Exception as e:
            self.logger.error(f"✗ 预测生成失败: {e}")
            self.logger.error(traceback.format_exc())
            self.results["errors"].append(f"预测生成失败: {e}")
            return {}

    def save_model(self, predictor: Any, feature_cols: List[str]):
        """保存模型"""
        self.log_section("6. 保存模型")
        try:
            import pickle
            import os

            model_path = PROJECT_ROOT / "src" / "models" / "pl5_predictor_trained.pkl"
            model_path.parent.mkdir(parents=True, exist_ok=True)

            model_data = {
                'stacking': predictor.stacking if hasattr(predictor, 'stacking') else None,
                'hmm_models': predictor.hmm_models if hasattr(predictor, 'hmm_models') else {},
                'bsts_models': predictor.bsts_models if hasattr(predictor, 'bsts_models') else {},
                'evm_models': predictor.evm_models if hasattr(predictor, 'evm_models') else {},
                'copula': predictor.copula if hasattr(predictor, 'copula') else None,
                'is_trained': predictor.is_trained,
                'feature_cols': feature_cols,
                'saved_at': datetime.now().isoformat()
            }

            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)

            file_size = os.path.getsize(model_path) / 1024
            self.logger.info(f"✓ 模型已保存: {model_path}")
            self.logger.info(f"  文件大小: {file_size:.2f} KB")

        except Exception as e:
            self.logger.error(f"✗ 模型保存失败: {e}")
            self.logger.error(traceback.format_exc())
            self.results["errors"].append(f"模型保存失败: {e}")

    def run_training_cycle(self) -> bool:
        """运行一次完整的训练周期"""
        self.log_section("执行训练周期")
        try:
            data = self.load_data()
            if data is None:
                return False

            features, feature_cols = self.extract_features(data)
            if features is None:
                return False

            predictor = self.train_model(features, feature_cols)
            if predictor is None:
                return False

            metrics = self.evaluate_model(predictor, features, feature_cols)

            predictions = self.make_predictions(predictor, features)

            self.save_model(predictor, feature_cols)

            self.results["training_cycles"] += 1

            return True

        except Exception as e:
            self.logger.error(f"✗ 训练周期执行失败: {e}")
            self.logger.error(traceback.format_exc())
            self.results["errors"].append(f"训练周期失败: {e}")
            self.results["success"] = False
            return False

    def generate_report(self):
        """生成报告"""
        self.results["end_time"] = datetime.now().isoformat()
        self.results["status"] = "SUCCESS" if self.results["success"] else "FAILED"

        try:
            with open(self.report_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            self.logger.info(f"✓ 报告已保存: {self.report_file}")
        except Exception as e:
            self.logger.error(f"✗ 报告保存失败: {e}")

        self.log_section("训练任务总结")
        self.logger.info(f"开始时间: {self.results['start_time']}")
        self.logger.info(f"结束时间: {self.results['end_time']}")
        self.logger.info(f"训练周期数: {self.results['training_cycles']}")
        self.logger.info(f"总预测次数: {self.results['total_predictions']}")
        self.logger.info(f"错误数量: {len(self.results['errors'])}")

        if self.results["performance_metrics"]:
            latest = self.results["performance_metrics"][-1]
            self.logger.info(f"最新准确率: {latest['accuracy'] * 100:.2f}%")

        self.logger.info(f"状态: {self.results['status']}")

    def run(self):
        """运行日循环训练任务"""
        self.log_section("PL5 日循环训练任务执行器")
        self.logger.info(f"启动时间: {datetime.now()}")
        self.logger.info(f"工作目录: {PROJECT_ROOT}")
        self.logger.info(f"日志文件: {self.log_file}")

        try:
            success = self.run_training_cycle()

            if success:
                self.logger.info("✓ 日循环训练任务执行成功")
            else:
                self.logger.warning("⚠ 日循环训练任务执行失败")

        except Exception as e:
            self.logger.error(f"✗ 执行失败: {e}")
            self.logger.error(traceback.format_exc())
            self.results["success"] = False
            self.results["errors"].append(str(e))

        finally:
            self.generate_report()

if __name__ == "__main__":
    executor = DailyTrainingExecutor()
    executor.run()
