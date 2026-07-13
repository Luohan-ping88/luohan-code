"""
PL5系统测试配置和共享夹具
提供测试数据生成、mock对象和通用测试工具
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os
import json
import tempfile
import shutil
from typing import Dict, List, Optional, Tuple, Any
from unittest.mock import Mock, MagicMock, patch
import warnings

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 测试数据目录
TEST_DATA_DIR = project_root / "tests" / "fixtures"
TEST_DATA_DIR.mkdir(exist_ok=True)

# 忽略警告
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


# ═══════════════════════════════════════════════════════════════
# 测试数据生成器
# ═══════════════════════════════════════════════════════════════

class TestDataGenerator:
    """测试数据生成器 - 提供各种测试数据集"""
    
    POSITIONS = ['wan', 'qian', 'bai', 'shi', 'ge']
    
    @staticmethod
    def generate_pl5_sequence(
        n_records: int = 100, 
        start_period: int = 2026001,
        add_noise: bool = False,
        seed: int = 42
    ) -> pd.DataFrame:
        """生成PL5序列数据"""
        np.random.seed(seed)
        periods = [str(start_period + i) for i in range(n_records)]
        
        data = {
            'period': periods,
            'wan': np.random.randint(0, 10, n_records),
            'qian': np.random.randint(0, 10, n_records),
            'bai': np.random.randint(0, 10, n_records),
            'shi': np.random.randint(0, 10, n_records),
            'ge': np.random.randint(0, 10, n_records)
        }
        
        df = pd.DataFrame(data)
        df['full_number'] = (
            df['wan'].astype(str) + 
            df['qian'].astype(str) + 
            df['bai'].astype(str) + 
            df['shi'].astype(str) + 
            df['ge'].astype(str)
        )
        
        if add_noise:
            # 添加一些模式
            for i in range(1, n_records):
                if np.random.random() < 0.3:  # 30%概率延续趋势
                    for pos in TestDataGenerator.POSITIONS:
                        df.loc[i, pos] = (df.loc[i-1, pos] + np.random.randint(-1, 2)) % 10
        
        return df
    
    @staticmethod
    def generate_features(
        n_samples: int = 100, 
        n_features: int = 50,
        seed: int = 42
    ) -> pd.DataFrame:
        """生成特征数据"""
        np.random.seed(seed)
        
        features = pd.DataFrame(
            np.random.randn(n_samples, n_features),
            columns=[f'feature_{i}' for i in range(n_features)]
        )
        
        # 添加目标变量
        for pos in TestDataGenerator.POSITIONS:
            features[pos] = np.random.randint(0, 10, n_samples)
        
        return features
    
    @staticmethod
    def generate_raw_text_data(n_records: int = 50) -> str:
        """生成原始文本格式的PL5数据"""
        lines = []
        start_period = 2026001
        
        for i in range(n_records):
            period = start_period + i
            date = f"2026-{((i % 12) + 1):02d}-{(i % 28) + 1:02d}"
            wan = np.random.randint(0, 10)
            qian = np.random.randint(0, 10)
            bai = np.random.randint(0, 10)
            shi = np.random.randint(0, 10)
            ge = np.random.randint(0, 10)
            
            line = f"{period} {date} {wan} {qian} {bai} {shi} {ge} {wan}{qian}{bai}{shi}{ge}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def generate_invalid_data(
        invalid_type: str = 'mixed'
    ) -> pd.DataFrame:
        """生成包含各种问题的无效数据"""
        np.random.seed(42)
        n = 20
        
        data = {
            'period': [f'2026{i:03d}' for i in range(n)],
            'wan': np.random.randint(0, 10, n),
            'qian': np.random.randint(0, 10, n),
            'bai': np.random.randint(0, 10, n),
            'shi': np.random.randint(0, 10, n),
            'ge': np.random.randint(0, 10, n)
        }
        
        if invalid_type in ('missing', 'mixed'):
            # 添加缺失值
            data['wan'][5] = None
            data['qian'][10] = np.nan
        
        if invalid_type in ('out_of_range', 'mixed'):
            # 添加超出范围的值
            data['bai'][3] = 15
            data['shi'][7] = -1
        
        if invalid_type in ('invalid_period', 'mixed'):
            # 添加无效期号
            data['period'][2] = 'invalid'
            data['period'][8] = ''
        
        if invalid_type in ('duplicates', 'mixed'):
            # 添加重复期号
            data['period'][15] = data['period'][14]
        
        return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════
# Pytest Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def sample_pl5_data():
    """创建样本PL5数据"""
    return TestDataGenerator.generate_pl5_sequence(n_records=50)


@pytest.fixture
def sample_large_dataset():
    """创建较大的样本数据集"""
    return TestDataGenerator.generate_pl5_sequence(n_records=500)


@pytest.fixture
def sample_invalid_data():
    """创建包含问题的样本数据"""
    return TestDataGenerator.generate_invalid_data(invalid_type='mixed')


@pytest.fixture
def sample_duplicate_data():
    """创建包含重复数据的样本"""
    df = TestDataGenerator.generate_pl5_sequence(n_records=20)
    # 添加重复行
    duplicate = df.iloc[5:8].copy()
    return pd.concat([df, duplicate], ignore_index=True)


@pytest.fixture
def sample_feature_data():
    """创建样本特征数据"""
    return TestDataGenerator.generate_features(n_samples=100, n_features=50)


@pytest.fixture
def sample_raw_text():
    """创建样本原始文本数据"""
    return TestDataGenerator.generate_raw_text_data(n_records=30)


@pytest.fixture
def test_config():
    """测试配置"""
    return {
        'test_mode': True,
        'use_mock_data': True,
        'max_test_records': 100,
        'validation_level': 'standard',
        'model_params': {
            'n_estimators': 10,
            'max_depth': 3,
            'random_state': 42
        }
    }


@pytest.fixture(scope="session")
def test_logger():
    """测试日志器"""
    import logging
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        ))
        logger.addHandler(handler)
    return logger


@pytest.fixture
def temp_directory():
    """创建临时目录"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_data_collector():
    """创建Mock数据采集器"""
    collector = Mock()
    collector.fetch_from_network.return_value = TestDataGenerator.generate_raw_text_data(20)
    collector.load_local_data.return_value = TestDataGenerator.generate_pl5_sequence(20)
    collector.update_data.return_value = TestDataGenerator.generate_pl5_sequence(20)
    return collector


