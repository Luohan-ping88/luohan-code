#!/usr/bin/env python
"""PL5 V11.0 端到端验证测试"""
import requests
import json

print('=' * 60)
print('PL5 V11.0 端到端验证测试')
print('=' * 60)

# 测试 1: 版本检查
print('\n[测试 1] 健康检查和版本验证')
r = requests.get('http://localhost:8000/health')
if r.status_code == 200:
    data = r.json()
    version = data.get('version')
    status = data.get('status')
    print(f'  版本: {version}')
    print(f'  状态: {status}')
    version_ok = version == '11.0.0'
    print(f'  版本正确' if version_ok else '  版本错误')
else:
    print('  健康检查失败')
    version_ok = False

# 测试 2: 登录
print('\n[测试 2] 用户登录')
r = requests.post('http://localhost:8000/api/auth/login', params={'username': 'admin', 'password': 'admin@123'})
if r.status_code == 200:
    token = r.json().get('access_token')
    print('  登录成功')
    login_ok = True
else:
    print('  登录失败')
    login_ok = False
    token = None

# 测试 3: 预测API
print('\n[测试 3] 预测功能验证')
if token:
    r = requests.get('http://localhost:8000/api/pl5/prediction', headers={'Authorization': f'Bearer {token}'})
    if r.status_code == 200:
        data = r.json()
        success = data.get('success', False)
        error = data.get('error', 'No error')
        print(f'  预测成功: {success}')
        print(f'  错误信息: {error}')
        pred_ok = success and error == 'No error'
        print('  预测正常' if pred_ok else '  预测失败')
        if success:
            preds = data.get('predictions', {})
            print('  预测结果 (Top 3):')
            for pos in ['wan', 'qian', 'bai', 'shi', 'ge']:
                if pos in preds:
                    top3 = preds[pos].get('top_k', [])[:3]
                    print(f'    {pos}: {top3}')
    else:
        print('  API调用失败')
        pred_ok = False
else:
    print('  跳过（登录失败）')
    pred_ok = False

# 测试 4: 训练状态
print('\n[测试 4] 训练状态API')
if token:
    r = requests.get('http://localhost:8000/api/pl5/training-status', headers={'Authorization': f'Bearer {token}'})
    if r.status_code == 200:
        data = r.json()
        current_task = data.get('current_task', 'N/A')
        print(f'  当前任务: {current_task}')
        print('  状态API正常')
        status_ok = True
    else:
        print('  状态API失败')
        status_ok = False
else:
    print('  跳过（登录失败）')
    status_ok = False

# 总结
print('\n' + '=' * 60)
print('验证结果汇总')
print('=' * 60)
all_ok = version_ok and login_ok and pred_ok and status_ok
print(f'  版本检查: {"OK" if version_ok else "FAIL"}')
print(f'  用户登录: {"OK" if login_ok else "FAIL"}')
print(f'  预测功能: {"OK" if pred_ok else "FAIL"}')
print(f'  状态API: {"OK" if status_ok else "FAIL"}')
print()
if all_ok:
    print('所有测试通过！系统运行正常！')
else:
    print('部分测试失败，请检查日志')
print('=' * 60)
