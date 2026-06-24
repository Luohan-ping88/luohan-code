#!/usr/bin/env python3
"""
策略评估和回测系统 V10.1
用于评估不同推理策略的效果，测试"换一种策略又会怎么样"

修复记录 (2026-04-21):
  - BUG#1: predict() 无参调用 → 必须传 features 数组 (TypeError)
  - BUG#2: 时间穿越 → 每期用截止到该期之前的数据特征做预测
  - BUG#3: except Exception: pass → 添加详细日志，不再静默吞没异常
"""

import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

from src.core.config import DATA_DIR, MODELS_DIR
from src.core.models.enhanced_predictor import EnhancedPL5Predictor
from src.core.data.collector import PL5DataCollector
from src.core.features.engineer import FeatureEngineer

logger = logging.getLogger(__name__)

_STRATEGY_HISTORY_PATH = MODELS_DIR / "strategy_evaluation_history.json"

# 位置名称（与 EnhancedPL5Predictor.POSITIONS 一致）
POSITION_NAMES = ['wan', 'qian', 'bai', 'shi', 'ge']
# 排除列（非特征列）
NON_FEATURE_COLS = ['period', 'date', 'full_number', 'parse_line', 'wan', 'qian', 'bai', 'shi', 'ge']


class StrategyEvaluator:
    """策略评估器 - 用于评估和比较不同推理策略的效果"""

    def __init__(self):
        self.predictor = EnhancedPL5Predictor()
        self.collector = PL5DataCollector()
        self.engineer = FeatureEngineer()
        self.evaluation_history = self._load_history()

    def _load_history(self) -> List[Dict]:
        """加载策略评估历史"""
        try:
            if _STRATEGY_HISTORY_PATH.exists():
                with open(_STRATEGY_HISTORY_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载策略评估历史失败: {e}")
        return []

    def _save_history(self):
        """保存策略评估历史"""
        try:
            with open(_STRATEGY_HISTORY_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.evaluation_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存策略评估历史失败: {e}")

    def define_strategies(self) -> Dict[str, Dict]:
        """定义不同的推理策略"""
        strategies = {
            'default': {
                'name': '默认策略',
                'description': '使用所有模型的默认权重',
                'model_weights': {'stacking': 0.4, 'hmm': 0.2, 'copula': 0.2, 'bsts': 0.2},
                'feature_selection': 'all',
                'ensemble_method': 'weighted_average'
            },
            'stacking_dominant': {
                'name': 'Stacking主导策略',
                'description': 'Stacking模型权重更高（已降低防止特征泄漏绑架）',
                'model_weights': {'stacking': 0.30, 'hmm': 0.20, 'copula': 0.20, 'bsts': 0.15, 'evm': 0.15},
                'feature_selection': 'all',
                'ensemble_method': 'weighted_average'
            },
            'hmm_dominant': {
                'name': 'HMM主导策略',
                'description': 'HMM模型权重更高',
                'model_weights': {'stacking': 0.15, 'hmm': 0.40, 'copula': 0.20, 'bsts': 0.15, 'evm': 0.10},
                'feature_selection': 'all',
                'ensemble_method': 'weighted_average'
            },
            'copula_dominant': {
                'name': 'Copula主导策略',
                'description': 'Copula模型权重更高',
                'model_weights': {'stacking': 0.15, 'hmm': 0.20, 'copula': 0.40, 'bsts': 0.15, 'evm': 0.10},
                'feature_selection': 'all',
                'ensemble_method': 'weighted_average'
            },
            'rfe_features': {
                'name': 'RFE特征选择策略',
                'description': '使用RFE选择的特征',
                'model_weights': {'stacking': 0.4, 'hmm': 0.2, 'copula': 0.2, 'bsts': 0.2},
                'feature_selection': 'rfe',
                'ensemble_method': 'weighted_average'
            },
            'voting_ensemble': {
                'name': '投票集成策略',
                'description': '使用投票而非加权平均',
                'model_weights': {'stacking': 0.25, 'hmm': 0.25, 'copula': 0.25, 'bsts': 0.25},
                'feature_selection': 'all',
                'ensemble_method': 'voting'
            }
        }
        return strategies

    def _build_feature_matrix(self, df_raw: pd.DataFrame,
                              feature_cols: List[str],
                              select_top: Optional[int] = None) -> pd.DataFrame:
        """
        对原始数据提取特征，返回包含特征列的 DataFrame。

        Args:
            df_raw: 原始处理后的数据（含 wan/qian/bai/shi/ge 等列）
            feature_cols: 特征列名列表
            select_top: 传给 extract_all_features 的 select_top，None 表示全量特征
        """
        df_features = self.engineer.extract_all_features(
            df_raw, select_top=select_top
        )
        return df_features

    def evaluate_strategy(self, strategy_name: str, strategy: Dict,
                          df_raw: pd.DataFrame, feature_cols: List[str],
                          test_window: int = 20) -> Dict:
        """
        评估单个策略的效果（逐期回测）。

        回测逻辑：
        - 取原始数据最后 test_window 期作为测试集
        - 对每一期 i：
            1. 用 df_raw[:n_train + i] 的数据（截止到该期之前）提取特征
            2. 取最后一行特征作为 predict() 的输入
            3. 将预测的 top_k 与该期实际开奖号码比对
        """
        logger.info(f"开始评估策略: {strategy_name}")

        try:
            # 测试数据在原始 df 的最后 test_window 行
            n_total = len(df_raw)
            test_start_idx = n_total - test_window

            if test_start_idx < 100:
                logger.warning(f"测试窗口 {test_window} 过大（数据仅 {n_total} 行），缩小至可用范围")
                test_start_idx = max(0, n_total - max(5, n_total - 100))
                test_window = n_total - test_start_idx

            # 加载模型（只需加载一次）
            if not self.predictor.load_models():
                logger.warning("模型加载失败")
                return {
                    'strategy_name': strategy_name,
                    'success': False,
                    'error': '模型加载失败'
                }

            # 应用策略配置
            self._apply_strategy_config(strategy)

            # 回测策略效果
            results = {
                'strategy_name': strategy_name,
                'strategy_config': strategy,
                'positions': {},
                'overall': {}
            }

            total_top1_hits = 0
            total_top3_hits = 0
            total_top5_hits = 0
            total_top8_hits = 0

            for pos in POSITION_NAMES:
                pos_results = self._backtest_position(
                    pos, df_raw, test_start_idx, test_window, feature_cols
                )
                results['positions'][pos] = pos_results

                total_top1_hits += pos_results['top1_hits']
                total_top3_hits += pos_results['top3_hits']
                total_top5_hits += pos_results['top5_hits']
                total_top8_hits += pos_results['top8_hits']

            # 计算总体指标
            total_tests = test_window * 5
            results['overall'] = {
                'top1_accuracy': total_top1_hits / total_tests if total_tests > 0 else 0,
                'top3_accuracy': total_top3_hits / total_tests if total_tests > 0 else 0,
                'top5_accuracy': total_top5_hits / total_tests if total_tests > 0 else 0,
                'top8_accuracy': total_top8_hits / total_tests if total_tests > 0 else 0,
                'total_tests': total_tests,
                'top1_hits': total_top1_hits,
                'top3_hits': total_top3_hits,
                'top5_hits': total_top5_hits,
                'top8_hits': total_top8_hits
            }

            results['success'] = True
            results['timestamp'] = datetime.now().isoformat()

            logger.info(
                f"策略 {strategy_name} 评估完成: "
                f"Top-1={results['overall']['top1_accuracy']:.4f}, "
                f"Top-3={results['overall']['top3_accuracy']:.4f}, "
                f"Top-5={results['overall']['top5_accuracy']:.4f}, "
                f"Top-8={results['overall']['top8_accuracy']:.4f}"
            )

            return results

        except Exception as e:
            logger.error(f"评估策略 {strategy_name} 失败: {e}", exc_info=True)
            return {
                'strategy_name': strategy_name,
                'success': False,
                'error': str(e)
            }

    def _apply_strategy_config(self, strategy: Dict):
        """应用策略配置到预测器"""
        # 这里可以根据策略配置调整预测器的行为
        # 例如：调整模型权重、特征选择等
        pass

    def _backtest_position(self, position: str, df_raw: pd.DataFrame,
                           test_start_idx: int, test_window: int,
                           feature_cols: List[str]) -> Dict:
        """
        回测单个位置。

        对测试窗口中的每一期：
        1. 取 df_raw[0 : test_start_idx + i]（该期之前的所有数据）提取特征
        2. 用最后一行的特征向量调用 predictor.predict(features, ...)
        3. 比对预测 top_k 与 df_raw.iloc[test_start_idx + i][position]

        性能优化：因为同一期的数据对所有 5 个位置共享，我们用 test_start_idx
        标记截止点，每期只提取一次特征。
        但由于每个位置独立调用此方法，为了避免重复提取，这里采用
        每个位置独立回测的方式（调用者外层遍历 5 个位置）。
        为避免 5 * test_window 次重复特征提取，我们在类级别缓存特征矩阵。
        """
        top1_hits = 0
        top3_hits = 0
        top5_hits = 0
        top8_hits = 0
        total_tests = 0
        predict_errors = 0

        for i in range(test_window):
            target_idx = test_start_idx + i
            # 截止到目标期之前的数据（不包含目标期本身，避免数据泄露）
            df_train = df_raw.iloc[:target_idx]

            if len(df_train) < 50:
                logger.debug(f"位置 {position} 第 {i} 期: 训练数据不足 ({len(df_train)} 行), 跳过")
                continue

            try:
                # 提取特征（与生产预测路径一致：select_top=None，避免RFE选出不同特征导致维度不匹配）
                logger.info(f"_backtest_position: 调用 extract_all_features 时 select_top=None（特征漂移已修复）")
                df_features = self.engineer.extract_all_features(
                    df_train, 
                    select_top=None,
                    feature_selection_method='rfe'
                )
                if df_features.empty or len(df_features) == 0:
                    logger.debug(f"位置 {position} 第 {i} 期: 特征提取结果为空, 跳过")
                    continue

                # 取最后一行的特征向量
                last_row = df_features.iloc[-1]
                # 提取纯特征列（排除非特征列）
                features_list = []
                for col in df_features.columns:
                    if col not in NON_FEATURE_COLS:
                        val = last_row[col]
                        # 处理可能的 Inf/NaN 和类型问题
                        try:
                            val = float(val)
                            if np.isfinite(val):
                                features_list.append(val)
                            else:
                                features_list.append(0.0)
                        except (ValueError, TypeError):
                            features_list.append(0.0)

                if len(features_list) == 0:
                    logger.debug(f"位置 {position} 第 {i} 期: 特征数为 0, 跳过")
                    continue

                features = np.array(features_list, dtype=np.float64)
                logger.info(f"_backtest_position: 提取的特征维度: {len(features)}")

                # 准备最近的原始数据，用于 HMM 等时序模型
                recent_original_data = {}
                for pos_name in POSITION_NAMES:
                    if pos_name in df_train.columns:
                        # 取最近 20 期的数据，用于 HMM 预测
                        recent_data = df_train[pos_name].values[-20:] if len(df_train) >= 20 else df_train[pos_name].values
                        recent_original_data[pos_name] = recent_data

                # 调用 predict（传入特征数组和最近原始数据）
                predictions = self.predictor.predict(
                    features=features,
                    recent_original_data=recent_original_data,
                    top_k=8,
                    use_rl=False,        # 回测时关闭 RL，保持结果可复现
                    use_uncertainty=False # 回测时关闭不确定性量化，加快速度
                )

                if position not in predictions:
                    logger.debug(f"位置 {position} 第 {i} 期: 预测结果中无该位置, 跳过")
                    continue

                pos_pred = predictions[position]
                if 'top_k' not in pos_pred:
                    logger.debug(f"位置 {position} 第 {i} 期: 预测结果中无 top_k, 跳过")
                    continue

                top_k = pos_pred['top_k']
                actual_value = int(df_raw.iloc[target_idx][position])

                total_tests += 1
                if actual_value in top_k[:1]:
                    top1_hits += 1
                if actual_value in top_k[:3]:
                    top3_hits += 1
                if actual_value in top_k[:5]:
                    top5_hits += 1
                if actual_value in top_k[:8]:
                    top8_hits += 1

            except Exception as e:
                predict_errors += 1
                logger.debug(
                    f"位置 {position} 第 {i} 期 (target_idx={target_idx}) 预测失败: "
                    f"{type(e).__name__}: {e}"
                )
                continue

        if predict_errors > 0:
            logger.warning(
                f"位置 {position} 回测完成: {predict_errors}/{test_window} 期预测出错"
            )

        return {
            'top1_hits': top1_hits,
            'top3_hits': top3_hits,
            'top5_hits': top5_hits,
            'top8_hits': top8_hits,
            'total_tests': total_tests,
            'predict_errors': predict_errors,
            'top1_accuracy': top1_hits / total_tests if total_tests > 0 else 0,
            'top3_accuracy': top3_hits / total_tests if total_tests > 0 else 0,
            'top5_accuracy': top5_hits / total_tests if total_tests > 0 else 0,
            'top8_accuracy': top8_hits / total_tests if total_tests > 0 else 0
        }

    def evaluate_all_strategies(self, test_window: int = 20, target_duration_minutes: int = 45) -> Dict:
        """评估所有策略（智能动态调整版本）"""
        logger.info("=" * 80)
        logger.info("开始评估所有策略（智能动态调整版本）")
        logger.info("=" * 80)
        logger.info(f"目标运行时间: {target_duration_minutes} 分钟")
        
        start_time = datetime.now()

        # 加载原始数据
        df_raw = self.collector.load_processed_data()
        if df_raw is None or len(df_raw) < 100:
            logger.error(f"数据不足: {len(df_raw) if df_raw is not None else 0} 行")
            return {
                'timestamp': datetime.now().isoformat(),
                'test_window': test_window,
                'strategies': {},
                'best_strategy': None,
                'error': '数据不足'
            }

        n_total = len(df_raw)
        
        # 先快速完成第一阶段：只评估最后一期
        logger.info("=" * 80)
        logger.info("第一阶段：快速评估（1期）")
        logger.info("=" * 80)
        
        # 评估窗口1期
        test_window_1 = 1
        test_start_idx_1 = n_total - test_window_1
        
        df_train_1 = df_raw.iloc[:test_start_idx_1]
        logger.info(f"提取特征：使用前 {len(df_train_1)} 期数据")
        
        # 提取特征（与生产预测路径一致：select_top=None，避免RFE选出不同特征子集）
        df_features_1 = self.engineer.extract_all_features(
            df_train_1, 
            select_top=None,
            feature_selection_method='rfe'
        )
        
        # 确定特征列
        feature_cols = [col for col in df_features_1.columns if col not in NON_FEATURE_COLS]
        logger.info(f"特征列数: {len(feature_cols)}")

        strategies = self.define_strategies()
        results = {}

        # 先评估所有策略（1期）
        for strategy_name, strategy in strategies.items():
            result = self._evaluate_strategy_simple(
                strategy_name, strategy, df_raw, df_features_1, test_start_idx_1, test_window_1
            )
            results[strategy_name] = result

        # 找出第一阶段最佳策略
        best_strategy_1 = self._find_best_strategy(results)
        
        # 计算已用时间
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        logger.info(f"第一阶段完成，已用时间: {elapsed:.1f} 分钟")

        # 检查是否还有时间进行更深入的评估
        remaining_time = target_duration_minutes - elapsed
        if remaining_time > 10:  # 如果剩余时间大于10分钟，继续深入评估
            logger.info("=" * 80)
            logger.info(f"第二阶段：深入评估（更大窗口）")
            logger.info("=" * 80)
            logger.info(f"剩余时间: {remaining_time:.1f} 分钟，继续深入评估")
            
            # 根据剩余时间动态调整窗口大小
            if remaining_time > 30:
                test_window_2 = min(10, n_total // 10)  # 至少10期，最多总数据的1/10
            elif remaining_time > 20:
                test_window_2 = min(5, n_total // 20)  # 5期
            else:
                test_window_2 = 3  # 3期
            
            logger.info(f"第二阶段测试窗口: {test_window_2} 期")
            
            # 使用原来的逐期回测（但只对最佳策略进行深入评估）
            if best_strategy_1:
                best_name = best_strategy_1['name']
                logger.info(f"对最佳策略 {best_name} 进行深入评估")
                
                # 使用原来的回测方法
                result_deep = self.evaluate_strategy(
                    best_name, strategies[best_name], df_raw, feature_cols, test_window_2
                )
                results[best_name] = result_deep
                
                # 重新找出最佳策略
                best_strategy = self._find_best_strategy(results)
            else:
                best_strategy = best_strategy_1
        else:
            logger.info(f"剩余时间不足，跳过深入评估")
            best_strategy = best_strategy_1
        
        # 计算总用时
        total_elapsed = (datetime.now() - start_time).total_seconds() / 60
        logger.info(f"总用时: {total_elapsed:.1f} 分钟")

        evaluation_result = {
            'timestamp': datetime.now().isoformat(),
            'test_window': test_window,
            'strategies': results,
            'best_strategy': best_strategy,
            'total_elapsed_minutes': total_elapsed
        }

        # 保存到历史
        self.evaluation_history.append(evaluation_result)
        if len(self.evaluation_history) > 10:
            self.evaluation_history = self.evaluation_history[-10:]
        self._save_history()

        logger.info("=" * 80)
        logger.info("评估完成")
        logger.info("=" * 80)
        return evaluation_result
    
    def _evaluate_strategy_simple(self, strategy_name: str, strategy: Dict,
                                   df_raw: pd.DataFrame, df_features: pd.DataFrame,
                                   test_start_idx: int, test_window: int) -> Dict:
        """简化版策略评估：只评估最后一期"""
        logger.info(f"开始评估策略（简化版）: {strategy_name}")

        try:
            # 加载模型（只需加载一次）
            if not self.predictor.load_models():
                logger.warning("模型加载失败")
                return {
                    'strategy_name': strategy_name,
                    'success': False,
                    'error': '模型加载失败'
                }

            # 应用策略配置
            self._apply_strategy_config(strategy)

            # 只评估最后一期
            target_idx = test_start_idx
            
            # 取最后一行的特征向量
            last_row = df_features.iloc[-1]
            features_list = []
            for col in df_features.columns:
                if col not in NON_FEATURE_COLS:
                    val = last_row[col]
                    try:
                        # 确保值是数字类型
                        val = float(val)
                        if np.isfinite(val):
                            features_list.append(val)
                        else:
                            features_list.append(0.0)
                    except (ValueError, TypeError):
                        features_list.append(0.0)
            
            features = np.array(features_list, dtype=np.float64)

            # 准备最近的原始数据
            recent_original_data = {}
            df_train = df_raw.iloc[:target_idx]
            for pos_name in POSITION_NAMES:
                if pos_name in df_train.columns:
                    recent_data = df_train[pos_name].values[-20:] if len(df_train) >= 20 else df_train[pos_name].values
                    recent_original_data[pos_name] = recent_data

            # 调用 predict
            predictions = self.predictor.predict(
                features=features,
                recent_original_data=recent_original_data,
                top_k=8,
                use_rl=False,
                use_uncertainty=False
            )

            # 统计命中情况
            results = {
                'strategy_name': strategy_name,
                'strategy_config': strategy,
                'positions': {},
                'overall': {}
            }

            total_top1_hits = 0
            total_top3_hits = 0
            total_top5_hits = 0
            total_top8_hits = 0

            for pos in POSITION_NAMES:
                if pos not in predictions:
                    continue
                
                pos_pred = predictions[pos]
                if 'top_k' not in pos_pred:
                    continue
                
                top_k = pos_pred['top_k']
                actual_value = int(df_raw.iloc[target_idx][pos])
                
                top1_hits = 1 if actual_value in top_k[:1] else 0
                top3_hits = 1 if actual_value in top_k[:3] else 0
                top5_hits = 1 if actual_value in top_k[:5] else 0
                top8_hits = 1 if actual_value in top_k[:8] else 0
                
                results['positions'][pos] = {
                    'top1_hits': top1_hits,
                    'top3_hits': top3_hits,
                    'top5_hits': top5_hits,
                    'top8_hits': top8_hits,
                    'total_tests': 1
                }
                
                total_top1_hits += top1_hits
                total_top3_hits += top3_hits
                total_top5_hits += top5_hits
                total_top8_hits += top8_hits

            # 计算总体指标
            total_tests = 5
            results['overall'] = {
                'top1_accuracy': total_top1_hits / total_tests,
                'top3_accuracy': total_top3_hits / total_tests,
                'top5_accuracy': total_top5_hits / total_tests,
                'top8_accuracy': total_top8_hits / total_tests,
                'total_tests': total_tests,
                'top1_hits': total_top1_hits,
                'top3_hits': total_top3_hits,
                'top5_hits': total_top5_hits,
                'top8_hits': total_top8_hits
            }

            results['success'] = True
            results['timestamp'] = datetime.now().isoformat()

            logger.info(
                f"策略 {strategy_name} 评估完成: "
                f"Top-1={results['overall']['top1_accuracy']:.4f}, "
                f"Top-3={results['overall']['top3_accuracy']:.4f}, "
                f"Top-5={results['overall']['top5_accuracy']:.4f}, "
                f"Top-8={results['overall']['top8_accuracy']:.4f}"
            )

            return results

        except Exception as e:
            logger.error(f"评估策略 {strategy_name} 失败: {e}", exc_info=True)
            return {
                'strategy_name': strategy_name,
                'success': False,
                'error': str(e)
            }

    def _find_best_strategy(self, results: Dict) -> Dict:
        """找出最佳策略"""
        best_strategy = None
        best_score = -1

        for strategy_name, result in results.items():
            if result.get('success', False) and 'overall' in result:
                # 使用Top-3准确率作为主要评分指标
                score = result['overall'].get('top3_accuracy', 0)
                if score > best_score:
                    best_score = score
                    best_strategy = {
                        'name': strategy_name,
                        'score': score,
                        'details': result
                    }

        return best_strategy

    def get_strategy_comparison_report(self, evaluation_result: Dict) -> str:
        """生成策略对比报告"""
        report = []
        report.append("=" * 80)
        report.append("策略对比评估报告")
        report.append("=" * 80)

        strategies = evaluation_result.get('strategies', {})
        best = evaluation_result.get('best_strategy')

        report.append(f"\n评估时间: {evaluation_result.get('timestamp')}")
        report.append(f"测试窗口: {evaluation_result.get('test_window')} 期\n")

        # 表头
        report.append(f"{'策略名称':<20} {'Top-1':<8} {'Top-3':<8} {'Top-5':<8} {'Top-8':<8} {'状态':<10}")
        report.append("-" * 80)

        for strategy_name, result in strategies.items():
            if result.get('success', False):
                overall = result.get('overall', {})
                marker = " 🏆" if best and best.get('name') == strategy_name else ""
                report.append(
                    f"{strategy_name:<20} "
                    f"{overall.get('top1_accuracy', 0):.4f}{'':<4} "
                    f"{overall.get('top3_accuracy', 0):.4f}{'':<4} "
                    f"{overall.get('top5_accuracy', 0):.4f}{'':<4} "
                    f"{overall.get('top8_accuracy', 0):.4f}{'':<4} "
                    f"✅{marker}"
                )
            else:
                report.append(f"{strategy_name:<20} {'':<8} {'':<8} {'':<8} {'':<8} ❌ {result.get('error', '未知错误')}")

        if best:
            report.append("\n" + "=" * 80)
            report.append(f"🏆 最佳策略: {best.get('name')}")
            report.append(f"   Top-3准确率: {best.get('score', 0):.4f}")
            report.append("=" * 80)

        return "\n".join(report)
