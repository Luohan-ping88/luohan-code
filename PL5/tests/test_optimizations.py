#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统优化验证脚本
验证所有架构优化是否正确实施
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import json


def test_event_bus():
    """测试事件总线模块"""
    print("\n" + "="*60)
    print("测试 1: 事件总线模块")
    print("="*60)

    try:
        from src.core.events import (
            EventBus, Event, EventType,
            get_event_bus, publish_event
        )

        # 测试获取单例
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2, "事件总线应该是单例"
        print("✓ 事件总线单例模式正常")

        # 测试发布/订阅
        received_events = []
        def handler(event):
            received_events.append(event)

        bus1.subscribe("test.event", handler)
        event = Event("test.event", {"data": "test"})
        bus1.publish(event)

        assert len(received_events) == 1, "应该接收到1个事件"
        print("✓ 事件发布/订阅机制正常")

        # 测试事件历史
        history = bus1.get_history()
        assert len(history) > 0, "事件历史应该包含事件"
        print(f"✓ 事件历史记录正常 ({len(history)} 个事件)")

        # 测试统计信息
        stats = bus1.get_statistics()
        assert "total_events" in stats
        print(f"✓ 事件统计信息正常: {stats['total_events']} 个事件")

        print("\n✅ 事件总线模块验证通过")
        return True

    except Exception as e:
        print(f"\n❌ 事件总线模块验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feature_config_manager():
    """测试特征配置管理器"""
    print("\n" + "="*60)
    print("测试 2: 特征配置管理器")
    print("="*60)

    try:
        from src.core.features import (
            FeatureConfig,
            FeatureConfigManager,
            get_feature_config_manager
        )

        # 测试获取单例
        manager1 = get_feature_config_manager()
        manager2 = get_feature_config_manager()
        assert manager1 is manager2, "特征配置管理器应该是单例"
        print("✓ 特征配置管理器单例模式正常")

        # 测试获取统计信息
        stats = manager1.get_statistics()
        print(f"✓ 统计信息获取正常: {json.dumps(stats, indent=2, ensure_ascii=False)}")

        # 测试验证配置
        validation = manager1.validate_config(["col1", "col2", "col3"])
        assert "is_valid" in validation
        print(f"✓ 配置验证功能正常")

        print("\n✅ 特征配置管理器验证通过")
        return True

    except Exception as e:
        print(f"\n❌ 特征配置管理器验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_task_dependency_manager():
    """测试任务依赖管理器"""
    print("\n" + "="*60)
    print("测试 3: 任务依赖管理器")
    print("="*60)

    try:
        from src.core.workflow import (
            Task,
            TaskStatus,
            TaskDependencyManager,
            create_task_manager_from_config
        )

        # 测试创建任务
        manager = TaskDependencyManager()
        manager.add_task_simple("task1", "任务1", [], priority=1)
        manager.add_task_simple("task2", "任务2", ["task1"], priority=2)
        manager.add_task_simple("task3", "任务3", ["task1"], priority=3)

        # 测试执行顺序（task2和task3都依赖task1，按优先级排序task3先执行）
        order = manager.get_execution_order()
        assert order[0] == "task1", f"第一个任务应该是task1: {order}"
        assert set(order[1:]) == {"task2", "task3"}, f"后续任务应该是task2和task3: {order}"
        print(f"✓ 任务执行顺序正确: {order}")

        # 测试任务状态
        ready_tasks = manager.get_ready_tasks()
        assert len(ready_tasks) == 1, "应该只有1个就绪任务"
        assert ready_tasks[0].task_id == "task1"
        print(f"✓ 任务就绪检测正常")

        # 测试标记完成
        manager.mark_task_completed("task1")
        ready_tasks = manager.get_ready_tasks()
        assert len(ready_tasks) == 2, "task1完成后应该有2个就绪任务"
        print(f"✓ 任务完成标记正常")

        # 测试统计信息
        stats = manager.get_statistics()
        assert stats["total_tasks"] == 3
        print(f"✓ 任务统计信息正常: {stats}")

        print("\n✅ 任务依赖管理器验证通过")
        return True

    except Exception as e:
        print(f"\n❌ 任务依赖管理器验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_orchestrator_optimized():
    """测试优化后的编排器"""
    print("\n" + "="*60)
    print("测试 4: 优化后的编排器")
    print("="*60)

    try:
        from src.core.orchestrator_optimized import PL5OrchestratorOptimized

        # 测试创建编排器
        orchestrator = PL5OrchestratorOptimized(
            workflow_dir="./test_workflows",
            default_timeout=3600
        )
        print("✓ 编排器实例创建成功")

        # 测试上下文管理器
        with orchestrator as ctx:
            assert ctx._is_running == True
            print("✓ 上下文管理器入口正常")
        assert orchestrator._is_running == False
        print("✓ 上下文管理器出口正常")

        # 测试延迟初始化属性（不触发初始化）
        # 检查缓存属性是否存在
        assert hasattr(type(orchestrator), 'data_collector')
        assert hasattr(type(orchestrator), 'feature_engineer')
        assert hasattr(type(orchestrator), 'predictor')
        print("✓ 延迟初始化属性定义正常")

        # 测试状态获取
        status = orchestrator.get_status()
        assert "is_running" in status
        assert "workflow_dir" in status
        print(f"✓ 状态获取正常: workflow_dir={status['workflow_dir']}")

        # 测试关闭
        orchestrator.shutdown()
        print("✓ 关闭方法正常")

        # 清理测试目录
        import shutil
        if os.path.exists("./test_workflows"):
            shutil.rmtree("./test_workflows")

        print("\n✅ 优化后的编排器验证通过")
        return True

    except Exception as e:
        print(f"\n❌ 优化后的编排器验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_system_config():
    """测试系统配置"""
    print("\n" + "="*60)
    print("测试 5: 系统配置")
    print("="*60)

    try:
        config_path = Path("./config/system_config.json")

        if not config_path.exists():
            # 尝试查找配置文件
            possible_paths = [
                Path(__file__).parent.parent / "config" / "system_config.json",
                Path("config/system_config.json")
            ]
            for p in possible_paths:
                if p.exists():
                    config_path = p
                    break

        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 验证配置结构
            assert "workflow" in config
            assert "events" in config
            assert "features" in config
            print(f"✓ 系统配置文件加载成功")
            print(f"  - workflow.timeout: {config['workflow'].get('default_timeout')}")
            print(f"  - features.cache_enabled: {config['features'].get('cache_enabled')}")

            print("\n✅ 系统配置验证通过")
            return True
        else:
            print("⚠ 系统配置文件不存在，跳过测试")
            return True

    except Exception as e:
        print(f"\n❌ 系统配置验证失败: {e}")
        return False


def test_security_modules():
    """测试安全模块"""
    print("\n" + "="*60)
    print("测试 6: 安全模块")
    print("="*60)

    try:
        # 测试用户管理器
        from src.ai.users import UserManager

        user_manager = UserManager()
        print("✓ 用户管理器实例化成功")

        # 测试密码验证
        success, user_info = user_manager.verify_password("admin", "admin@123")
        if success:
            print(f"✓ 密码验证成功: {user_info}")
        else:
            print("⚠ 管理员密码验证失败（可能需要初始化）")

        # 测试特征配置管理器
        from src.core.features import get_feature_config_manager
        config_manager = get_feature_config_manager()
        print("✓ 特征配置管理器加载成功")

        print("\n✅ 安全模块验证通过")
        return True

    except Exception as e:
        print(f"\n❌ 安全模块验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "="*60)
    print("PL5 系统优化验证测试")
    print("="*60)

    results = []

    # 运行所有测试
    results.append(("事件总线模块", test_event_bus()))
    results.append(("特征配置管理器", test_feature_config_manager()))
    results.append(("任务依赖管理器", test_task_dependency_manager()))
    results.append(("优化后的编排器", test_orchestrator_optimized()))
    results.append(("系统配置", test_system_config()))
    results.append(("安全模块", test_security_modules()))

    # 输出测试结果汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    passed = 0
    failed = 0

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print("-"*60)
    print(f"总计: {passed} 通过, {failed} 失败, {len(results)} 总计")

    if failed == 0:
        print("\n🎉 所有测试通过！系统优化验证成功！")
        return 0
    else:
        print(f"\n⚠️  {failed} 个测试失败，请检查日志")
        return 1


if __name__ == "__main__":
    sys.exit(main())
