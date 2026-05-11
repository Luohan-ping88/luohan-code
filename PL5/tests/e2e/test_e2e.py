#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PL5 排列五预测系统端到端测试脚本
测试整个系统的端到端功能完整性
"""

import asyncio
import time
import logging
import os
import pytest
from datetime import datetime

from src.core.orchestrator import PL5Orchestrator
from src.core.automation.scheduler import PL5AutomationScheduler
from src.core.utils import setup_logging

# 配置日志
setup_logging()
logger = logging.getLogger(__name__)


class TestE2E:
    """端到端测试类"""

    def setup_class(self):
        """测试类初始化"""
        logger.info("=" * 80)
        logger.info("开始端到端测试")
        logger.info("=" * 80)
        self.orchestrator = None
        self.scheduler = None

    def teardown_class(self):
        """测试类清理"""
        if self.orchestrator:
            self.orchestrator.shutdown()
        if self.scheduler:
            self.scheduler.stop()
        logger.info("=" * 80)
        logger.info("端到端测试完成")
        logger.info("=" * 80)

    def test_data_collection(self):
        """测试数据采集与处理功能"""
        logger.info("\n测试数据采集与处理功能")

        async def run_test():
            # 初始化编排器
            self.orchestrator = PL5Orchestrator()

            # 执行数据处理
            result = await self.orchestrator._stage_data_processing({})

            # 验证结果
            assert result["success"], f"数据采集失败: {result.get('error', '未知错误')}"
            assert "record_count" in result, "数据采集结果缺少记录数"
            assert result["record_count"] > 0, "数据采集记录数为0"

            logger.info(f"数据采集成功，记录数: {result['record_count']}")

        asyncio.run(run_test())

    def test_model_training(self):
        """测试模型训练功能"""
        logger.info("\n测试模型训练功能")

        async def run_test():
            # 初始化编排器
            if not self.orchestrator:
                self.orchestrator = PL5Orchestrator()

            # 执行训练流程
            result = await self.orchestrator.execute_training_pipeline()

            # 验证结果
            assert result["success"], f"训练失败: {result.get('error', '未知错误')}"
            assert "results" in result, "训练结果缺少结果数据"
            assert "model_evaluation" in result["results"], "训练结果缺少模型评估"
            assert "evaluation" in result["results"]["model_evaluation"], "训练结果缺少评估数据"
            assert "overall_accuracy" in result["results"]["model_evaluation"]["evaluation"], "训练结果缺少准确率"

            accuracy = result["results"]["model_evaluation"]["evaluation"]["overall_accuracy"]
            logger.info(f"训练成功，准确率: {accuracy:.4f}")

        asyncio.run(run_test())

    def test_prediction(self):
        """测试预测功能"""
        logger.info("\n测试预测功能")

        async def run_test():
            # 初始化编排器
            if not self.orchestrator:
                self.orchestrator = PL5Orchestrator()

            # 执行预测流程
            result = await self.orchestrator.execute_prediction_pipeline()

            # 验证结果
            assert result["success"], f"预测失败: {result.get('error', '未知错误')}"
            assert "next_period" in result, "预测结果缺少期号"
            assert "predictions" in result, "预测结果缺少预测数据"
            assert isinstance(result["predictions"], dict), "预测结果格式错误"

            # 验证预测结果格式
            for pos, pred in result["predictions"].items():
                assert "top_k" in pred, f"位置 {pos} 缺少top_k数据"
                assert len(pred["top_k"]) > 0, f"位置 {pos} top_k数据为空"

            logger.info(f"预测成功，期号: {result['next_period']}")
            logger.info("预测结果:")
            for pos, pred in result["predictions"].items():
                logger.info(f"{pos}: {pred['top_k'][:5]}")

        asyncio.run(run_test())

    def test_automation_scheduler(self):
        """测试自动化调度功能"""
        logger.info("\n测试自动化调度功能")

        # 初始化调度器
        self.scheduler = PL5AutomationScheduler()

        # 启动调度器
        self.scheduler.start()

        # 验证调度器状态
        status = self.scheduler.get_status()
        assert status["is_running"], "调度器未成功启动"
        assert "data_collection" in status["scheduler_jobs"], "调度器缺少数据采集任务"
        assert "system_check" in status["scheduler_jobs"], "调度器缺少系统检查任务"

        logger.info("调度器启动成功")
        logger.info(f"调度器状态: {status}")

        # 等待一段时间，确保系统检查任务执行
        time.sleep(2)

        # 停止调度器
        self.scheduler.stop()

        # 验证调度器已停止
        status = self.scheduler.get_status()
        assert not status["is_running"], "调度器未成功停止"
        assert len(status["scheduler_jobs"]) == 0, "调度器任务未清空"

        logger.info("调度器停止成功")

    def test_full_workflow(self):
        """测试完整工作流程"""
        logger.info("\n测试完整工作流程")

        async def run_test():
            # 初始化编排器
            self.orchestrator = PL5Orchestrator()

            # 执行完整工作流程
            logger.info("1. 执行数据处理")
            data_result = await self.orchestrator._stage_data_processing({})
            assert data_result["success"], f"数据处理失败: {data_result.get('error', '未知错误')}"

            logger.info("2. 执行训练流程")
            train_result = await self.orchestrator.execute_training_pipeline()
            assert train_result["success"], f"训练失败: {train_result.get('error', '未知错误')}"

            logger.info("3. 执行预测流程")
            predict_result = await self.orchestrator.execute_prediction_pipeline()
            assert predict_result["success"], f"预测失败: {predict_result.get('error', '未知错误')}"

            logger.info("完整工作流程执行成功")

        asyncio.run(run_test())

    def test_system_status(self):
        """测试系统状态获取功能"""
        logger.info("\n测试系统状态获取功能")

        # 初始化编排器
        if not self.orchestrator:
            self.orchestrator = PL5Orchestrator()

        # 获取系统状态
        status = self.orchestrator.get_status()

        # 验证状态数据
        assert "is_running" in status, "系统状态缺少运行状态"
        assert "components" in status, "系统状态缺少组件状态"
        assert "execution_history" in status, "系统状态缺少执行历史"

        logger.info("系统状态获取成功")
        logger.info(f"系统状态: {status}")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
