#!/usr/bin/env python
"""
V11全面集成测试脚本
测试V11模式在主流程和调度器中的完整集成
"""
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.utils.logger import get_logger

logger = get_logger('v11_integration_test')


def test_config_update():
    """测试V11配置更新"""
    logger.info("=" * 80)
    logger.info("测试1: V11配置检查")
    logger.info("=" * 80)
    
    config_path = Path(__file__).parent.parent / "config" / "scheduler_config_v8.json"
    
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        return False
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 检查V11配置是否存在
    if 'v11_mode' not in config:
        logger.warning("配置文件中缺少v11_mode配置，添加默认配置")
        config['v11_mode'] = {
            'enabled': False,
            'feature_mode': 'v11_advanced'
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("已添加V11默认配置")
    else:
        logger.info("V11配置已存在")
    
    logger.info(f"当前V11配置: {config['v11_mode']}")
    return True


def test_main_v11_arguments():
    """测试main.py的V11参数"""
    logger.info("=" * 80)
    logger.info("测试2: main.py V11参数检查")
    logger.info("=" * 80)
    
    main_path = Path(__file__).parent.parent / "main.py"
    
    if not main_path.exists():
        logger.error(f"main.py不存在: {main_path}")
        return False
    
    with open(main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查V11相关参数
    checks = {
        '--v11': '--v11参数是否存在',
        '--v11-mode': '--v11-mode参数是否存在',
        'v11_advanced': 'v11_advanced模式是否存在',
        'V11FeatureEngineer': 'V11FeatureEngineer是否被使用'
    }
    
    all_passed = True
    for check, description in checks.items():
        if check in content:
            logger.info(f"✓ {description}")
        else:
            logger.warning(f"✗ {description}")
            all_passed = False
    
    return all_passed


def test_scheduler_v11_support():
    """测试调度器的V11支持"""
    logger.info("=" * 80)
    logger.info("测试3: 调度器V11支持检查")
    logger.info("=" * 80)
    
    scheduler_path = Path(__file__).parent.parent / "src" / "app" / "auto_scheduler_v8.py"
    
    if not scheduler_path.exists():
        logger.error(f"调度器文件不存在: {scheduler_path}")
        return False
    
    with open(scheduler_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查V11相关函数
    checks = {
        '_is_v11_enabled': 'V11启用检查函数',
        '_get_v11_feature_mode': 'V11特征模式获取函数',
        'V11FeatureEngineer': 'V11特征工程师引用',
        'v11_enabled': 'v11_enabled字段使用'
    }
    
    all_passed = True
    for check, description in checks.items():
        if check in content:
            logger.info(f"✓ {description}")
        else:
            logger.warning(f"✗ {description}")
            all_passed = False
    
    return all_passed


def test_v11_feature_engineer():
    """测试V11特征工程师是否可用"""
    logger.info("=" * 80)
    logger.info("测试4: V11特征工程师导入测试")
    logger.info("=" * 80)
    
    try:
        from src.core.features.v11_engineer import V11FeatureEngineer
        logger.info("✓ V11FeatureEngineer导入成功")
        
        # 测试初始化
        engineer = V11FeatureEngineer(mode='v11_advanced')
        logger.info("✓ V11FeatureEngineer初始化成功")
        
        return True
    except Exception as e:
        logger.error(f"✗ V11FeatureEngineer导入或初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_v11_config_toggle():
    """测试V11配置切换"""
    logger.info("=" * 80)
    logger.info("测试5: V11配置切换测试")
    logger.info("=" * 80)
    
    config_path = Path(__file__).parent.parent / "config" / "scheduler_config_v8.json"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        original_config = json.load(f)
    
    try:
        # 测试启用V11
        logger.info("测试启用V11...")
        test_config = original_config.copy()
        test_config['v11_mode']['enabled'] = True
        test_config['v11_mode']['feature_mode'] = 'v11_advanced'
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, indent=2, ensure_ascii=False)
        logger.info("✓ V11启用配置保存成功")
        
        # 测试不同模式
        logger.info("测试V11不同模式配置...")
        for mode in ['v10', 'v11_advanced', 'v11_full']:
            test_config['v11_mode']['feature_mode'] = mode
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(test_config, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ V11模式配置为 {mode}")
        
        # 恢复原始配置
        logger.info("恢复原始配置...")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(original_config, f, indent=2, ensure_ascii=False)
        logger.info("✓ 配置已恢复")
        
        return True
    except Exception as e:
        # 出错时恢复原始配置
        logger.error(f"测试过程出错: {e}")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(original_config, f, indent=2, ensure_ascii=False)
        logger.info("已恢复原始配置")
        return False


def generate_summary_report(results):
    """生成测试总结报告"""
    logger.info("=" * 80)
    logger.info("V11集成测试总结")
    logger.info("=" * 80)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    logger.info(f"总测试数: {total}")
    logger.info(f"通过测试: {passed}")
    logger.info(f"失败测试: {total - passed}")
    
    logger.info("\n详细测试结果:")
    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"  {name}: {status}")
    
    if passed == total:
        logger.info("\n🎉 所有测试通过！V11集成成功！")
        return True
    else:
        logger.warning(f"\n⚠️  有 {total - passed} 个测试失败，请检查")
        return False


def main():
    """主测试函数"""
    logger.info("=" * 80)
    logger.info("开始V11全面集成测试")
    logger.info("=" * 80)
    
    results = {}
    
    # 执行测试
    results['配置更新测试'] = test_config_update()
    results['Main参数测试'] = test_main_v11_arguments()
    results['调度器V11支持'] = test_scheduler_v11_support()
    results['V11特征工程师'] = test_v11_feature_engineer()
    results['V11配置切换'] = test_v11_config_toggle()
    
    # 生成报告
    success = generate_summary_report(results)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
