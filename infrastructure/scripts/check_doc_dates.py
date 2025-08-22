#!/usr/bin/env python3
"""
文档日期检查脚本
基于Linus哲学：文档即代码，过期即错误

检查项目文档的更新日期，确保文档与代码同步
"""

import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import yaml


class DocumentDateChecker:
    """文档日期检查器"""

    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path).resolve()
        self.skip_dirs = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "archive",
        }

        # 文档文件扩展名
        self.doc_extensions = {".md", ".rst", ".txt", ".yml", ".yaml"}

        # 检查结果
        self.outdated_docs = []
        self.missing_dates = []
        self.valid_docs = []
        self.parsing_errors = []

        # 日期检查配置
        self.warning_days = 30  # 30天未更新显示警告
        self.critical_days = 90  # 90天未更新显示严重警告

        # 日期格式模式
        self.date_patterns = [
            # YAML Front Matter
            r'^updated:\s*["\']?(\d{4}-\d{2}-\d{2})["\']?',
            r'^last_updated:\s*["\']?(\d{4}-\d{2}-\d{2})["\']?',
            r'^date:\s*["\']?(\d{4}-\d{2}-\d{2})["\']?',
            # Markdown注释
            r"更新日期:\s*(\d{4}-\d{2}-\d{2})",
            r"最后更新:\s*(\d{4}-\d{2}-\d{2})",
            r"Last Updated:\s*(\d{4}-\d{2}-\d{2})",
            r"Updated:\s*(\d{4}-\d{2}-\d{2})",
            # 版本信息中的日期
            r"版本.*?(\d{4}-\d{2}-\d{2})",
            r"Version.*?(\d{4}-\d{2}-\d{2})",
            # 一般日期格式
            r"(\d{4}-\d{2}-\d{2})",
        ]

    def extract_document_date(self, file_path: Path) -> Optional[Tuple[datetime, str]]:
        """从文档中提取日期信息"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 尝试解析YAML Front Matter
            if content.startswith("---"):
                try:
                    yaml_end = content.find("---", 3)
                    if yaml_end != -1:
                        yaml_content = content[3:yaml_end]
                        yaml_data = yaml.safe_load(yaml_content)

                        if isinstance(yaml_data, dict):
                            # 检查常见的日期字段
                            for date_field in [
                                "updated",
                                "last_updated",
                                "date",
                                "modified",
                            ]:
                                if date_field in yaml_data:
                                    date_str = str(yaml_data[date_field])
                                    if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                                        date_obj = datetime.strptime(
                                            date_str[:10], "%Y-%m-%d"
                                        )
                                        return date_obj, f"YAML字段: {date_field}"
                except yaml.YAMLError:
                    pass

            # 使用正则表达式查找日期
            lines = content.split("\n")[:20]  # 只检查前20行
            for i, line in enumerate(lines):
                for pattern in self.date_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        date_str = match.group(1)
                        try:
                            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                            return date_obj, f"第{i+1}行: {line.strip()[:50]}..."
                        except ValueError:
                            continue

            return None

        except (UnicodeDecodeError, PermissionError, IOError) as e:
            self.parsing_errors.append((file_path, str(e)))
            return None

    def check_document_files(self) -> None:
        """检查所有文档文件"""
        print("📅 检查文档日期...")

        doc_files = []

        # 收集所有文档文件
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]

            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in self.doc_extensions:
                    doc_files.append(file_path)

        print(f"📄 发现 {len(doc_files)} 个文档文件")

        # 检查每个文档文件
        for file_path in doc_files:
            relative_path = file_path.relative_to(self.root_path)

            # 获取文件系统修改时间作为后备
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

            # 尝试从文档内容提取日期
            doc_date_info = self.extract_document_date(file_path)

            if doc_date_info:
                doc_date, source = doc_date_info
                days_old = (datetime.now() - doc_date).days

                status = {
                    "file": relative_path,
                    "doc_date": doc_date,
                    "source": source,
                    "file_mtime": file_mtime,
                    "days_old": days_old,
                }

                if days_old > self.critical_days:
                    status["level"] = "critical"
                    self.outdated_docs.append(status)
                elif days_old > self.warning_days:
                    status["level"] = "warning"
                    self.outdated_docs.append(status)
                else:
                    status["level"] = "good"
                    self.valid_docs.append(status)
            else:
                # 没有找到文档日期，使用文件修改时间
                days_old = (datetime.now() - file_mtime).days

                status = {
                    "file": relative_path,
                    "doc_date": None,
                    "source": "未找到",
                    "file_mtime": file_mtime,
                    "days_old": days_old,
                    "level": "missing",
                }

                self.missing_dates.append(status)

    def print_results(self) -> None:
        """打印检查结果"""
        print("\n" + "=" * 60)
        print("📅 文档日期检查结果")
        print("=" * 60)

        # 统计信息
        total_docs = (
            len(self.valid_docs) + len(self.outdated_docs) + len(self.missing_dates)
        )
        critical_count = len(
            [d for d in self.outdated_docs if d["level"] == "critical"]
        )
        warning_count = len([d for d in self.outdated_docs if d["level"] == "warning"])

        print(f"\n📊 统计信息:")
        print(f"  总文档数: {total_docs}")
        print(f"  ✅ 最新文档: {len(self.valid_docs)}")
        print(f"  ⚠️  需要更新: {warning_count}")
        print(f"  🚨 严重过期: {critical_count}")
        print(f"  ❓ 缺少日期: {len(self.missing_dates)}")

        # 严重过期文档
        if critical_count > 0:
            print(f"\n🚨 严重过期文档 (>{self.critical_days}天):")
            for doc in [d for d in self.outdated_docs if d["level"] == "critical"][:5]:
                print(f"    - {doc['file']} ({doc['days_old']}天前)")
                print(f"      更新信息: {doc['source']}")

        # 需要更新的文档
        if warning_count > 0:
            print(f"\n⚠️  需要更新的文档 (>{self.warning_days}天):")
            for doc in [d for d in self.outdated_docs if d["level"] == "warning"][:5]:
                print(f"    - {doc['file']} ({doc['days_old']}天前)")
                print(f"      更新信息: {doc['source']}")

        # 缺少日期的文档
        if self.missing_dates:
            print(f"\n❓ 缺少更新日期的文档:")
            for doc in self.missing_dates[:10]:
                print(
                    f"    - {doc['file']} (文件修改: {doc['file_mtime'].strftime('%Y-%m-%d')})"
                )

        # 解析错误
        if self.parsing_errors:
            print(f"\n❌ 解析错误:")
            for file_path, error in self.parsing_errors[:5]:
                rel_path = file_path.relative_to(self.root_path)
                print(f"    - {rel_path}: {error}")

    def generate_recommendations(self) -> List[str]:
        """生成改进建议"""
        recommendations = []

        if self.missing_dates:
            recommendations.append(
                "建议为所有文档添加更新日期标记，格式如：\n"
                "  Markdown: <!-- 更新日期: 2025-08-21 -->\n"
                "  YAML Front Matter: updated: 2025-08-21"
            )

        if any(d["level"] == "critical" for d in self.outdated_docs):
            recommendations.append(
                f"发现严重过期文档(>{self.critical_days}天)，建议立即审查和更新这些文档"
            )

        if any(d["level"] == "warning" for d in self.outdated_docs):
            recommendations.append(
                f"建议定期(每{self.warning_days}天)审查和更新项目文档"
            )

        recommendations.append(
            "建议建立文档维护流程：\n"
            "  1. 每次代码更新后检查相关文档\n"
            "  2. 使用CI/CD自动检查文档日期\n"
            "  3. 定期进行文档审查会议"
        )

        return recommendations

    def generate_report(self) -> Dict:
        """生成详细报告"""
        return {
            "timestamp": datetime.now().isoformat(),
            "root_path": str(self.root_path),
            "config": {
                "warning_days": self.warning_days,
                "critical_days": self.critical_days,
            },
            "summary": {
                "total_documents": len(self.valid_docs)
                + len(self.outdated_docs)
                + len(self.missing_dates),
                "valid_docs": len(self.valid_docs),
                "warning_docs": len(
                    [d for d in self.outdated_docs if d["level"] == "warning"]
                ),
                "critical_docs": len(
                    [d for d in self.outdated_docs if d["level"] == "critical"]
                ),
                "missing_dates": len(self.missing_dates),
                "parsing_errors": len(self.parsing_errors),
            },
            "details": {
                "valid": [self._serialize_doc_info(d) for d in self.valid_docs],
                "outdated": [self._serialize_doc_info(d) for d in self.outdated_docs],
                "missing_dates": [
                    self._serialize_doc_info(d) for d in self.missing_dates
                ],
                "parsing_errors": [
                    (str(p.relative_to(self.root_path)), e)
                    for p, e in self.parsing_errors
                ],
            },
            "recommendations": self.generate_recommendations(),
        }

    def _serialize_doc_info(self, doc_info: Dict) -> Dict:
        """序列化文档信息为JSON可保存格式"""
        result = doc_info.copy()
        result["file"] = str(result["file"])

        if result.get("doc_date"):
            result["doc_date"] = result["doc_date"].isoformat()

        if result.get("file_mtime"):
            result["file_mtime"] = result["file_mtime"].isoformat()

        return result

    def run_check(self) -> bool:
        """运行完整检查"""
        print("📅 开始文档日期检查...")
        print(f"📁 检查路径: {self.root_path}")
        print(f"⚠️  警告阈值: {self.warning_days} 天")
        print(f"🚨 严重阈值: {self.critical_days} 天")
        print("-" * 60)

        # 执行检查
        self.check_document_files()

        # 显示结果
        self.print_results()

        # 显示建议
        recommendations = self.generate_recommendations()
        if recommendations:
            print(f"\n💡 改进建议:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")

        # 保存报告
        report = self.generate_report()
        report_path = (
            self.root_path / "infrastructure" / "scripts" / "doc_dates_report.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n📋 详细报告已保存: {report_path}")

        # 返回检查结果（有严重问题则返回False）
        critical_issues = len(
            [d for d in self.outdated_docs if d["level"] == "critical"]
        )
        return critical_issues == 0


def main():
    """主函数"""
    print("📅 文档日期检查工具")
    print("基于Linus哲学：文档即代码，过期即错误")
    print("=" * 50)

    checker = DocumentDateChecker()
    no_critical_issues = checker.run_check()

    if no_critical_issues:
        print("\n✅ 文档状态良好！")
        exit(0)
    else:
        print("\n⚠️  发现严重过期的文档，请及时更新")
        exit(1)


if __name__ == "__main__":
    main()