@pytest.fixture
def mock_feature_engineer():
    """创建Mock特征工程器"""
    engineer = Mock()
    engineer.extract_all_features.return_value = TestDataGenerator.generate_features(50, 30)
    return engineer


@pytest.fixture
def mock_predictor():
    """创建Mock预测器"""
    predictor = Mock()
    predictor.predict.return_value = {
        'wan': {'top_k': [1, 2, 3, 4, 5], 'probabilities': [0.2, 0.15, 0.12, 0.1, 0.08]},
        'qian': {'top_k': [2, 3, 4, 5, 6], 'probabilities': [0.18, 0.16, 0.14, 0.12, 0.1]},
        'bai': {'top_k': [3, 4, 5, 6, 7], 'probabilities': [0.22, 0.18, 0.15, 0.12, 0.1]},
        'shi': {'top_k': [4, 5, 6, 7, 8], 'probabilities': [0.2, 0.17, 0.15, 0.13, 0.11]},
        'ge': {'top_k': [5, 6, 7, 8, 9], 'probabilities': [0.19, 0.17, 0.16, 0.14, 0.12]}
    }
    return predictor


# ═══════════════════════════════════════════════════════════════
# 测试标记
# ═══════════════════════════════════════════════════════════════

def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line("markers", "slow: 慢速测试（需要较长时间）")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "performance: 性能测试")
    config.addinivalue_line("markers", "unit: 单元测试")
    config.addinivalue_line("markers", "data: 数据相关测试")
    config.addinivalue_line("markers", "model: 模型相关测试")
    config.addinivalue_line("markers", "validation: 验证测试")
    config.addinivalue_line("markers", "e2e: 端到端测试")


# ═══════════════════════════════════════════════════════════════
# 测试辅助函数
# ═══════════════════════════════════════════════════════════════

def assert_dataframe_structure(df: pd.DataFrame, required_columns: List[str]):
    """断言DataFrame包含必需的列"""
    missing = [col for col in required_columns if col not in df.columns]
    assert not missing, f"缺少必需列: {missing}"


def assert_pl5_data_validity(df: pd.DataFrame):
    """断言PL5数据的有效性"""
    positions = ['wan', 'qian', 'bai', 'shi', 'ge']
    
    # 检查必需列
    assert_dataframe_structure(df, ['period'] + positions)
    
    # 检查数值范围
    for pos in positions:
        assert df[pos].between(0, 9).all(), f"{pos} 包含超出0-9范围的值"
    
    # 检查期号格式
    assert df['period'].astype(str).str.match(r'^\d{5,7}$').all(), "期号格式无效"


def create_mock_response(status_code: int = 200, content: str = "", json_data: dict = None):
    """创建Mock响应对象"""
    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.text = content
    mock_response.json.return_value = json_data or {}
    mock_response.headers = {'Content-Type': 'text/plain'}
    return mock_response
