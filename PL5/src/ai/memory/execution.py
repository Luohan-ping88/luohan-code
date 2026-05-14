"""执行记忆实现"""

from typing import Dict, List, Any, Optional

from .base import BaseMemory
from ..ai_types import MemoryConfig, MemoryType, ExecutionRecord


class ExecutionMemory(BaseMemory):
    """执行记忆

    存储和管理工具执行记录。
    """

    def __init__(self, config: MemoryConfig):
        """初始化执行记忆

        Args:
            config: 记忆配置
        """
        if config.memory_type != MemoryType.EXECUTION:
            config.memory_type = MemoryType.EXECUTION
        super().__init__(config)

    def add(self, item: ExecutionRecord) -> bool:
        """添加执行记录

        Args:
            item: 执行记录

        Returns:
            是否添加成功
        """
        if not isinstance(item, ExecutionRecord):
            return False

        # 检查是否过期
        if self._check_expiry(item):
            return False

        # 添加到存储
        self._store.append(item)

        # 维护大小
        self._maintain_size()

        return True

    def get(self, key: Any = None) -> Optional[ExecutionRecord]:
        """获取执行记录

        Args:
            key: 检索键，可以是索引或工具名称

        Returns:
            执行记录
        """
        if key is None:
            # 返回最新的记录
            return self._store[-1] if self._store else None

        if isinstance(key, int):
            # 按索引获取
            if 0 <= key < len(self._store):
                return self._store[key]
            return None

        if isinstance(key, str):
            # 按工具名称获取最新的记录
            for record in reversed(self._store):
                if record.tool_name == key:
                    return record
            return None

        return None

    def get_all(self) -> List[ExecutionRecord]:
        """获取所有执行记录

        Returns:
            执行记录列表
        """
        # 过滤过期记录
        return [
            record for record in self._store if not self._check_expiry(record)
        ]

    def remove(self, key: Any) -> bool:
        """移除执行记录

        Args:
            key: 检索键，可以是索引或工具名称

        Returns:
            是否移除成功
        """
        if isinstance(key, int):
            # 按索引移除
            if 0 <= key < len(self._store):
                del self._store[key]
                return True
            return False

        if isinstance(key, str):
            # 按工具名称移除所有记录
            original_length = len(self._store)
            self._store = [
                record for record in self._store if record.tool_name != key
            ]
            return len(self._store) < original_length

        return False

    def clear(self) -> bool:
        """清空执行记忆

        Returns:
            是否清空成功
        """
        self._store = []
        return True

    def size(self) -> int:
        """获取执行记录数量

        Returns:
            执行记录数量
        """
        # 过滤过期记录
        return len(
            [
                record
                for record in self._store
                if not self._check_expiry(record)
            ]
        )

    def get_last_n_records(self, n: int) -> List[ExecutionRecord]:
        """获取最近的n条执行记录

        Args:
            n: 记录数量

        Returns:
            执行记录列表
        """
        records = self.get_all()
        return records[-n:] if n > 0 else []

    def get_records_by_tool(self, tool_name: str) -> List[ExecutionRecord]:
        """获取指定工具的执行记录

        Args:
            tool_name: 工具名称

        Returns:
            执行记录列表
        """
        records = self.get_all()
        return [record for record in records if record.tool_name == tool_name]

    def get_success_rate(self, tool_name: Optional[str] = None) -> float:
        """获取执行成功率

        Args:
            tool_name: 工具名称，为None时计算所有工具的成功率

        Returns:
            成功率 (0.0-1.0)
        """
        records = self.get_all()

        if tool_name:
            records = [
                record for record in records if record.tool_name == tool_name
            ]

        if not records:
            return 0.0

        success_count = sum(1 for record in records if record.result.success)
        return success_count / len(records)

    def get_average_execution_time(
        self, tool_name: Optional[str] = None
    ) -> float:
        """获取平均执行时间

        Args:
            tool_name: 工具名称，为None时计算所有工具的平均执行时间

        Returns:
            平均执行时间（秒）
        """
        records = self.get_all()

        if tool_name:
            records = [
                record for record in records if record.tool_name == tool_name
            ]

        if not records:
            return 0.0

        total_time = sum(record.execution_time for record in records)
        return total_time / len(records)

    def add_execution_record(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Any,
        execution_time: float = 0.0,
    ) -> bool:
        """添加执行记录

        Args:
            tool_name: 工具名称
            parameters: 执行参数
            result: 执行结果
            execution_time: 执行时间（秒）

        Returns:
            是否添加成功
        """
        record = ExecutionRecord(
            tool_name=tool_name,
            parameters=parameters,
            result=result,
            execution_time=execution_time,
        )
        return self.add(record)
