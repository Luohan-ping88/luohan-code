import json, os
from pathlib import Path
import pytest
from src.core.closed_loop_memory import ClosedLoopMemoryStore

TMP = Path(__file__).parent / "_test_memory.json"

@pytest.fixture(autouse=True)
def clean():
    if TMP.exists():
        TMP.unlink()
    yield
    if TMP.exists():
        TMP.unlink()

def test_append_and_read():
    store = ClosedLoopMemoryStore(path=TMP)
    store.append("evaluations", {"accuracy": 0.3, "k": 3})
    store.append("actions", {"type": "update_param", "param": "max_depth"})
    store.save()
    store2 = ClosedLoopMemoryStore(path=TMP)
    assert len(store2.get("evaluations")) == 1
    assert store2.get("actions")[0]["type"] == "update_param"

def test_merge_legacy_files(tmp_path):
    legacy = tmp_path / "learning_history.json"
    legacy.write_text(json.dumps([{"accuracy": 0.4}]), encoding="utf-8")
    store = ClosedLoopMemoryStore(
        path=tmp_path / "closed_loop_memory.json",
        legacy_sources={"evaluations": [legacy]},
    )
    assert len(store.get("evaluations")) == 1