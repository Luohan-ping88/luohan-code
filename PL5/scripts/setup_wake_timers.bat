@echo off
chcp 65001 >nul
title 设置系统唤醒定时器 - 排列五自动化系统
color 0A

echo.
echo  ╔════════════════════════════════════════════════════════════════════════════════╗
echo  ║                                                                                ║
echo  ║              设置系统唤醒定时器 - 确保睡眠时也能执行任务                        ║
echo  ║                                                                                ║
echo  ╚════════════════════════════════════════════════════════════════════════════════╝
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo  ❌ 错误：需要以管理员身份运行此脚本
    echo  请右键点击此文件，选择"以管理员身份运行"
    pause
    exit /b 1
)

echo  🔧 正在配置系统唤醒设置...
echo.

:: 启用唤醒定时器
echo  [1/5] 启用唤醒定时器...
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP RTCWAKE 1
echo  ✅ 唤醒定时器已启用
echo.

:: 禁用混合睡眠（确保能正常唤醒）
echo  [2/5] 配置睡眠模式...
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP 0
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP HYBRIDSLEEP 0
echo  ✅ 混合睡眠已禁用
echo.

:: 设置允许唤醒
echo  [3/5] 配置允许唤醒...
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP AWAYMODE 0
echo  ✅ 离开模式已配置
echo.

:: 应用电源设置
echo  [4/5] 应用电源设置...
powercfg /SetActive SCHEME_CURRENT
echo  ✅ 电源设置已应用
echo.

:: 显示当前设置
echo  [5/5] 验证设置...
echo  当前唤醒定时器状态:
powercfg /QUERY SCHEME_CURRENT SUB_SLEEP RTCWAKE | findstr "当前"
echo.

echo  ╔════════════════════════════════════════════════════════════════════════════════╗
echo  ║                          唤醒设置配置完成                                       ║
echo  ╚════════════════════════════════════════════════════════════════════════════════╝
echo.
echo  现在系统将在以下时间自动从睡眠中唤醒：
echo    - 22:00  自动获取开奖数据
echo    - 22:15  评估预测逻辑与命中情况
echo    - 02:30  推理逻辑策略优化学习
echo    - 04:00  开始深度学习训练
echo    - 08:00  增量训练（上午）- 首次佐证
echo    - 10:00  首次预测验证（首次佐证）
echo    - 12:00  增量训练（中午）- 二次佐证
echo    - 14:00  增量训练（下午）- 三次佐证
echo    - 16:00  深度策略优化（四次佐证）
echo    - 17:00  预测结果预生成（五次佐证）
echo    - 18:00  生成最终预测结果
echo    - 19:00  验证最终预测结果（六次佐证）
echo    - 20:00  售前最终预测
echo    - 20:15  发送训练报告和最终预测到邮箱
echo.
echo  ⚠️  注意：
echo    1. 确保电脑连接电源（笔记本需要插电）
echo    2. 需要在BIOS中启用"Wake on Timer"或类似选项
echo    3. 某些电脑可能不支持睡眠唤醒功能
echo.
pause
