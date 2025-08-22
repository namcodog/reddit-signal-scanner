#!/usr/bin/env python3
"""
废弃文件归档脚本
遵循Linus原则：清理不是删除，是妥善保存

自动检测并归档标记为废弃的文件
"""

import os
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import json


class DeprecatedFileArchiver:
    """废弃文件归档器"""

    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path).resolve()
        self.archive_root = self.root_path / "archive"
        self.current_archive = self.archive_root / datetime.now().strftime("%Y-%m")

        # 创建归档目录结构
        self.deprecated_dir = self.current_archive / "deprecated"
        self.experiments_dir = self.current_archive / "experiments"

        self.archived_files = []
        self.scan_results = []

        # 废弃文件标记模式
        self.deprecation_patterns = [
            r"@deprecated",
            r"# DEPRECATED",
            r"// DEPRECATED",
            r"<!-- DEPRECATED",
            r"# TODO: 废弃",
            r"# FIXME: 废弃",
        ]

        # 实验性文件模式
        self.experimental_patterns = [
            r"_experiment",
            r"_prototype",
            r"_draft",
            r"_poc",
            r"_spike",
        ]

        # 需要跳过的目录
        self.skip_dirs = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "archive",
        }

    def setup_archive_structure(self) -> None:
        """创建归档目录结构"""
        self.deprecated_dir.mkdir(parents=True, exist_ok=True)
        self.experiments_dir.mkdir(parents=True, exist_ok=True)

        # 创建归档说明文件
        readme_path = self.current_archive / "README.md"
        if not readme_path.exists():
            readme_content = f"""# 归档文件说明

## 归档时间
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 目录结构
- `deprecated/` - 标记为废弃的代码文件
- `experiments/` - 实验性代码文件

## 归档原则
1. 文件在主项目中标记为废弃超过2周
2. 实验性文件不再活跃开发
3. 保留完整的文件历史和元数据

## 恢复方法
如需恢复文件，请从此目录复制到主项目中，并移除废弃标记。
"""
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(readme_content)

    def scan_deprecated_files(self) -> List[Tuple[Path, str]]:
        """扫描标记为废弃的文件"""
        deprecated_files = []

        for root, dirs, files in os.walk(self.root_path):
            # 过滤掉需要跳过的目录
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]

            for file in files:
                file_path = Path(root) / file

                # 只处理文本文件
                if self._is_text_file(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                            # 检查废弃标记
                            for pattern in self.deprecation_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    deprecated_files.append((file_path, pattern))
                                    break
                    except (UnicodeDecodeError, PermissionError):
                        # 跳过无法读取的文件
                        continue

        return deprecated_files

    def scan_experimental_files(self) -> List[Path]:
        """扫描实验性文件"""
        experimental_files = []

        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]

            for file in files:
                file_path = Path(root) / file

                # 检查文件名是否包含实验性标记
                for pattern in self.experimental_patterns:
                    if pattern in file.lower():
                        experimental_files.append(file_path)
                        break

        return experimental_files

    def _is_text_file(self, file_path: Path) -> bool:
        """判断是否为文本文件"""
        text_extensions = {
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".html",
            ".css",
            ".scss",
            ".md",
            ".txt",
            ".yml",
            ".yaml",
            ".json",
            ".xml",
            ".sql",
            ".sh",
            ".bash",
            ".zsh",
            ".fish",
            ".dockerfile",
            ".gitignore",
            ".env",
        }

        return file_path.suffix.lower() in text_extensions

    def archive_file(self, source_path: Path, target_dir: Path, reason: str) -> bool:
        """归档单个文件"""
        try:
            # 计算相对路径以保持目录结构
            relative_path = source_path.relative_to(self.root_path)
            target_path = target_dir / relative_path

            # 创建目标目录
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # 复制文件
            shutil.copy2(source_path, target_path)

            # 创建元数据文件
            meta_path = target_path.with_suffix(target_path.suffix + ".meta.json")
            metadata = {
                "original_path": str(relative_path),
                "archived_at": datetime.now().isoformat(),
                "reason": reason,
                "file_size": source_path.stat().st_size,
                "last_modified": datetime.fromtimestamp(
                    source_path.stat().st_mtime
                ).isoformat(),
            }

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            # 记录归档信息
            self.archived_files.append(
                {
                    "source": str(source_path),
                    "target": str(target_path),
                    "reason": reason,
                }
            )

            return True

        except Exception as e:
            print(f"❌ 归档文件失败: {source_path} -> {e}")
            return False

    def confirm_archive(self, files: List[Tuple[Path, str]], file_type: str) -> bool:
        """确认归档操作"""
        if not files:
            return False

        print(f"\n📦 发现 {len(files)} 个{file_type}文件:")
        for i, (file_path, reason) in enumerate(files[:10]):  # 只显示前10个
            relative_path = file_path.relative_to(self.root_path)
            print(f"  {i+1}. {relative_path} ({reason})")

        if len(files) > 10:
            print(f"  ... 还有 {len(files) - 10} 个文件")

        response = input(f"\n确认归档这些{file_type}文件？[y/N]: ").strip().lower()
        return response in ["y", "yes", "Y"]

    def run_archive(self) -> None:
        """运行归档过程"""
        print("📦 开始扫描废弃文件...")
        print(f"📁 项目路径: {self.root_path}")
        print(f"🗄️  归档路径: {self.current_archive}")
        print("-" * 60)

        # 创建归档结构
        self.setup_archive_structure()

        # 扫描废弃文件
        deprecated_files = self.scan_deprecated_files()
        experimental_files = [(f, "实验性文件") for f in self.scan_experimental_files()]

        total_archived = 0

        # 处理废弃文件
        if deprecated_files:
            if self.confirm_archive(deprecated_files, "废弃"):
                print("\n🗂️  归档废弃文件...")
                for file_path, pattern in deprecated_files:
                    if self.archive_file(
                        file_path, self.deprecated_dir, f"废弃标记: {pattern}"
                    ):
                        print(f"✅ 已归档: {file_path.relative_to(self.root_path)}")
                        total_archived += 1

        # 处理实验性文件
        if experimental_files:
            if self.confirm_archive(experimental_files, "实验性"):
                print("\n🧪 归档实验性文件...")
                for file_path, reason in experimental_files:
                    if self.archive_file(file_path, self.experiments_dir, reason):
                        print(f"✅ 已归档: {file_path.relative_to(self.root_path)}")
                        total_archived += 1

        # 生成归档报告
        self._generate_archive_report()

        print(f"\n🎉 归档完成！总计归档 {total_archived} 个文件")
        print(f"📋 归档位置: {self.current_archive}")

        if total_archived > 0:
            print("\n⚠️  注意：原始文件仍在项目中，如需删除请手动操作")
            print("💡 建议：确认归档无问题后，使用Git删除原文件")

    def _generate_archive_report(self) -> None:
        """生成归档报告"""
        if not self.archived_files:
            return

        report = {
            "archive_date": datetime.now().isoformat(),
            "total_files": len(self.archived_files),
            "files": self.archived_files,
        }

        report_path = self.current_archive / "archive_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"📊 归档报告已保存: {report_path}")


def main():
    """主函数"""
    print("🗄️  废弃文件归档工具")
    print("遵循Linus原则：清理不是删除，是妥善保存")
    print("=" * 50)

    archiver = DeprecatedFileArchiver()
    archiver.run_archive()


if __name__ == "__main__":
    main()
