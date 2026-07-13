"""
邮件发送模块
用于发送训练报告到用户邮箱
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class EmailSender:
    """邮件发送器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent / "config.json"
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """加载邮件配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载邮件配置失败: {e}")
        
        # 默认配置
        return {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'username': '',
            'password': '',
            'sender': '',
            'receivers': [],
            'subject': 'PL5 预测模型训练报告'
        }
    
    def send_email(self, report: Dict[str, Any], attachment_path: Optional[Path] = None) -> bool:
        """发送邮件
        
        Args:
            report: 训练报告
            attachment_path: 附件路径
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 检查配置
            if not self.config['username'] or not self.config['password']:
                logger.error("邮件配置不完整，无法发送邮件")
                return False
            
            if not self.config['receivers']:
                logger.error("没有配置收件人，无法发送邮件")
                return False
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.config['sender'] or self.config['username']
            msg['To'] = ', '.join(self.config['receivers'])
            msg['Subject'] = self.config['subject']
            
            # 构建邮件内容
            body = self._generate_email_body(report)
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            # 添加附件
            if attachment_path and attachment_path.exists():
                with open(attachment_path, 'rb') as f:
                    attachment = MIMEApplication(f.read())
                    attachment.add_header('Content-Disposition', 'attachment', filename=attachment_path.name)
                    msg.attach(attachment)
            
            # 发送邮件
            with smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port']) as server:
                server.starttls()
                server.login(self.config['username'], self.config['password'])
                server.send_message(msg)
            
            logger.info(f"邮件发送成功，收件人: {msg['To']}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
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
