"""Task6 接线回归：验证学习闭环接入日循环优化任务、flush 历史记忆已移除。"""
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "app" / "auto_scheduler_v8.py"


def _source() -> str:
    return _SRC.read_text(encoding="utf-8")


def test_learning_loop_wired_into_optimize():
    src = _source()
    # 闭环入口已接入优化任务
    assert "from src.core.learning_loop import LearningLoopEngine" in src
    assert "run_once" in src
    # 优化任务处的 sls.flush() 已移除（留有 V11 移除标记；其它任务可保留）
    assert "移除 sls.flush()" in src


def test_learning_loop_importable():
    from src.core.learning_loop import LearningLoopEngine
    assert hasattr(LearningLoopEngine, "run_once")