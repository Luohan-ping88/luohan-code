#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查模型的特征列信息
"""

from src.core.models.predictor import PL5Predictor

if __name__ == "__main__":
    print("正在检查模型特征信息...")
    
    # 初始化预测器
    predictor = PL5Predictor()
    
    # 加载模型
    print("正在加载模型...")
    load_success = predictor.load_models()
    if not load_success:
        print("模型加载失败")
        exit(1)
    
    # 打印特征列信息
    print(f"模型特征列数量: {len(predictor.feature_cols)}")
    print(f"特征列: {predictor.feature_cols}")
