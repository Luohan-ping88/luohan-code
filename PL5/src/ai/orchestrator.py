"""工作流编排引擎

支持复杂任务的流程编排，包括线性、条件和并行工作流。
"""

import asyncio
import json
import os
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .ai_types import WorkflowStatus, WorkflowStep, ToolResult
from .registry import get_registry
from .performance import get_cache


@dataclass
class Workflow:
    """工作流定义"""
    name: str                  # 工作流名称
    description: str           # 工作流描述
    steps: List[WorkflowStep]  # 工作流步骤
    status: WorkflowStatus = WorkflowStatus.PENDING  # 工作流状态
    variables: Dict[str, Any] = field(default_factory=dict)  # 工作流变量
    created_at: datetime = field(default_factory=datetime.now)  # 创建时间
    started_at: Optional[datetime] = None  # 开始时间
    completed_at: Optional[datetime] = None  # 完成时间
    execution_id: str = field(default_factory=lambda: str(int(datetime.now().timestamp() * 1000)))  # 执行ID
    current_step: int = 0  # 当前执行的步骤索引
    step_results: Dict[str, Any] = field(default_factory=dict)  # 步骤执行结果
    
    def to_dict(self) -> Dict[str, Any]:
        """将工作流转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
            "status": self.status.value,
            "variables": self.variables,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_id": self.execution_id,
            "current_step": self.current_step,
            "step_results": self.step_results
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Workflow':
        """从字典创建工作流"""
        steps = [WorkflowStep.from_dict(step_data) for step_data in data.get("steps", [])]
        workflow = cls(
            name=data["name"],
            description=data.get("description", ""),
            steps=steps,
            status=WorkflowStatus(data.get("status", "pending")),
            variables=data.get("variables", {}),
            execution_id=data.get("execution_id", str(int(datetime.now().timestamp() * 1000)))
        )
        
        # 恢复时间戳
        if data.get("created_at"):
            workflow.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            workflow.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            workflow.completed_at = datetime.fromisoformat(data["completed_at"])
        
        # 恢复执行状态
        workflow.current_step = data.get("current_step", 0)
        workflow.step_results = data.get("step_results", {})
        
        return workflow
    
    def save(self, directory: str = "./workflows") -> None:
        """保存工作流到文件"""
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, f"{self.execution_id}.json")
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, execution_id: str, directory: str = "./workflows") -> Optional['Workflow']:
        """从文件加载工作流"""
        file_path = os.path.join(directory, f"{execution_id}.json")
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception:
            return None


class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self, persistence_dir: str = "./workflows", template_dir: str = "./workflow_templates"):
        """初始化工作流引擎"""
        self.registry = get_registry()
        self.running_workflows = {}
        self.persistence_dir = persistence_dir
        self.template_dir = template_dir
        self.workflow_history = {}
        self.templates = {}
        # 加载历史工作流
        self._load_workflow_history()
        # 加载工作流模板
        self._load_templates()
    
    def _load_workflow_history(self) -> None:
        """加载工作流历史"""
        os.makedirs(self.persistence_dir, exist_ok=True)
        for filename in os.listdir(self.persistence_dir):
            if filename.endswith(".json"):
                execution_id = filename[:-5]  # 移除 .json 后缀
                workflow = Workflow.load(execution_id, self.persistence_dir)
                if workflow:
                    self.workflow_history[execution_id] = workflow
    
    def _load_templates(self) -> None:
        """加载工作流模板"""
        os.makedirs(self.template_dir, exist_ok=True)
        for filename in os.listdir(self.template_dir):
            if filename.endswith(".json"):
                template_name = filename[:-5]  # 移除 .json 后缀
                template_path = os.path.join(self.template_dir, filename)
                try:
                    with open(template_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.templates[template_name] = data
                except Exception:
                    pass
    
    async def run_workflow(self, workflow: Workflow) -> Dict[str, Any]:
        """运行工作流
        
        Args:
            workflow: 工作流实例
            
        Returns:
            工作流执行结果
        """
        # 保存初始状态
        workflow.save(self.persistence_dir)
        
        # 发送开始更新
        try:
            from .api import send_workflow_update
            send_workflow_update(
                workflow.execution_id,
                "started",
                {"name": workflow.name, "steps": len(workflow.steps)}
            )
        except ImportError:
            pass
        
        # 记录开始时间
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now()
        self.running_workflows[workflow.execution_id] = workflow
        workflow.save(self.persistence_dir)
        
        try:
            # 执行工作流步骤
            results = await self._execute_steps(workflow)
            
            # 记录完成时间
            workflow.status = WorkflowStatus.SUCCESS
            workflow.completed_at = datetime.now()
            workflow.save(self.persistence_dir)
            
            # 发送完成更新
            try:
                from .api import send_workflow_update
                send_workflow_update(
                    workflow.execution_id,
                    "completed",
                    {"results": results, "variables": workflow.variables}
                )
            except ImportError:
                pass
            
            return {
                "execution_id": workflow.execution_id,
                "status": workflow.status.value,
                "results": results,
                "variables": workflow.variables
            }
            
        except Exception as e:
            # 记录错误
            workflow.status = WorkflowStatus.FAILED
            workflow.completed_at = datetime.now()
            workflow.save(self.persistence_dir)
            
            # 发送失败更新
            try:
                from .api import send_workflow_update
                send_workflow_update(
                    workflow.execution_id,
                    "failed",
                    {"error": str(e)}
                )
            except ImportError:
                pass
            
            return {
                "execution_id": workflow.execution_id,
                "status": workflow.status.value,
                "error": str(e)
            }
        finally:
            # 移除运行中的工作流
            if workflow.execution_id in self.running_workflows:
                del self.running_workflows[workflow.execution_id]
            # 更新工作流历史
            self.workflow_history[workflow.execution_id] = workflow
    
    async def _execute_steps(self, workflow: Workflow) -> Dict[str, Any]:
        """执行工作流步骤
        
        Args:
            workflow: 工作流实例
            
        Returns:
            执行结果
        """
        results = workflow.step_results.copy()
        
        # 按并行组分组
        parallel_groups = {}
        for step in workflow.steps:
            if step.parallel_group:
                if step.parallel_group not in parallel_groups:
                    parallel_groups[step.parallel_group] = []
                parallel_groups[step.parallel_group].append(step)
        
        # 执行步骤（从当前步骤开始）
        for i, step in enumerate(workflow.steps[workflow.current_step:]):
            # 检查是否是并行组的一部分
            if step.parallel_group:
                continue
            
            # 检查执行条件
            if step.condition and not step.condition(workflow.variables):
                results[step.name] = {"skipped": True}
                continue
            
            # 执行步骤
            result = await self._execute_step(step, workflow.variables)
            results[step.name] = result
            
            # 更新工作流状态
            workflow.current_step = workflow.current_step + i + 1
            workflow.step_results = results
            workflow.save(self.persistence_dir)
            
            # 更新工作流变量
            if result.get("success") and result.get("data"):
                workflow.variables[step.name] = result["data"]
        
        # 执行并行组
        for group_name, group_steps in parallel_groups.items():
            # 检查是否已经执行过
            if group_name in results:
                continue
            
            group_results = await self._execute_parallel_steps(group_steps, workflow.variables)
            results[group_name] = group_results
            
            # 更新工作流状态
            workflow.step_results = results
            workflow.save(self.persistence_dir)
            
            # 更新工作流变量
            for step_name, result in group_results.items():
                if result.get("success") and result.get("data"):
                    workflow.variables[step_name] = result["data"]
        
        return results
    
    async def _execute_step(self, step: WorkflowStep, variables: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个步骤
        
        Args:
            step: 工作流步骤
            variables: 工作流变量
            
        Returns:
            执行结果
        """
        # 解析参数中的变量
        resolved_params = self._resolve_variables(step.parameters, variables)
        
        # 执行工具
        for attempt in range(step.retry_count + 1):
            result = self.registry.execute_tool(step.tool_name, resolved_params)
            
            if result.success:
                return {
                    "success": True,
                    "data": result.data,
                    "error": None
                }
            
            if attempt < step.retry_count:
                await asyncio.sleep(step.retry_delay)
        
        return {
            "success": False,
            "data": None,
            "error": result.error
        }
    
    async def _execute_parallel_steps(self, steps: List[WorkflowStep], variables: Dict[str, Any]) -> Dict[str, Any]:
        """并行执行步骤
        
        Args:
            steps: 工作流步骤列表
            variables: 工作流变量
            
        Returns:
            执行结果
        """
        tasks = []
        step_names = []
        
        for step in steps:
            # 检查执行条件
            if step.condition and not step.condition(variables):
                continue
            
            step_names.append(step.name)
            tasks.append(self._execute_step(step, variables))
        
        # 并行执行
        results = await asyncio.gather(*tasks)
        
        # 整理结果
        return dict(zip(step_names, results))
    
    def _resolve_variables(self, parameters: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """解析参数中的变量
        
        Args:
            parameters: 原始参数
            variables: 工作流变量
            
        Returns:
            解析后的参数
        """
        resolved = {}
        
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("$"):
                # 变量引用，格式：$variable
                var_name = value[1:]
                resolved[key] = variables.get(var_name, value)
            elif isinstance(value, dict):
                # 递归解析
                resolved[key] = self._resolve_variables(value, variables)
            elif isinstance(value, list):
                # 递归解析列表
                resolved[key] = [
                    self._resolve_variables(item, variables) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                resolved[key] = value
        
        return resolved
    
    def get_workflow_status(self, execution_id: str) -> Optional[WorkflowStatus]:
        """获取工作流状态
        
        Args:
            execution_id: 执行ID
            
        Returns:
            工作流状态
        """
        workflow = self.running_workflows.get(execution_id)
        if workflow:
            return workflow.status
        return None
    
    def list_running_workflows(self) -> List[str]:
        """列出运行中的工作流
        
        Returns:
            执行ID列表
        """
        return list(self.running_workflows.keys())
    
    def list_workflows(self, status: Optional[WorkflowStatus] = None) -> List[str]:
        """列出工作流
        
        Args:
            status: 工作流状态，None表示所有状态
            
        Returns:
            执行ID列表
        """
        workflow_ids = []
        for execution_id, workflow in self.workflow_history.items():
            if status is None or workflow.status == status:
                workflow_ids.append(execution_id)
        return workflow_ids
    
    def get_workflow(self, execution_id: str) -> Optional[Workflow]:
        """获取工作流
        
        Args:
            execution_id: 执行ID
            
        Returns:
            工作流实例
        """
        # 先检查运行中的工作流
        if execution_id in self.running_workflows:
            return self.running_workflows[execution_id]
        # 再检查历史工作流
        return self.workflow_history.get(execution_id)
    
    async def resume_workflow(self, execution_id: str) -> Dict[str, Any]:
        """恢复工作流
        
        Args:
            execution_id: 执行ID
            
        Returns:
            工作流执行结果
        """
        # 加载工作流
        workflow = Workflow.load(execution_id, self.persistence_dir)
        if not workflow:
            raise ValueError(f"Workflow with execution_id {execution_id} not found")
        
        # 检查工作流状态
        if workflow.status in [WorkflowStatus.SUCCESS, WorkflowStatus.FAILED]:
            return {
                "execution_id": workflow.execution_id,
                "status": workflow.status.value,
                "error": "Workflow already completed"
            }
        
        # 恢复工作流执行
        return await self.run_workflow(workflow)
    
    def delete_workflow(self, execution_id: str) -> bool:
        """删除工作流
        
        Args:
            execution_id: 执行ID
            
        Returns:
            是否删除成功
        """
        # 从运行中的工作流中移除
        if execution_id in self.running_workflows:
            del self.running_workflows[execution_id]
        
        # 从历史中移除
        if execution_id in self.workflow_history:
            del self.workflow_history[execution_id]
        
        # 删除文件
        file_path = os.path.join(self.persistence_dir, f"{execution_id}.json")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except Exception:
                return False
        
        return False
    
    def save_template(self, template_name: str, workflow: Workflow) -> bool:
        """保存工作流模板
        
        Args:
            template_name: 模板名称
            workflow: 工作流实例
            
        Returns:
            是否保存成功
        """
        try:
            template_data = workflow.to_dict()
            # 移除运行时相关的字段
            template_data.pop("status", None)
            template_data.pop("created_at", None)
            template_data.pop("started_at", None)
            template_data.pop("completed_at", None)
            template_data.pop("execution_id", None)
            template_data.pop("current_step", None)
            template_data.pop("step_results", None)
            
            # 保存模板文件
            template_path = os.path.join(self.template_dir, f"{template_name}.json")
            with open(template_path, "w", encoding="utf-8") as f:
                json.dump(template_data, f, ensure_ascii=False, indent=2)
            
            # 更新内存中的模板
            self.templates[template_name] = template_data
            return True
        except Exception:
            return False
    
    def load_template(self, template_name: str) -> Optional[Workflow]:
        """从模板加载工作流
        
        Args:
            template_name: 模板名称
            
        Returns:
            工作流实例
        """
        # 从内存中获取模板
        template_data = self.templates.get(template_name)
        if not template_data:
            # 从文件加载模板
            template_path = os.path.join(self.template_dir, f"{template_name}.json")
            if not os.path.exists(template_path):
                return None
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    template_data = json.load(f)
            except Exception:
                return None
        
        # 创建工作流实例
        return Workflow.from_dict(template_data)
    
    def list_templates(self) -> List[str]:
        """列出所有工作流模板
        
        Returns:
            模板名称列表
        """
        return list(self.templates.keys())
    
    def delete_template(self, template_name: str) -> bool:
        """删除工作流模板
        
        Args:
            template_name: 模板名称
            
        Returns:
            是否删除成功
        """
        # 从内存中移除
        if template_name in self.templates:
            del self.templates[template_name]
        
        # 删除文件
        template_path = os.path.join(self.template_dir, f"{template_name}.json")
        if os.path.exists(template_path):
            try:
                os.remove(template_path)
                return True
            except Exception:
                return False
        
        return False


class BuiltInWorkflows:
    """内置工作流模板"""
    
    @staticmethod
    def data_analysis_workflow() -> Workflow:
        """数据分析工作流
        
        1. 读取数据
        2. 分析数据
        3. 生成报告
        """
        return Workflow(
            name="data_analysis",
            description="数据分析工作流",
            steps=[
                WorkflowStep(
                    name="read_data",
                    tool_name="file",
                    parameters={
                        "action": "read",
                        "path": "$data_file"
                    }
                ),
                WorkflowStep(
                    name="analyze_data",
                    tool_name="pl5_tool",
                    parameters={
                        "tool_name": "feature_engineer",
                        "parameters": {
                            "data": "$read_data"
                        }
                    }
                ),
                WorkflowStep(
                    name="generate_report",
                    tool_name="file",
                    parameters={
                        "action": "write",
                        "path": "$report_file",
                        "content": "$analyze_data"
                    }
                )
            ]
        )
    
    @staticmethod
    def prediction_workflow() -> Workflow:
        """预测工作流
        
        1. 加载模型
        2. 准备数据
        3. 执行预测
        4. 分析结果
        """
        return Workflow(
            name="prediction",
            description="预测工作流",
            steps=[
                WorkflowStep(
                    name="load_model",
                    tool_name="pl5_tool",
                    parameters={
                        "tool_name": "predictor",
                        "parameters": {
                            "model_id": "$model_id"
                        }
                    }
                ),
                WorkflowStep(
                    name="prepare_data",
                    tool_name="file",
                    parameters={
                        "action": "read",
                        "path": "$data_file"
                    }
                ),
                WorkflowStep(
                    name="predict",
                    tool_name="pl5_tool",
                    parameters={
                        "tool_name": "batch_predictor",
                        "parameters": {
                            "model": "$load_model",
                            "data": "$prepare_data"
                        }
                    }
                ),
                WorkflowStep(
                    name="analyze_results",
                    tool_name="pl5_tool",
                    parameters={
                        "tool_name": "model_analyzer",
                        "parameters": {
                            "predictions": "$predict"
                        }
                    }
                )
            ]
        )
    
    @staticmethod
    def research_workflow() -> Workflow:
        """研究工作流
        
        1. 搜索信息
        2. 分析信息
        3. 生成报告
        """
        return Workflow(
            name="research",
            description="研究工作流",
            steps=[
                WorkflowStep(
                    name="search_info",
                    tool_name="search",
                    parameters={
                        "query": "$query",
                        "max_results": 5
                    }
                ),
                WorkflowStep(
                    name="analyze_info",
                    tool_name="calculator",
                    parameters={
                        "expression": "$analysis_expression"
                    }
                ),
                WorkflowStep(
                    name="generate_report",
                    tool_name="file",
                    parameters={
                        "action": "write",
                        "path": "$report_file",
                        "content": "$search_info"
                    }
                )
            ]
        )
    
    @staticmethod
    def parallel_processing_workflow() -> Workflow:
        """并行处理工作流
        
        并行执行多个任务
        """
        return Workflow(
            name="parallel_processing",
            description="并行处理工作流",
            steps=[
                WorkflowStep(
                    name="task1",
                    tool_name="calculator",
                    parameters={"expression": "1 + 1"},
                    parallel_group="group1"
                ),
                WorkflowStep(
                    name="task2",
                    tool_name="calculator",
                    parameters={"expression": "2 + 2"},
                    parallel_group="group1"
                ),
                WorkflowStep(
                    name="task3",
                    tool_name="calculator",
                    parameters={"expression": "3 + 3"},
                    parallel_group="group1"
                ),
                WorkflowStep(
                    name="aggregate",
                    tool_name="calculator",
                    parameters={"expression": "$task1 + $task2 + $task3"}
                )
            ]
        )
