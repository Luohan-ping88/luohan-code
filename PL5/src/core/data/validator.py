"""
数据验证模块 V8.0
完整的数据质量检查、异常检测和修复机制
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import json
import hashlib
from dataclasses import dataclass
from enum import Enum

from .config import setup_logging

logger = setup_logging(__name__)


class ValidationLevel(Enum):
    """验证级别"""

    BASIC = "basic"  # 基本格式验证
    STANDARD = "standard"  # 标准验证（包括数据范围）
    STRICT = "strict"  # 严格验证（包括统计异常检测）
    COMPLETE = "complete"  # 完整验证（包括时序连续性）


class DataIssue(Enum):
    """数据问题类型"""

    MISSING_VALUES = "missing_values"
    INVALID_FORMAT = "invalid_format"
    OUT_OF_RANGE = "out_of_range"
    DUPLICATES = "duplicates"
    INCONSISTENT = "inconsistent"
    ANOMALY = "anomaly"
    SEQUENCE_BREAK = "sequence_break"
    TIMESTAMP_ISSUE = "timestamp_issue"


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    issues: List[Dict[str, Any]]
    summary: Dict[str, Any]
    data_hash: str
    validated_at: str


class AdvancedDataValidator:
    """高级数据验证器"""

    def __init__(
        self, validation_level: ValidationLevel = ValidationLevel.STANDARD
    ):
        self.validation_level = validation_level
        self.issues = []
        self.validation_stats = {}

        # 验证规则配置
        self.rules = {
            "period": {
                "required": True,
                "type": str,
                "pattern": r"^\d{5,7}$",  # 5-7位数字
                "min_value": 20000,
                "max_value": 29999,
            },
            "wan": {"required": True, "type": int, "min": 0, "max": 9},
            "qian": {"required": True, "type": int, "min": 0, "max": 9},
            "bai": {"required": True, "type": int, "min": 0, "max": 9},
            "shi": {"required": True, "type": int, "min": 0, "max": 9},
            "ge": {"required": True, "type": int, "min": 0, "max": 9},
        }

    def validate_dataset(self, data: pd.DataFrame) -> ValidationResult:
        """验证整个数据集"""
        self.issues = []
        self.validation_stats = {
            "total_records": len(data),
            "valid_records": 0,
            "invalid_records": 0,
            "issue_counts": {},
            "start_period": None,
            "end_period": None,
        }

        if data.empty:
            self._add_issue(
                DataIssue.MISSING_VALUES, "数据集为空", severity="critical"
            )
            return self._create_result(False, data)

        # 1. 检查数据结构
        self._validate_structure(data)

        # 2. 检查每行数据
        valid_indices = []
        for idx, row in data.iterrows():
            is_valid, row_issues = self._validate_record(row)
            if is_valid:
                valid_indices.append(idx)
                self.validation_stats["valid_records"] += 1
            else:
                self.validation_stats["invalid_records"] += 1
                for issue in row_issues:
                    self._add_issue(
                        issue["type"],
                        f"记录 {idx}: {issue['message']}",
                        record_index=idx,
                        severity=issue.get("severity", "warning"),
                    )

        # 3. 检查数据集级别的问题
        if self.validation_level in [
            ValidationLevel.STRICT,
            ValidationLevel.COMPLETE,
        ]:
            self._validate_dataset_level(data)

        # 4. 检查时序连续性
        if self.validation_level == ValidationLevel.COMPLETE:
            self._validate_temporal_continuity(data)

        # 5. 统计汇总
        self._update_validation_stats(data, valid_indices)

        # 计算数据哈希
        data_hash = self._calculate_data_hash(data)

        return self._create_result(len(self.issues) == 0, data, data_hash)

    def _validate_structure(self, data: pd.DataFrame):
        """验证数据结构"""
        # 检查必需列
        required_columns = list(self.rules.keys())
        missing_columns = [
            col for col in required_columns if col not in data.columns
        ]

        if missing_columns:
            self._add_issue(
                DataIssue.MISSING_VALUES,
                f"缺少必需列: {missing_columns}",
                severity="critical",
            )

        # 检查数据类型
        for col, rule in self.rules.items():
            if col in data.columns:
                expected_type = rule["type"]
                actual_type = data[col].dtype

                # 简单的类型检查
                if expected_type == int and not pd.api.types.is_integer_dtype(
                    actual_type
                ):
                    self._add_issue(
                        DataIssue.INVALID_FORMAT,
                        f"列 {col} 类型错误: 期望 {expected_type}, 实际 {actual_type}",
                    )

    def _validate_record(self, record: pd.Series) -> Tuple[bool, List[Dict]]:
        """验证单条记录"""
        issues = []
        is_valid = True

        for field, rule in self.rules.items():
            if field not in record:
                if rule["required"]:
                    issues.append(
                        {
                            "type": DataIssue.MISSING_VALUES,
                            "message": f"缺少字段: {field}",
                            "severity": "error",
                        }
                    )
                    is_valid = False
                continue

            value = record[field]

            # 检查类型
            if rule["type"] == int and not isinstance(
                value, (int, np.integer)
            ):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    issues.append(
                        {
                            "type": DataIssue.INVALID_FORMAT,
                            "message": f"字段 {field} 类型错误: {type(value).__name__}",
                            "severity": "error",
                        }
                    )
                    is_valid = False
                    continue

            # 检查范围
            if "min" in rule and value < rule["min"]:
                issues.append(
                    {
                        "type": DataIssue.OUT_OF_RANGE,
                        "message": f"字段 {field} 值 {value} 小于最小值 {rule['min']}",
                        "severity": "error",
                    }
                )
                is_valid = False

            if "max" in rule and value > rule["max"]:
                issues.append(
                    {
                        "type": DataIssue.OUT_OF_RANGE,
                        "message": f"字段 {field} 值 {value} 大于最大值 {rule['max']}",
                        "severity": "error",
                    }
                )
                is_valid = False

        return is_valid, issues

    def _validate_dataset_level(self, data: pd.DataFrame):
        """验证数据集级别的问题"""
        # 检查重复记录
        duplicates = data.duplicated(subset=["period"], keep=False)
        if duplicates.any():
            duplicate_periods = data[duplicates]["period"].unique()
            self._add_issue(
                DataIssue.DUPLICATES,
                f"发现重复期号: {duplicate_periods[:5]}",
                count=len(duplicate_periods),
            )

        # 检查数字分布（统计异常）
        self._validate_number_distribution(data)

        # 检查缺失期号
        if "period" in data.columns:
            self._validate_missing_periods(data)

    def _validate_number_distribution(self, data: pd.DataFrame):
        """验证数字分布"""
        positions = ["wan", "qian", "bai", "shi", "ge"]

        for pos in positions:
            if pos in data.columns:
                values = data[pos].values

                # 检查是否为0-9的数字
                invalid_values = values[(values < 0) | (values > 9)]
                if len(invalid_values) > 0:
                    self._add_issue(
                        DataIssue.OUT_OF_RANGE,
                        f"位置 {pos} 有无效值: {invalid_values[:5]}",
                        count=len(invalid_values),
                    )

                # 检查分布均匀性（可选）
                if len(values) > 100:
                    unique, counts = np.unique(values, return_counts=True)
                    expected_count = len(values) / 10
                    chi_square = np.sum(
                        (counts - expected_count) ** 2 / expected_count
                    )

                    if chi_square > 20:  # 卡方检验阈值
                        self._add_issue(
                            DataIssue.ANOMALY,
                            f"位置 {pos} 数字分布不均匀 (χ²={chi_square:.2f})",
                            severity="warning",
                        )

    def _validate_missing_periods(self, data: pd.DataFrame):
        """检查缺失的期号"""
        if "period" not in data.columns:
            return

        try:
            periods = pd.to_numeric(data["period"])
            periods_sorted = sorted(periods)

            if len(periods_sorted) < 2:
                return

            # 检查期号连续性
            expected_sequence = list(
                range(int(periods_sorted[0]), int(periods_sorted[-1]) + 1)
            )
            actual_sequence = [int(p) for p in periods_sorted]

            missing_periods = set(expected_sequence) - set(actual_sequence)
            if missing_periods:
                self._add_issue(
                    DataIssue.SEQUENCE_BREAK,
                    f"发现缺失期号: {sorted(missing_periods)[:10]}",
                    count=len(missing_periods),
                )

        except Exception as e:
            logger.warning(f"检查缺失期号失败: {e}")

    def _validate_temporal_continuity(self, data: pd.DataFrame):
        """验证时序连续性"""
        if "period" not in data.columns:
            return

        try:
            # 将期号转换为时间序列（假设每天一期）
            data_sorted = data.sort_values("period")
            periods = pd.to_numeric(data_sorted["period"])

            # 计算期号间隔
            diffs = np.diff(periods)
            irregular_intervals = diffs[diffs != 1]

            if len(irregular_intervals) > 0:
                self._add_issue(
                    DataIssue.SEQUENCE_BREAK,
                    f"期号间隔不规则: 发现 {len(irregular_intervals)} 处间隔不为1",
                    details={
                        "irregular_intervals": irregular_intervals.tolist()
                    },
                )

        except Exception as e:
            logger.warning(f"检查时序连续性失败: {e}")

    def _update_validation_stats(
        self, data: pd.DataFrame, valid_indices: List
    ):
        """更新验证统计信息"""
        # 统计各类问题数量
        issue_counts = {}
        for issue in self.issues:
            issue_type = (
                issue["type"].value
                if isinstance(issue["type"], DataIssue)
                else issue["type"]
            )
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        self.validation_stats["issue_counts"] = issue_counts

        # 获取期号范围
        if "period" in data.columns and len(valid_indices) > 0:
            valid_data = data.loc[valid_indices]
            periods = pd.to_numeric(valid_data["period"])
            if len(periods) > 0:
                self.validation_stats["start_period"] = int(periods.min())
                self.validation_stats["end_period"] = int(periods.max())

    def _calculate_data_hash(self, data: pd.DataFrame) -> str:
        """计算数据哈希值"""
        try:
            # 使用主要字段计算哈希
            hash_fields = ["period", "wan", "qian", "bai", "shi", "ge"]
            available_fields = [f for f in hash_fields if f in data.columns]

            if not available_fields:
                return "no_hash"

            # 对数据进行排序以确保哈希一致性
            sorted_data = data[available_fields].sort_values("period")
            data_str = sorted_data.to_string(index=False)

            return hashlib.md5(data_str.encode("utf-8")).hexdigest()[:16]
        except Exception as e:
            logger.warning(f"计算数据哈希失败: {e}")
            return "error"

    def _add_issue(self, issue_type: DataIssue, message: str, **kwargs):
        """添加问题记录"""
        issue = {
            "type": issue_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
        self.issues.append(issue)

        # 记录日志
        severity = kwargs.get("severity", "warning")
        if severity == "critical":
            logger.critical(f"数据验证问题: {message}")
        elif severity == "error":
            logger.error(f"数据验证问题: {message}")
        else:
            logger.warning(f"数据验证问题: {message}")

    def _create_result(
        self, is_valid: bool, data: pd.DataFrame, data_hash: str = None
    ) -> ValidationResult:
        """创建验证结果"""
        if data_hash is None:
            data_hash = self._calculate_data_hash(data)

        summary = {
            "validation_level": self.validation_level.value,
            "total_records": self.validation_stats.get("total_records", 0),
            "valid_records": self.validation_stats.get("valid_records", 0),
            "invalid_records": self.validation_stats.get("invalid_records", 0),
            "validity_rate": self.validation_stats.get("valid_records", 0)
            / max(self.validation_stats.get("total_records", 1), 1),
            "issue_summary": self.validation_stats.get("issue_counts", {}),
            "period_range": {
                "start": self.validation_stats.get("start_period"),
                "end": self.validation_stats.get("end_period"),
            },
        }

        return ValidationResult(
            is_valid=is_valid,
            issues=self.issues,
            summary=summary,
            data_hash=data_hash,
            validated_at=datetime.now().isoformat(),
        )

    def generate_validation_report(
        self, result: ValidationResult, output_path: Optional[Path] = None
    ) -> str:
        """生成验证报告"""
        report = {
            "validation_result": {
                "is_valid": result.is_valid,
                "validated_at": result.validated_at,
                "data_hash": result.data_hash,
            },
            "summary": result.summary,
            "issues": [
                {
                    "type": (
                        issue["type"].value
                        if isinstance(issue["type"], DataIssue)
                        else issue["type"]
                    ),
                    "message": issue["message"],
                    "severity": issue.get("severity", "warning"),
                    "timestamp": issue.get("timestamp"),
                }
                for issue in result.issues
            ],
            "recommendations": self._generate_recommendations(result),
        }

        report_json = json.dumps(
            report, indent=2, ensure_ascii=False, default=str
        )

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report_json)
            logger.info(f"验证报告已保存到: {output_path}")

        return report_json

    def _generate_recommendations(self, result: ValidationResult) -> List[str]:
        """生成修复建议"""
        recommendations = []
        summary = result.summary

        # 基于问题类型生成建议
        issue_counts = summary.get("issue_summary", {})

        if issue_counts.get("missing_values", 0) > 0:
            recommendations.append(
                "发现缺失值，建议进行数据填充或删除无效记录"
            )

        if issue_counts.get("invalid_format", 0) > 0:
            recommendations.append(
                "发现格式错误，建议检查数据源并修复格式问题"
            )

        if issue_counts.get("out_of_range", 0) > 0:
            recommendations.append("发现超出范围的值，建议验证数据采集过程")

        if issue_counts.get("duplicates", 0) > 0:
            recommendations.append("发现重复记录，建议删除重复数据")

        if issue_counts.get("sequence_break", 0) > 0:
            recommendations.append("发现期号序列中断，建议检查数据完整性")

        # 有效性率建议
        validity_rate = summary.get("validity_rate", 0)
        if validity_rate < 0.9:
            recommendations.append(
                f"数据有效性较低 ({validity_rate:.1%})，建议全面检查数据质量"
            )
        elif validity_rate < 0.99:
            recommendations.append(
                f"数据有效性良好 ({validity_rate:.1%})，但仍有改进空间"
            )

        return recommendations


class DataCleaner:
    """数据清洗器"""

    @staticmethod
    def clean_dataset(
        data: pd.DataFrame, validation_result: ValidationResult
    ) -> pd.DataFrame:
        """根据验证结果清洗数据"""
        if data.empty:
            return data

        cleaned_data = data.copy()
        issues_to_fix = []

        for issue in validation_result.issues:
            if issue.get("severity") in ["critical", "error"]:
                # 记录需要处理的问题
                issues_to_fix.append(issue)

        # 应用清洗规则
        cleaned_data = DataCleaner._remove_duplicates(cleaned_data)
        cleaned_data = DataCleaner._fix_invalid_values(cleaned_data)
        cleaned_data = DataCleaner._ensure_types(cleaned_data)

        # 排序数据
        if "period" in cleaned_data.columns:
            cleaned_data = cleaned_data.sort_values("period")

        return cleaned_data

    @staticmethod
    def _remove_duplicates(data: pd.DataFrame) -> pd.DataFrame:
        """移除重复记录"""
        if "period" in data.columns:
            # 保留每个期号的第一条记录
            return data.drop_duplicates(subset=["period"], keep="first")
        return data

    @staticmethod
    def _fix_invalid_values(data: pd.DataFrame) -> pd.DataFrame:
        """修复无效值"""
        positions = ["wan", "qian", "bai", "shi", "ge"]

        for pos in positions:
            if pos in data.columns:
                # 将非数字转换为NaN
                data[pos] = pd.to_numeric(data[pos], errors="coerce")
                # 将超出范围的值转换为NaN
                data[pos] = data[pos].where(
                    (data[pos] >= 0) & (data[pos] <= 9), np.nan
                )
                # 使用前向填充缺失值
                data[pos] = data[pos].ffill().bfill()
                # 确保为整数
                data[pos] = data[pos].astype(int)

        return data

    @staticmethod
    def _ensure_types(data: pd.DataFrame) -> pd.DataFrame:
        """确保数据类型正确"""
        type_mapping = {
            "period": str,
            "wan": int,
            "qian": int,
            "bai": int,
            "shi": int,
            "ge": int,
        }

        for col, dtype in type_mapping.items():
            if col in data.columns:
                try:
                    if dtype == str:
                        data[col] = data[col].astype(str)
                    elif dtype == int:
                        data[col] = (
                            pd.to_numeric(data[col], errors="coerce")
                            .fillna(0)
                            .astype(int)
                        )
                except Exception as e:
                    logger.warning(f"转换列 {col} 类型失败: {e}")

        return data


def validate_data_file(
    data_path: Path,
    validation_level: ValidationLevel = ValidationLevel.STANDARD,
) -> ValidationResult:
    """验证数据文件"""
    logger.info(f"开始验证数据文件: {data_path}")

    try:
        # 读取数据
        if data_path.suffix == ".csv":
            data = pd.read_csv(data_path, dtype=str)
        elif data_path.suffix == ".json":
            data = pd.read_json(data_path)
        else:
            raise ValueError(f"不支持的文件格式: {data_path.suffix}")

        # 执行验证
        validator = AdvancedDataValidator(validation_level)
        result = validator.validate_dataset(data)

        # 生成报告
        report_path = (
            data_path.parent / f"{data_path.stem}_validation_report.json"
        )
        validator.generate_validation_report(result, report_path)

        logger.info(
            f"数据验证完成: 有效性 {result.summary.get('validity_rate', 0):.1%}"
        )

        return result

    except Exception as e:
        logger.error(f"验证数据文件失败: {e}")
        raise


# 便捷函数
def quick_validate(data: pd.DataFrame) -> Tuple[bool, str]:
    """快速验证数据"""
    validator = AdvancedDataValidator(ValidationLevel.BASIC)
    result = validator.validate_dataset(data)

    if result.is_valid:
        return True, "数据验证通过"
    else:
        issues_summary = ", ".join(
            [
                f"{k}:{v}"
                for k, v in result.summary.get("issue_summary", {}).items()
            ]
        )
        return False, f"数据验证失败: {issues_summary}"


def clean_and_validate(
    data: pd.DataFrame,
) -> Tuple[pd.DataFrame, ValidationResult]:
    """清洗并验证数据"""
    # 首先验证
    validator = AdvancedDataValidator(ValidationLevel.STANDARD)
    validation_result = validator.validate_dataset(data)

    # 然后清洗
    if not validation_result.is_valid:
        logger.info("数据验证发现问题，开始清洗...")
        cleaned_data = DataCleaner.clean_dataset(data, validation_result)

        # 重新验证清洗后的数据
        validation_result = validator.validate_dataset(cleaned_data)
        return cleaned_data, validation_result

    return data, validation_result
