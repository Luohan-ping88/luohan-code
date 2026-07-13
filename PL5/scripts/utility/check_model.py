#!/usr/bin/env python
"""检查模型文件状态"""
import sys
sys.path.insert(0, '.')
import os

f = 'src/models/pl5_predictor_trained.pkl'
exists = os.path.exists(f)
size = os.path.getsize(f) if exists else 0

print(f'模型文件存在: {exists}')
print(f'文件大小: {size} bytes ({size/1024:.2f} KB)')

if exists and size > 0:
    print('\n模型文件已生成成功！')
    # 尝试加载模型
    import pickle
    try:
        with open(f, 'rb') as mf:
            model_data = pickle.load(mf)
        print(f'模型组件: {list(model_data.keys())}')
        print(f'是否已训练: {model_data.get("is_trained", False)}')
        print(f'特征列数量: {len(model_data.get("feature_cols", []))}')
    except Exception as e:
        print(f'加载模型失败: {e}')
else:
    print('\n模型文件未生成或为空！')
