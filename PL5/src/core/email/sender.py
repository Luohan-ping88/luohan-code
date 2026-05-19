"""
邮件发送模块
用于发送训练报告到用户邮箱
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
import json
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class EmailSender:
    """邮件发送器 - 安全增强版"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent.parent.parent / "config" / "email_config.json"
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """加载邮件配置（优先使用环境变量）"""
        # 首先尝试从环境变量加载
        env_config = self._load_from_env()
        if env_config.get('username') and env_config.get('password'):
            logger.info("从环境变量加载邮件配置")
            return env_config
        
        # 然后尝试从配置文件加载
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                # 兼容不同的配置字段名
                return self._normalize_config(file_config)
            except Exception as e:
                logger.error(f"加载邮件配置文件失败: {e}")
        
        # 默认配置
        logger.warning("使用默认邮件配置，可能无法发送邮件")
        return {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'username': '',
            'password': '',
            'sender': '',
            'receivers': [],
            'subject': 'PL5 预测模型训练报告',
            'use_ssl': True
        }
    
    def _load_from_env(self) -> Dict[str, Any]:
        """从环境变量加载配置"""
        config = {}
        
        # 从环境变量读取
        if os.environ.get('SMTP_SERVER'):
            config['smtp_server'] = os.environ['SMTP_SERVER']
        
        if os.environ.get('SMTP_PORT'):
            try:
                config['smtp_port'] = int(os.environ['SMTP_PORT'])
            except ValueError:
                config['smtp_port'] = 587
        
        if os.environ.get('FROM_EMAIL'):
            config['username'] = os.environ['FROM_EMAIL']
            config['sender'] = os.environ['FROM_EMAIL']
        
        if os.environ.get('AUTH_CODE'):
            config['password'] = os.environ['AUTH_CODE']
        
        if os.environ.get('TO_EMAIL'):
            config['receivers'] = [email.strip() for email in os.environ['TO_EMAIL'].split(',')]
        
        return config
    
    def _normalize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """标准化配置字段名"""
        normalized = config.copy()
        
        # 字段名映射
        field_mapping = {
            'from_email': 'username',
            'auth_code': 'password',
            'to_email': 'receivers'
        }
        
        for old_field, new_field in field_mapping.items():
            if old_field in normalized and new_field not in normalized:
                value = normalized[old_field]
                if new_field == 'receivers' and isinstance(value, str):
                    normalized[new_field] = [value]
                else:
                    normalized[new_field] = value
        
        # 确保receivers是列表
        if 'receivers' in normalized and isinstance(normalized['receivers'], str):
            normalized['receivers'] = [normalized['receivers']]
        
        # 设置默认sender
        if 'sender' not in normalized and 'username' in normalized:
            normalized['sender'] = normalized['username']
        
        return normalized
    
    def send_email(self, report: Dict[str, Any], attachment_path: Optional[Path] = None) -> bool:
        """发送邮件 - 安全增强版
        
        Args:
            report: 训练报告
            attachment_path: 附件路径
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 检查配置
            if not self.config.get('username') or not self.config.get('password'):
                logger.error("邮件配置不完整：缺少用户名或密码，无法发送邮件")
                return False
            
            if not self.config.get('receivers'):
                logger.error("没有配置收件人，无法发送邮件")
                return False
            
            # 验证关键配置
            smtp_server = self.config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = self.config.get('smtp_port', 587)
            
            if not smtp_server or not isinstance(smtp_port, int):
                logger.error("SMTP服务器配置无效")
                return False
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.config.get('sender', self.config.get('username', ''))
            msg['To'] = ', '.join(self.config['receivers'])
            msg['Subject'] = self.config.get('subject', 'PL5 预测模型训练报告')
            
            # 构建邮件内容
            body = self._generate_email_body(report)
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            # 安全地添加附件
            if attachment_path and attachment_path.exists():
                try:
                    # 验证文件类型和大小
                    file_size = attachment_path.stat().st_size
                    if file_size > 10 * 1024 * 1024:  # 限制10MB
                        logger.warning(f"附件过大 ({file_size / 1024 / 1024:.1f}MB)，跳过添加")
                    else:
                        with open(attachment_path, 'rb') as f:
                            attachment = MIMEApplication(f.read())
                            safe_filename = attachment_path.name.replace('..', '_').replace('/', '_').replace('\\', '_')
                            attachment.add_header('Content-Disposition', 'attachment', filename=safe_filename)
                            msg.attach(attachment)
                except Exception as e:
                    logger.warning(f"添加附件失败（继续发送邮件）: {e}")
            
            # 发送邮件 - 根据端口选择安全连接方式
            use_ssl = self.config.get('use_ssl', smtp_port == 465)
            
            if use_ssl:
                # 使用SMTP_SSL（端口465）
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                    server.login(self.config['username'], self.config['password'])
                    server.send_message(msg)
            else:
                # 使用STARTTLS（端口587）
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls(context=ssl.create_default_context())
                    server.login(self.config['username'], self.config['password'])
                    server.send_message(msg)
            
            # 日志中避免记录完整邮箱
            safe_receivers = [email.split('@')[0] + '@***' for email in self.config['receivers']]
            logger.info(f"邮件发送成功，收件人: {', '.join(safe_receivers)}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error("邮件发送失败：SMTP身份验证错误，请检查用户名和密码")
            return False
        except smtplib.SMTPConnectError:
            logger.error(f"邮件发送失败：无法连接到SMTP服务器 {smtp_server}:{smtp_port}")
            return False
        except Exception as e:
            logger.error(f"邮件发送失败: {type(e).__name__}: {e}")
            return False
    
    def _generate_email_body(self, report: Dict[str, Any]) -> str:
        """生成邮件正文
        
        Args:
            report: 训练报告
            
        Returns:
            str: 邮件正文（HTML格式）
        """
        # 提取报告信息
        timestamp = report.get('timestamp', '')
        data_processing = report.get('data_processing', {})
        feature_engineering = report.get('feature_engineering', {})
        model_evaluation = report.get('model_evaluation', {})
        analysis = report.get('analysis', {})
        predictions = report.get('predictions', {})
        
        # 构建HTML内容
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>PL5 预测模型训练报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                h1 {{ color: #333; }}
                h2 {{ color: #555; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .section {{ margin-bottom: 20px; }}
                .success {{ color: green; }}
                .warning {{ color: orange; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>PL5 预测模型训练报告</h1>
            <p>生成时间: {timestamp}</p>
            
            <div class="section">
                <h2>1. 数据处理</h2>
                <table>
                    <tr>
                        <th>项目</th>
                        <th>值</th>
                    </tr>
                    <tr>
                        <td>记录数</td>
                        <td>{data_processing.get('record_count', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td>最新期号</td>
                        <td>{data_processing.get('latest_period', 'N/A')}</td>
                    </tr>
                </table>
            </div>
            
            <div class="section">
                <h2>2. 特征工程</h2>
                <table>
                    <tr>
                        <th>项目</th>
                        <th>值</th>
                    </tr>
                    <tr>
                        <td>特征数</td>
                        <td>{feature_engineering.get('feature_count', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td>特征选择方法</td>
                        <td>{analysis.get('feature_analysis', {}).get('feature_selection_method', 'N/A')}</td>
                    </tr>
                </table>
            </div>
            
            <div class="section">
                <h2>3. 模型评估</h2>
                <table>
                    <tr>
                        <th>项目</th>
                        <th>值</th>
                    </tr>
                    <tr>
                        <td>总体准确率</td>
                        <td>{model_evaluation.get('evaluation', {}).get('overall_accuracy', 'N/A'):.4f}</td>
                    </tr>
                    <tr>
                        <td>总预测数</td>
                        <td>{model_evaluation.get('evaluation', {}).get('total_predictions', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td>正确预测数</td>
                        <td>{model_evaluation.get('evaluation', {}).get('correct_predictions', 'N/A')}</td>
                    </tr>
                </table>
            </div>
            
            <div class="section">
                <h2>4. 预测结果</h2>
                <p>下期期号: {predictions.get('next_period', 'N/A')}</p>
                
                <h3>每个位置预测号码 (Top 8)</h3>
                <table>
                    <tr>
                        <th>位置</th>
                        <th>预测号码</th>
                    </tr>
                    {self._generate_predictions_table(predictions.get('top_8', {}))}
                </table>
                
                <h3>每个位置预测号码 (Top 5)</h3>
                <table>
                    <tr>
                        <th>位置</th>
                        <th>预测号码</th>
                    </tr>
                    {self._generate_predictions_table(predictions.get('top_5', {}))}
                </table>
                
                <h3>每个位置预测号码 (Top 3)</h3>
                <table>
                    <tr>
                        <th>位置</th>
                        <th>预测号码</th>
                    </tr>
                    {self._generate_predictions_table(predictions.get('top_3', {}))}
                </table>
            </div>
            
            <div class="section">
                <h2>5. 系统信息</h2>
                <p>此邮件由 PL5 预测系统自动生成，请勿直接回复。</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _generate_predictions_table(self, predictions: Dict[str, Dict[str, Any]]) -> str:
        """生成预测结果表格
        
        Args:
            predictions: 预测结果
            
        Returns:
            str: HTML表格
        """
        rows = []
        positions = ['wan', 'qian', 'bai', 'shi', 'ge']
        pos_names = {'wan': '万位', 'qian': '千位', 'bai': '百位', 'shi': '十位', 'ge': '个位'}
        
        for pos in positions:
            if pos in predictions:
                top_k = predictions[pos].get('top_k', [])
                top_k_str = ', '.join(map(str, top_k))
                rows.append(f"<tr><td>{pos_names.get(pos, pos)}</td><td>{top_k_str}</td></tr>")
        
        return '\n'.join(rows)
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """更新邮件配置
        
        Args:
            config: 新的配置
        """
        self.config.update(config)
        
        # 保存配置
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info("邮件配置已更新")
        except Exception as e:
            logger.error(f"保存邮件配置失败: {e}")
