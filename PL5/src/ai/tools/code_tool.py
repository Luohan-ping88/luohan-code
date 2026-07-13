"""代码工具实现"""

from typing import Dict, Any, List
import subprocess
import tempfile
import os

from .base import BaseTool
from .registry import register_tool
from ..ai_types import ToolResult, ToolCategory


@register_tool
class CodeTool(BaseTool):
    """代码工具
    
    支持代码执行和代码生成。
    """
    name = "code"
    description = "执行代码或生成代码"
    category = ToolCategory.BUILTIN
    tags = ["code", "execution"]
    parameters = [
        {
            "name": "code",
            "type": "str",
            "description": "要执行或生成的代码",
            "required": True,
            "example": "print('Hello, World!')"
        },
        {
            "name": "language",
            "type": "str",
            "description": "代码语言",
            "required": False,
            "default": "python",
            "enum": ["python", "javascript", "bash"],
            "example": "python"
        },
        {
            "name": "action",
            "type": "str",
            "description": "操作类型 (execute 或 generate)",
            "required": True,
            "enum": ["execute", "generate"],
            "example": "execute"
        }
    ]
    
    def run(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行代码工具
        
        Args:
            parameters: 工具参数
            
        Returns:
            代码执行或生成结果
        """
        code = parameters.get("code")
        language = parameters.get("language", "python")
        action = parameters.get("action")
        
        try:
            if action == "execute":
                result = self._execute_code(code, language)
            else:
                result = self._generate_code(code, language)
            
            return ToolResult(
                success=True,
                data=result
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"代码工具执行失败: {str(e)}"
            )
    
    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行代码工具
        
        Args:
            parameters: 工具参数
            
        Returns:
            代码执行或生成结果
        """
        return super().execute(parameters)
    
    def _execute_code(self, code: str, language: str) -> Dict:
        """执行代码
        
        Args:
            code: 要执行的代码
            language: 代码语言
            
        Returns:
            执行结果
        """
        if language == "python":
            return self._execute_python(code)
        elif language == "javascript":
            return self._execute_javascript(code)
        elif language == "bash":
            return self._execute_bash(code)
        else:
            raise ValueError(f"不支持的语言: {language}")
    
    def _execute_python(self, code: str) -> Dict:
        """执行Python代码
        
        Args:
            code: Python代码
            
        Returns:
            执行结果
        """
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # 执行代码
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # 清理临时文件
            os.unlink(temp_file)
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "代码执行超时",
                "returncode": 1,
                "success": False
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": 1,
                "success": False
            }
    
    def _execute_javascript(self, code: str) -> Dict:
        """执行JavaScript代码
        
        Args:
            code: JavaScript代码
            
        Returns:
            执行结果
        """
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # 执行代码
            result = subprocess.run(
                ['node', temp_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # 清理临时文件
            os.unlink(temp_file)
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "代码执行超时",
                "returncode": 1,
                "success": False
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": 1,
                "success": False
            }
    
    def _execute_bash(self, code: str) -> Dict:
        """执行Bash代码
        
        Args:
            code: Bash代码
            
        Returns:
            执行结果
        """
        try:
            # 执行代码
            result = subprocess.run(
                ['bash', '-c', code],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "代码执行超时",
                "returncode": 1,
                "success": False
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": 1,
                "success": False
            }
    
    def _generate_code(self, prompt: str, language: str) -> Dict:
        """生成代码
        
        Args:
            prompt: 代码生成提示
            language: 代码语言
            
        Returns:
            生成的代码
        """
        # 模拟代码生成
        # 实际实现可以使用大模型生成代码
        generated_code = f"""# {language} code generated for: {prompt}

# Generated code here
print('Hello, Code Generation!')
"""
        
        return {
            "generated_code": generated_code,
            "language": language,
            "prompt": prompt
        }
