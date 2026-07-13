"""
推理研究分析并自动发送报告到邮箱
V10.0: Stacking+HMM+Copula+BSTS+Mamba+iTransformer + 贝叶斯不确定性量化
"""

import logging
import smtplib
import numpy as np
import pandas as pd
from datetime import datetime
from .email_sender import EmailSender, generate_html_report
from src.core.utils.logger import logger


def _format_verification_report(verification_results: dict) -> str:
    """【V2修复】将佐证链验证结果格式化为文本段落"""
    if not verification_results:
        return "  （佐证链结果尚未生成，任务可能尚未执行）"
    
    lines = []
    round_labels = {
        'first_verification': '首次佐证',
        'second_verification': '二次佐证',
        'third_verification': '三次佐证',
        'final_verification': '最终预测验证',
        'deep_strategy': '深度策略优化',
    }
    
    for key, label in round_labels.items():
        if key in verification_results:
            vr = verification_results[key]
            ts = vr.get('verification_time', vr.get('optimization_time', '未知'))
            next_p = vr.get('next_period', '未知')
            
            if key == 'deep_strategy':
                best_strat = vr.get('best_strategy', '未知')
                best_score = vr.get('best_score', 0)
                lines.append(f"  [{label}] 时间: {ts}")
                lines.append(f"    最佳策略: {best_strat}, 得分: {best_score:.4f}")
            else:
                predictions = vr.get('predictions', vr.get('verification_predictions', {}))
                lines.append(f"  [{label}] 时间: {ts}, 预测期号: {next_p}")
                for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                    if pos in predictions and 'top_k' in predictions[pos]:
                        top_k = predictions[pos]['top_k']
                        lines.append(f"    {pos}: {top_k}")
    
    return "\n".join(lines) if lines else "  （无有效佐证结果）"


