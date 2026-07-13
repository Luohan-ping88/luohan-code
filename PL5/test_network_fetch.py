#!/usr/bin/env python3
"""
测试从网络获取排列五数据
"""
import requests
import pandas as pd
from datetime import datetime

def test_fetch_from_network():
    """测试从网络获取数据"""
    url = "http://data.17500.cn/pl5_asc.txt"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive'
    }

    print(f"正在从 {url} 获取数据...")
    print(f"时间: {datetime.now()}")

    try:
        response = requests.get(url, headers=headers, timeout=(10, 30))
        response.encoding = 'utf-8'

        print(f"HTTP状态码: {response.status_code}")
        print(f"数据大小: {len(response.text)} 字符")

        if response.status_code == 200:
            # 解析数据
            lines = response.text.strip().split('\n')
            print(f"数据行数: {len(lines)}")

            # 获取最后几行
            print("\n最后5期数据:")
            for line in lines[-5:]:
                parts = line.split()
                if len(parts) >= 7:
                    period = parts[0]
                    wan, qian, bai, shi, ge = parts[2], parts[3], parts[4], parts[5], parts[6]
                    print(f"  期号: {period}, 号码: {wan}{qian}{bai}{shi}{ge}")

            # 保存到本地
            with open('c:/Users/Administrator/Desktop/PL5/data/raw/pl5_history.txt', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("\n数据已保存到本地文件")

            return True
        else:
            print(f"HTTP错误: {response.status_code}")
            return False

    except requests.Timeout:
        print("请求超时")
        return False
    except requests.ConnectionError:
        print("连接错误，请检查网络")
        return False
    except Exception as e:
        print(f"请求异常: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_fetch_from_network()
    print(f"\n测试结果: {'成功' if success else '失败'}")
