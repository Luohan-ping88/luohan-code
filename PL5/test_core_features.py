#!/usr/bin/env python3
"""核心功能测试脚本"""

print('='*70)
print('🧪 核心功能测试')
print('='*70)

# 1. 测试环境变量配置
print('\n1️⃣  测试环境变量配置:')
try:
    from src.core.config.env_config import get_config
    config = get_config()
    print('   ✅ 配置管理器加载成功')
    print(f'   📧 邮件配置: {config.email_config["smtp_server"]}:{config.email_config["smtp_port"]}')
    print(f'   🔧 特征模式: {config.feature_config["feature_mode"]}')
    print(f'   ⚡ C++加速: {"启用" if config.feature_config["enable_cpp_acceleration"] else "禁用"}')
except Exception as e:
    print(f'   ❌ 配置测试失败: {e}')

# 2. 测试邮件发送器
print('\n2️⃣  测试邮件发送器:')
try:
    from src.app.email_sender import EmailSender
    sender = EmailSender()
    print('   ✅ EmailSender初始化成功')
    print(f'   📤 发件人: {sender.sender_email}')
    print(f'   🌐 SMTP: {sender.smtp_server}:{sender.smtp_port}')
except Exception as e:
    print(f'   ❌ EmailSender测试失败: {e}')

# 3. 测试数据加载
print('\n3️⃣  测试数据加载:')
try:
    from pathlib import Path
    data_dir = Path('data')
    data_files = list(data_dir.rglob('*.csv')) + list(data_dir.rglob('*.txt'))
    print(f'   📊 找到 {len(data_files)} 个数据文件')
    for data_file in data_files[:3]:
        print(f'      - {data_file}')
except Exception as e:
    print(f'   ⚠️  数据加载测试有问题: {e}')

# 4. 测试NumPy和Pandas
print('\n4️⃣  测试数据处理库:')
try:
    import numpy as np
    import pandas as pd
    print('   ✅ NumPy版本:', np.__version__)
    print('   ✅ Pandas版本:', pd.__version__)
    test_array = np.array([1, 2, 3, 4, 5])
    test_df = pd.DataFrame({'test': test_array})
    print('   ✅ 基本数据操作正常')
except Exception as e:
    print(f'   ❌ 数据处理库测试失败: {e}')

# 5. 测试特征工程模块
print('\n5️⃣  测试特征工程模块:')
try:
    from src.core.features.config import get_feature_config
    print('   ✅ 特征配置模块导入成功')
except Exception as e:
    print(f'   ⚠️  特征工程模块测试有问题: {e}')

# 6. 测试日志系统
print('\n6️⃣  测试日志系统:')
try:
    # 检查logs目录是否存在
    log_dir = Path('logs')
    if log_dir.exists():
        log_files = list(log_dir.glob('*.log'))
        print(f'   📝 日志目录存在，找到 {len(log_files)} 个日志文件')
    else:
        print('   ℹ️  日志目录不存在 (会自动创建)')
except Exception as e:
    print(f'   ⚠️  日志系统测试有问题: {e}')

print('\n'+'='*70)
print('🎉 核心功能测试完成！')
print('='*70)