def analyze_and_send(verification_results=None, precomputed_predictions=None):
    """完成推理研究分析并发送邮件 — 使用已训练的 EnhancedPL5Predictor 模型
    
    Args:
        verification_results: 可选的佐证链验证结果字典。
            如果为 None，函数会尝试从 logs 目录读取。
        precomputed_predictions: 可选的日循环预计算预测结果（由 task_send_report 传入）。
            如果提供，跳过模型加载+推理，直接使用该预测结果。
            来源：logs/pre_sale_prediction.json 或 logs/final_prediction.json。
    """
    
    import time
    start_time = time.time()
    
    logger.info("=" * 80)
    logger.info("排列五高阶数理分析预测系统 V10.3")
    logger.info("推理研究分析 & 邮件发送")
    logger.info("=" * 80)
    logger.info(f"开始时间: {time.strftime('%H:%M:%S')}")
    
    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    position_names = {
        'wan': '万位', 'qian': '千位', 'bai': '百位',
        'shi': '十位', 'ge': '个位'
    }
    
    # ─────────────────────────────────────────
    # 1. 加载数据 + 特征工程（始终需要，用于生成分析数据）
    # ─────────────────────────────────────────
    logger.info("\n[1] 加载历史数据并执行特征工程...")
    from src.core.data.collector import PL5DataCollector
    from src.core.features.engineer import FeatureEngineer
    from src.core.models.enhanced_predictor import EnhancedPL5Predictor
    
    collector = PL5DataCollector()
    df = collector.update_data()
    if df is None or len(df) == 0:
        logger.error("无法加载数据，终止分析")
        return None
    logger.info(f"  成功加载 {len(df)} 条历史记录 (最新期号: {df['period'].iloc[-1]})")
    
    engineer = FeatureEngineer()
    
    # 【修复】读取与训练一致的特征配置，优先从 logs 目录读取
    import json
    from pathlib import Path
    from src.core.config import LOGS_DIR, MODELS_DIR
    
    select_top = None
    feature_selection_method = None
    for config_dir in [LOGS_DIR, MODELS_DIR]:
        config_path = Path(config_dir) / "best_feature_config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg_data = json.load(f)
                if 'best_config' in cfg_data:
                    select_top = cfg_data['best_config'].get('select_top')
                    feature_selection_method = cfg_data['best_config'].get('feature_selection_method')
                else:
                    select_top = cfg_data.get('select_top')
                    feature_selection_method = cfg_data.get('feature_selection_method')
                logger.info(f"  从 {config_dir.name}/best_feature_config.json 加载特征配置: select_top={select_top}, method={feature_selection_method}")
                break
            except Exception as cfg_err:
                logger.warning(f"  读取 {config_dir.name}/best_feature_config.json 失败: {cfg_err}")
    
    df_features = engineer.extract_all_features(
        df,
        select_top=select_top,
        feature_selection_method=feature_selection_method
    )
    
    feature_cols = [
        c for c in df_features.columns
        if c not in ['period', 'date', 'full_number', 'parse_line'] + positions
    ]
    logger.info(f"  特征工程完成: {len(feature_cols)} 个特征")
    
    # ─────────────────────────────────────────
    # 2. 模型推理 — 优先使用日循环预计算结果
    # ─────────────────────────────────────────
    if precomputed_predictions is not None:
        predictions = precomputed_predictions
        logger.info(f"\n[2] 使用日循环预计算预测结果 (跳过模型推理)")
        for pos in positions:
            top3 = predictions.get(pos, {}).get('top_k', [])[:3]
            logger.info(f"  {position_names[pos]}: Top-3 = {top3}")
        # 仍然加载 predictor 用于 HMM/Copula 分析
        predictor = EnhancedPL5Predictor()
        predictor.load_models()
    else:
        logger.info("\n[2] 使用 EnhancedPL5Predictor 模型推理...")
        
        predictor = EnhancedPL5Predictor()
        model_loaded = predictor.load_models()

        old_feature_count = 0
        need_retrain = False
        if model_loaded and hasattr(predictor, 'feature_cols') and predictor.feature_cols:
            old_feature_count = len(predictor.feature_cols)
            new_feature_count = len(feature_cols)
            if old_feature_count != new_feature_count:
                logger.warning(f"  特征维度不匹配: 旧模型{old_feature_count}维，新数据{new_feature_count}维，需要重新训练")
                need_retrain = True

        v10_complete = (
            model_loaded and
            getattr(predictor, 'mamba_predictor', None) is not None and
            getattr(predictor, 'itransformer_predictor', None) is not None and
            getattr(predictor, 'bayesian_quantifier', None) is not None
        )
        if model_loaded and not v10_complete:
            logger.warning(
                "  V10模块不完整 (缺少Mamba/iTransformer/Bayesian)，"
                "将重新训练以获得完整的6模型融合能力"
            )
            need_retrain = True

        from src.core.models.incremental_learning import (
            should_perform_incremental_update,
            get_training_strategy,
            get_training_parameters,
            update_training_timestamp
        )
        
        if model_loaded and not need_retrain:
            if should_perform_incremental_update():
                need_retrain = True
                logger.info("  需要增量更新，将执行训练")
            else:
                logger.info("  已加载持久化模型 (V10完整版)，无需更新")
        
        if need_retrain or not model_loaded:
            if need_retrain:
                reasons = []
                if not model_loaded:
                    reasons.append("模型文件不存在")
                if model_loaded and old_feature_count != len(feature_cols):
                    reasons.append(f"特征维度变化({old_feature_count}->{len(feature_cols)})")
                if not v10_complete:
                    reasons.append("V10新模块缺失")
                if should_perform_incremental_update():
                    reasons.append("需要增量更新")
                logger.warning(f"  需要训练: {' + '.join(reasons)}")
            else:
                logger.warning("  模型文件不存在，执行即时训练...")
            
            strategy = get_training_strategy()
            params = get_training_parameters()
            logger.info(f"  使用训练策略: {strategy}")
            logger.info(f"  训练参数: {params}")
            
            predictor.fit(df_features, feature_cols, parallel=True, incremental=strategy != "deep")
            predictor.save_models()
            update_training_timestamp(strategy)
            
            logger.info("  训练完成并已保存模型 (含V10完整模块)")
            logger.info(f"  训练策略: {strategy}")
            logger.info(f"  预计训练时间: {params['train_time']} 小时")
        
        latest_features = df_features[feature_cols].iloc[-1].values
        recent_original_data = {pos: df[pos].values for pos in positions}
        
        predictions = predictor.predict(
            latest_features,
            recent_original_data=recent_original_data,
            top_k=8
        )
        
        logger.info("  模型推理完成")
        for pos in positions:
            top3 = predictions[pos]['top_k'][:3]
            logger.info(f"  {position_names[pos]}: Top-3 = {top3}")
    
    # ─────────────────────────────────────────
    # 3. 生成深度分析数据（基于真实模型输出）
    # ─────────────────────────────────────────
    logger.info("\n[3] 生成深度分析数据...")
    
    recent_30 = df.tail(30)
    recent_10 = df.tail(10)
    
    # 频率统计（作为辅助参考）
    analysis_results = {}
    for pos in positions:
        pos_data = recent_30[pos]
        analysis_results[pos] = {
            'hot_numbers': pos_data.value_counts().head(3).index.tolist(),
            'cold_numbers': pos_data.value_counts().tail(3).index.tolist(),
            'odd_ratio': float((pos_data % 2).sum() / 30),
            'big_ratio': float((pos_data >= 5).sum() / 30),
            'road_dist': [
                float((pos_data % 3 == 0).sum() / 30),
                float((pos_data % 3 == 1).sum() / 30),
                float((pos_data % 3 == 2).sum() / 30)
            ],
            'trend': "上升" if pos_data.tail(5).mean() > pos_data.head(25).mean() else "下降",
            'mean': float(pos_data.mean()),
            'std': float(pos_data.std())
        }
    
    # Copula 分析（使用真实模型数据）
    copula_data = {'mean_tau': 0.0, 'strongest_pair': 'N/A', 'max_tau': 0.0}
    if hasattr(predictor, 'copula_model') and predictor.copula_model is not None:
        if hasattr(predictor.copula_model, 'kendall_tau') and predictor.copula_model.kendall_tau is not None:
            tau = predictor.copula_model.kendall_tau
            copula_data = {
                'mean_tau': float(np.mean(np.abs(tau))),
                'max_tau': 0.0,
                'strongest_pair': 'N/A'
            }
            max_tau = 0.0
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    if abs(tau[i, j]) > max_tau:
                        max_tau = abs(tau[i, j])
                        copula_data['strongest_pair'] = f"{positions[i]}-{positions[j]}"
            copula_data['max_tau'] = float(max_tau)
    
    # HMM 状态（使用真实模型输出）
    state_names_map = ['cold', 'hot', 'transition', 'mean_reversion']
    hmm_states = {}
    if hasattr(predictor, 'hmm_models'):
        for pos in positions:
            if pos in predictor.hmm_models:
                hmm = predictor.hmm_models[pos]
                recent_data = df[pos].values[-5:]
                try:
                    if hasattr(hmm, 'predict_states'):
                        states = hmm.predict_states(recent_data)
                        if len(states) > 0:
                            state_idx = int(states[-1]) % len(state_names_map)
                            state = state_names_map[state_idx]
                            if hasattr(hmm, 'get_state_probabilities'):
                                state_prob = float(np.max(hmm.get_state_probabilities(recent_data)))
                            else:
                                state_prob = 0.5
                        else:
                            state = 'unknown'
                            state_prob = 0.0
                    else:
                        state = 'unknown'
                        state_prob = 0.0
                except Exception as e:
                    logger.warning(f"  HMM状态分析失败: {e}")
                    state = 'unknown'
                    state_prob = 0.0
            else:
                state = 'unknown'
                state_prob = 0.0
            hmm_states[pos] = {
                'state': state,
                'probability': state_prob
            }
    
    analysis_data = {
        'copula': copula_data,
        'hmm_states': hmm_states,
        'form_analysis': {
            pos: {
                'hot_numbers': analysis_results[pos]['hot_numbers'],
                'cold_numbers': analysis_results[pos]['cold_numbers'],
                'odd_ratio': f"{analysis_results[pos]['odd_ratio']:.1%}",
                'big_ratio': f"{analysis_results[pos]['big_ratio']:.1%}",
                'trend': analysis_results[pos]['trend']
            }
            for pos in positions
        }
    }
    
    # ─────────────────────────────────────────
    # 4. 生成详细文本报告
    # ─────────────────────────────────────────
    logger.info("\n[4] 生成详细分析报告...")
    
    last_period = int(df['period'].iloc[-1])
    period = str(last_period + 1)
    
    # 加载训练信息
    training_info = {
        'model_version': 'V10.3',
        'training_time': 0,
        'feature_count': len(feature_cols),
        'data_count': len(df),
        'latest_period': str(df['period'].iloc[-1]),
        'training_status': 'SUCCESS'
    }
    
    from pathlib import Path
    import json
    training_info_path = Path(__file__).parent.parent / 'logs' / 'training_info.json'
    training_info = {}
    if training_info_path.exists():
        with open(training_info_path, 'r', encoding='utf-8') as f:
            training_info = json.load(f)
    
    # 【V2修复】读取日循环佐证链结果，包含首次/二次/三次预测验证
    # 优先使用外部传入的 verification_results（如 auto_scheduler_v8 调用时）
    if verification_results is None:
        LOGS_DIR = Path(__file__).parent.parent / 'logs'
        verification_results = {}
        verification_files = {
            'first_verification':  'first_prediction_verification.json',
            'second_verification': 'second_prediction_verification.json',
            'third_verification':  'third_prediction_verification.json',
            'final_verification':  'final_prediction_verification.json',
            'deep_strategy':       'deep_strategy_optimization.json',
        }
        for key, filename in verification_files.items():
            fp = LOGS_DIR / filename
            if fp.exists():
                try:
                    with open(fp, 'r', encoding='utf-8') as vf:
                        verification_results[key] = json.load(vf)
                    logger.info(f"  佐证结果已读取: {filename}")
                except Exception as e:
                    logger.warning(f"  佐证结果读取失败: {filename}: {e}")
    
    text_report = f"""
================================================================================
排列五高阶数理分析预测系统 V10.3
第{period}期推理研究分析报告
================================================================================

【一、数据概况】
分析数据量: {len(df)} 条历史记录
数据期号范围: {df['period'].min()} - {df['period'].max()}
分析窗口: 最近30期

【二、模型信息】
模型版本: {training_info.get('model_version', 'V10.3')}
训练状态: {training_info.get('training_status', 'SUCCESS')}
训练时间: {training_info.get('training_time', 0):.2f} 秒
特征数量: {training_info.get('feature_count', len(feature_cols))}
最新数据期号: {training_info.get('latest_period', str(df['period'].iloc[-1]))}

【三、佐证链验证结果】（首次/二次/三次预测验证，用于验证预测稳健性）
""" + _format_verification_report(verification_results) + """

【四、近期开奖回顾（最近10期）】
"""
    
    for idx, row in recent_10.iterrows():
        text_report += f"  第{int(row['period'])}期: {int(row['wan'])}{int(row['qian'])}{int(row['bai'])}{int(row['shi'])}{int(row['ge'])}\n"
    
    text_report += "\n【四、各位置深度分析】\n"
    
    for pos in positions:
        result = analysis_results[pos]
        hmm_state = analysis_data['hmm_states'][pos]
        text_report += f"""
{position_names[pos]}分析:
  热号(近30期出现频率最高): {result['hot_numbers']}
  冷号(近30期出现频率最低): {result['cold_numbers']}
  奇偶比: {result['odd_ratio']:.1%} (奇数占比)
  大小比: {result['big_ratio']:.1%} (大数占比,大数>=5)
  012路分布: 0路={result['road_dist'][0]:.1%}, 1路={result['road_dist'][1]:.1%}, 2路={result['road_dist'][2]:.1%}
  均值: {result['mean']:.2f}, 标准差: {result['std']:.2f}
  趋势判断: {result['trend']}
  HMM状态: {hmm_state['state']} (置信度: {hmm_state['probability']:.1%})
"""
    
    text_report += f"""
【五、跨位置关联分析 (Copula模型)】
最强关联位置对: {analysis_data['copula']['strongest_pair']}
Kendall's tau: {analysis_data['copula']['max_tau']:.4f}
平均关联强度: {analysis_data['copula']['mean_tau']:.4f}

【六、模型预测推荐号码】(基于Stacking+HMM+Copula+BSTS+Mamba+iTransformer 6模型融合)
"""
    
    for pos in positions:
        pred = predictions[pos]
        top_8 = pred['top_k']
        top_5 = pred['top_k'][:5]
        top_3 = pred['top_k'][:3]
        
        # 从 full_distribution 提取 top 概率
        full_dist = pred.get('full_distribution', pred.get('probabilities', []))
        top_probs = []
        for idx_val in top_3:
            if isinstance(full_dist, list) and idx_val < len(full_dist):
                top_probs.append(f'{full_dist[idx_val]:.1%}')
            else:
                top_probs.append('N/A')
        
        text_report += f"""
{position_names[pos]}:
  推荐8个号码: {top_8}
  推荐5个号码: {top_5}
  推荐3个号码: {top_3}
  置信度: {top_probs}
"""
    
    text_report += """
【七、高阶数理方法应用】
1. Stacking集成模型 (RF+GB+ET+AdaBoost) — 多基模型集成
2. 隐马尔可夫模型(HMM) — GMM发射概率+自适应状态数
3. Copula联合分布 — 捕捉位置间非线性依赖
4. 贝叶斯结构时序模型(BSTS) — 趋势+季节+异常检测
5. Mamba选择性状态空间模型 — O(L)线性复杂度序列建模
6. iTransformer变量维度注意力 — 位置间动态交互建模
7. 贝叶斯不确定性量化 — 概率校准+共形预测+认知/偶然分解
8. 特征工程 — 多尺度特征提取+漂移检测

【八、风险提示】
1. 彩票本质是概率游戏，任何模型均只能提升概率优势，无法保证100%中奖
2. 本报告仅用于数理研究与规律分析，不构成购彩建议
3. 请理性购彩，量力而行

================================================================================
报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
排列五高阶数理分析预测系统 V10.3 | 增强版
================================================================================
"""
    
    # ─────────────────────────────────────────
    # 5. 发送邮件（带重试机制）
    # ─────────────────────────────────────────
    logger.info("\n[5] 发送邮件...")
    
    html_report = generate_html_report(period, predictions, analysis_data, len(df), str(df['period'].iloc[-1]))
    
    # 读取邮箱配置 — 优先从 config/ 目录读取，兼容旧路径
    config_path_new = Path(__file__).parent.parent.parent / 'config' / 'email_config.json'
    config_path_old = Path(__file__).parent.parent.parent / 'email_config.json'
    if config_path_new.exists():
        with open(config_path_new, 'r', encoding='utf-8') as f:
            email_config = json.load(f)
        sender_email = email_config.get('from_email', 'your_email@qq.com')
        auth_code = email_config.get('auth_code', 'your_auth_code')
        recipient_email = email_config.get('to_email', sender_email)
    elif config_path_old.exists():
        logger.warning(f"邮件配置使用旧路径(建议迁移至 config/ 目录): {config_path_old}")
        with open(config_path_old, 'r', encoding='utf-8') as f:
            email_config = json.load(f)
        sender_email = email_config.get('from_email', 'your_email@qq.com')
        auth_code = email_config.get('auth_code', 'your_auth_code')
        recipient_email = email_config.get('to_email', sender_email)
    else:
        logger.warning(
            f"邮件配置文件未找到，将尝试从环境变量读取。\n"
            f"请将 email_config.json 放置到以下路径之一:\n"
            f"  - 推荐路径: {config_path_new}\n"
            f"  - 兼容路径: {config_path_old}"
        )
        import os
        sender_email = os.environ.get('PL5_EMAIL', 'your_email@qq.com')
        auth_code = os.environ.get('PL5_AUTH_CODE', 'your_auth_code')
        recipient_email = os.environ.get('PL5_RECIPIENT', sender_email)
    
    # 发送邮件（最多重试3次，间隔递增）
    email_sent = False
    max_retries = 3
    retry_delays = [5, 15, 30]  # 秒
    for attempt in range(max_retries):
        try:
            sender = EmailSender(sender_email, auth_code)
            sender.send_report(
                recipient_email=recipient_email,
                subject=f"排列五第{period}期预测分析报告 V10.3 - {datetime.now().strftime('%Y-%m-%d')}",
                html_content=html_report,
                text_content=text_report
            )
            logger.info(f"  邮件发送成功: {recipient_email}")
            email_sent = True
            break
        except smtplib.SMTPAuthenticationError as auth_err:
            logger.error(f"  SMTP认证失败（账号或授权码错误），不再重试: {auth_err}")
            break
        except smtplib.SMTPException as smtp_err:
            if attempt < max_retries - 1:
                delay = retry_delays[attempt] if attempt < len(retry_delays) else 30
                logger.warning(f"  SMTP错误第{attempt+1}次，{delay}秒后重试: {smtp_err}")
                time.sleep(delay)
            else:
                logger.error(f"  SMTP发送失败，已达最大重试次数: {smtp_err}")
        except Exception as e:
            logger.error(f"  邮件发送异常: {str(e)}")
            break
    
    if not email_sent:
        logger.info("\n[备用方案] 保存报告到本地文件...")
        
        from src.core.config import RESULTS_DIR
        report_path = RESULTS_DIR / f"prediction_{period}_report.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(text_report)
        logger.info(f"  报告已保存: {report_path}")
        
        html_path = RESULTS_DIR / f"prediction_{period}_report.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_report)
        logger.info(f"  HTML报告已保存: {html_path}")
    
    # ─────────────────────────────────────────
    # 6. 输出报告摘要
    # ─────────────────────────────────────────
    logger.info("\n" + "=" * 80)
    logger.info("[预测结果摘要]")
    logger.info("=" * 80)
    
    for pos in positions:
        logger.info(f"\n{position_names[pos]}:")
        logger.info(f"  8码: {predictions[pos]['top_k']}")
        logger.info(f"  5码: {predictions[pos]['top_k'][:5]}")
        logger.info(f"  3码: {predictions[pos]['top_k'][:3]}")
    
    # 计算总执行时间
    end_time = time.time()
    total_duration = end_time - start_time
    logger.info(f"\n总执行时间: {total_duration:.2f} 秒")
    logger.info(f"结束时间: {time.strftime('%H:%M:%S')}")
    
    # 检查是否在20:15前完成（邮件发送时间为20:15）
    current_time = time.localtime()
    if current_time.tm_hour < 20 or (current_time.tm_hour == 20 and current_time.tm_min < 15):
        logger.info("✓ 预测和邮件发送在20:15前完成")
    else:
        logger.warning("⚠ 预测和邮件发送超过20:15")
    
    logger.info("\n" + "=" * 80)
    logger.info("V10.3 模型推理分析完成!")
    logger.info("=" * 80)
    
    return {
        'period': period,
        'predictions': predictions,
        'analysis_data': analysis_data,
        'text_report': text_report,
        'html_report': html_report,
        'training_info': training_info,
        'execution_time': total_duration
    }


if __name__ == "__main__":
    result = analyze_and_send()
