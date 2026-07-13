# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "e:/PL5")
import os

# 检查配置文件
yaml_path = "config/model_config.yaml"
json_path = "config/model_config.json"
print(f"model_config.yaml 存在: {os.path.exists(yaml_path)}")
print(f"model_config.json 存在: {os.path.exists(json_path)}")

if os.path.exists(yaml_path):
    with open(yaml_path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"\nmodel_config.yaml 内容 ({len(content)} bytes):")
    print(content[:3000])

# 检查 ModelConfig 类
print("\n\n=== ModelConfig 属性 ===")
from src.core.config import ModelConfig, get_model_config
cfg = get_model_config()
print(f"类型: {type(cfg)}")
print(f"dir: {[x for x in dir(cfg) if not x.startswith('_')]}")

# 找 max_depth 和 learning_rate
print("\n查找 max_depth/learning_rate 相关配置:")
try:
    md = cfg.get("stacking.base_config.max_depth")
    print(f"  stacking.base_config.max_depth = {md}")
except Exception as e:
    print(f"  获取失败: {e}")

try:
    lr = cfg.get("stacking.base_config.learning_rate")
    print(f"  stacking.base_config.learning_rate = {lr}")
except Exception as e:
    print(f"  获取失败: {e}")

try:
    ra = cfg.get("stacking.base_config.reg_alpha")
    print(f"  stacking.base_config.reg_alpha = {ra}")
except Exception as e:
    print(f"  获取失败: {e}")

try:
    rl = cfg.get("stacking.base_config.reg_lambda")
    print(f"  stacking.base_config.reg_lambda = {rl}")
except Exception as e:
    print(f"  获取失败: {e}")

# 检查可设置的属性
print("\n检查 ModelConfig.set 方法:")
if hasattr(cfg, 'set'):
    import inspect
    sig = inspect.signature(cfg.set)
    print(f"  cfg.set 签名: {sig}")
