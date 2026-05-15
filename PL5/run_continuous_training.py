#!/usr/bin/env python3
"""
PL5 24小时持续训练循环系统
每1小时执行一次完整训练和推理任务，持续24小时
"""

import os
import sys
import time
import json
import traceback
import logging
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path("/workspace/PL5")
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

LOG_DIR = PROJECT_ROOT / "logs" / "daily_training"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class ContinuousTrainingSystem:
    """24小时持续训练系统"""

    def __init__(self, duration_hours=24, interval_minutes=60):
        self.duration_hours = duration_hours
        self.interval_minutes = interval_minutes
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = LOG_DIR / f"continuous_training_{self.timestamp}.log"
        self.summary_file = LOG_DIR / f"summary_{self.timestamp}.txt"
        self.metrics_file = LOG_DIR / f"metrics_{self.timestamp}.json"
        self.setup_logging()

        self.stats = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "total_cycles": 0,
            "successful_cycles": 0,
            "failed_cycles": 0,
            "total_training_time": 0,
            "avg_cycle_time": 0,
            "accuracy_history": [],
            "errors": [],
            "performance_data": []
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
        self.logger = logging.getLogger("ContinuousTraining")

    def log_section(self, title: str):
        """记录章节"""
        line = "=" * 80
        self.logger.info(line)
        self.logger.info(f"  {title}")
        self.logger.info(line)

    def log_header(self):
        """记录头部信息"""
        self.log_section("PL5 24小时持续训练循环系统")
        self.logger.info(f"启动时间: {datetime.now()}")
        self.logger.info(f"持续时间: {self.duration_hours} 小时")
        self.logger.info(f"执行间隔: {self.interval_minutes} 分钟")
        self.logger.info(f"预计执行次数: {int(self.duration_hours * 60 / self.interval_minutes)} 次")
        self.logger.info(f"日志文件: {self.log_file}")

    def load_and_prepare_data(self):
        """加载和准备数据"""
        self.log_section("步骤1: 加载数据")
        try:
            from src.core.data.collector import PL5DataCollectorV8

            collector = PL5DataCollectorV8()
            self.logger.info("正在更新数据...")

            data = collector.update_data()
            if data is None or len(data) == 0:
                self.logger.warning("没有新数据，尝试加载现有数据")
                data = collector.load_processed_data()

            if data is None or len(data) == 0:
                raise ValueError("无法加载任何数据")

            self.logger.info(f"✓ 数据加载成功: {len(data)} 条记录")
            self.logger.info(f"  最新期号: {data['period'].iloc[-1]}")
            self.logger.info(f"  数据范围: {data['date'].min()} ~ {data['date'].max()}")

            return data

        except Exception as e:
            self.logger.error(f"✗ 数据加载失败: {e}")
            self.logger.error(traceback.format_exc())
            self.stats["errors"].append(f"数据加载失败: {e}")
            return None

    def extract_features(self, data):
        """提取特征"""
        self.log_section("步骤2: 特征工程")
        try:
            from src.core.features.engineer import FeatureEngineer

            engineer = FeatureEngineer()
            self.logger.info("正在提取特征...")

            features = engineer.extract_all_features(data)

            non_feature_cols = ['period', 'full_number', 'wan', 'qian', 'bai', 'shi', 'ge', 'date']
            feature_cols = [col for col in features.columns if col not in non_feature_cols]

            self.logger.info(f"✓ 特征提取成功: {len(features)} 样本, {len(feature_cols)} 特征")

            return features, feature_cols

        except Exception as e:
            self.logger.error(f"✗ 特征提取失败: {e}")
            self.logger.error(traceback.format_exc())
            self.stats["errors"].append(f"特征提取失败: {e}")
            return None, None

    def train_model(self, features, feature_cols):
        """训练模型"""
        self.log_section("步骤3: 模型训练")
        try:
            from src.core.models.predictor import PL5Predictor
            import time

            predictor = PL5Predictor()
            self.logger.info("开始训练模型...")

            start_time = time.time()
            predictor.train(features, feature_cols)
            training_time = time.time() - start_time

            self.logger.info(f"✓ 训练完成，耗时: {training_time:.2f}秒")

            if hasattr(predictor, 'stacking') and predictor.stacking:
                self.logger.info("  [✓] Stacking 集成模型已就绪")

            if hasattr(predictor, 'hmm_models') and predictor.hmm_models:
                self.logger.info(f"  [✓] HMM模型: {len(predictor.hmm_models)} 个已训练")

            self.stats["total_training_time"] += training_time

            return predictor

        except Exception as e:
            self.logger.error(f"✗ 模型训练失败: {e}")
            self.logger.error(traceback.format_exc())
            self.stats["errors"].append(f"模型训练失败: {e}")
            return None

    def evaluate_model(self, predictor, features, feature_cols):
        """评估模型"""
        self.log_section("步骤4: 模型评估")
        try:
            import time

            self.logger.info("评估模型性能...")

            if len(features) < 10:
                self.logger.warning("数据不足，跳过评估")
                return {}

            train_size = int(len(features) * 0.8)
            train_data = features.iloc[:train_size]
            test_data = features.iloc[train_size:]

            self.logger.info(f"  训练集: {train_size} 样本")
            self.logger.info(f"  测试集: {len(test_data)} 样本")

            predictor.train(train_data, feature_cols)

            start_time = time.time()
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

            eval_time = time.time() - start_time
            accuracy = correct / total if total > 0 else 0

            self.logger.info(f"✓ 评估完成，耗时: {eval_time:.2f}秒")
            self.logger.info(f"  准确率: {accuracy * 100:.2f}%")
            self.logger.info(f"  正确预测: {correct}/{total}")

            metrics = {
                "timestamp": datetime.now().isoformat(),
                "accuracy": accuracy,
                "correct": correct,
                "total": total,
                "train_size": train_size,
                "test_size": len(test_data),
                "eval_time": eval_time
            }

            self.stats["accuracy_history"].append(accuracy)
            self.stats["performance_data"].append(metrics)

            return metrics

        except Exception as e:
            self.logger.error(f"✗ 模型评估失败: {e}")
            self.logger.error(traceback.format_exc())
            self.stats["errors"].append(f"模型评估失败: {e}")
            return {}

    def generate_predictions(self, predictor, features):
        """生成预测"""
        self.log_section("步骤5: 生成预测")
        try:
            self.logger.info("为最新数据生成预测...")

            latest = features.iloc[[-1]]
            predictions = predictor.predict(latest)

            self.logger.info("✓ 预测生成完成:")
            for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                if pos in predictions:
                    top_k = predictions[pos]['top_k'][:5]
                    self.logger.info(f"  {pos}: {top_k}")

            return predictions

        except Exception as e:
            self.logger.error(f"✗ 预测生成失败: {e}")
            self.logger.error(traceback.format_exc())
            self.stats["errors"].append(f"预测生成失败: {e}")
            return {}

    def save_model(self, predictor, feature_cols):
        """保存模型"""
        self.log_section("步骤6: 保存模型")
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
            self.stats["errors"].append(f"模型保存失败: {e}")

    def execute_training_cycle(self, cycle_number):
        """执行一次完整的训练周期"""
        self.log_section(f"训练周期 #{cycle_number}")
        cycle_start = datetime.now()
        self.logger.info(f"开始时间: {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            data = self.load_and_prepare_data()
            if data is None:
                raise Exception("数据加载失败")

            features, feature_cols = self.extract_features(data)
            if features is None:
                raise Exception("特征提取失败")

            predictor = self.train_model(features, feature_cols)
            if predictor is None:
                raise Exception("模型训练失败")

            metrics = self.evaluate_model(predictor, features, feature_cols)

            predictions = self.generate_predictions(predictor, features)

            self.save_model(predictor, feature_cols)

            cycle_time = (datetime.now() - cycle_start).total_seconds()
            self.logger.info(f"✓ 周期 #{cycle_number} 完成，耗时: {cycle_time:.2f}秒")

            self.stats["successful_cycles"] += 1
            self.stats["total_cycles"] += 1

            return True

        except Exception as e:
            cycle_time = (datetime.now() - cycle_start).total_seconds()
            self.logger.error(f"✗ 周期 #{cycle_number} 失败，耗时: {cycle_time:.2f}秒")
            self.logger.error(f"  错误: {e}")

            self.stats["failed_cycles"] += 1
            self.stats["total_cycles"] += 1
            self.stats["errors"].append(f"周期 #{cycle_number}: {e}")

            return False

    def calculate_statistics(self):
        """计算统计信息"""
        if self.stats["total_cycles"] > 0:
            self.stats["avg_cycle_time"] = self.stats["total_training_time"] / self.stats["total_cycles"]

        if self.stats["accuracy_history"]:
            avg_accuracy = sum(self.stats["accuracy_history"]) / len(self.stats["accuracy_history"])
            self.stats["avg_accuracy"] = avg_accuracy
            self.stats["best_accuracy"] = max(self.stats["accuracy_history"])
            self.stats["worst_accuracy"] = min(self.stats["accuracy_history"])

    def generate_summary(self):
        """生成总结报告"""
        self.calculate_statistics()
        self.stats["end_time"] = datetime.now().isoformat()

        self.log_section("24小时持续训练总结")

        self.logger.info(f"开始时间: {self.stats['start_time']}")
        self.logger.info(f"结束时间: {self.stats['end_time']}")
        self.logger.info(f"总训练周期: {self.stats['total_cycles']}")
        self.logger.info(f"成功周期: {self.stats['successful_cycles']}")
        self.logger.info(f"失败周期: {self.stats['failed_cycles']}")
        self.logger.info(f"总训练时间: {self.stats['total_training_time']:.2f}秒")
        self.logger.info(f"平均周期时间: {self.stats['avg_cycle_time']:.2f}秒")

        if self.stats["accuracy_history"]:
            self.logger.info(f"平均准确率: {self.stats['avg_accuracy'] * 100:.2f}%")
            self.logger.info(f"最佳准确率: {self.stats['best_accuracy'] * 100:.2f}%")
            self.logger.info(f"最差准确率: {self.stats['worst_accuracy'] * 100:.2f}%")

        self.logger.info(f"错误总数: {len(self.stats['errors'])}")

        if self.stats["errors"]:
            self.logger.info("错误详情:")
            for error in self.stats["errors"][:10]:
                self.logger.info(f"  - {error}")

        try:
            with open(self.summary_file, 'w', encoding='utf-8') as f:
                for key, value in self.stats.items():
                    f.write(f"{key}: {value}\n")
            self.logger.info(f"✓ 总结报告已保存: {self.summary_file}")
        except Exception as e:
            self.logger.error(f"✗ 总结报告保存失败: {e}")

        try:
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
            self.logger.info(f"✓ 性能数据已保存: {self.metrics_file}")
        except Exception as e:
            self.logger.error(f"✗ 性能数据保存失败: {e}")

    def run(self):
        """运行持续训练系统"""
        self.log_header()

        try:
            total_cycles = int(self.duration_hours * 60 / self.interval_minutes)
            self.logger.info(f"\n开始执行 {total_cycles} 个训练周期...\n")

            for cycle in range(1, total_cycles + 1):
                cycle_start_time = datetime.now()

                self.logger.info(f"\n{'=' * 80}")
                self.logger.info(f"周期 {cycle}/{total_cycles}")
                self.logger.info(f"{'=' * 80}\n")

                success = self.execute_training_cycle(cycle)

                if not success:
                    self.logger.warning(f"⚠ 周期 {cycle} 失败，继续下一个周期")

                if cycle < total_cycles:
                    next_cycle_time = cycle_start_time + timedelta(minutes=self.interval_minutes)
                    self.logger.info(f"\n下一个周期预计开始: {next_cycle_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.logger.info(f"等待 {self.interval_minutes} 分钟...\n")
                    time.sleep(self.interval_minutes * 60)

            self.logger.info("\n" + "=" * 80)
            self.logger.info("✓ 所有训练周期已完成")
            self.logger.info("=" * 80 + "\n")

        except KeyboardInterrupt:
            self.logger.warning("\n⚠ 用户中断，正在停止...")
        except Exception as e:
            self.logger.error(f"\n✗ 系统错误: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.generate_summary()

if __name__ == "__main__":
    print("=" * 80)
    print("PL5 24小时持续训练循环系统")
    print("=" * 80)
    print()

    system = ContinuousTrainingSystem(duration_hours=24, interval_minutes=60)
    system.run()
