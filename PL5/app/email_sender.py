"""
邮件发送兼容模块
向后兼容旧的导入路径
"""

from src.core.email.sender import EmailSender

__all__ = ['EmailSender']
