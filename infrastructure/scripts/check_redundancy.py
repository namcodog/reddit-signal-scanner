#!/usr/bin/env python3
"""
冗余文件检查脚本
基于Linus的DRY原则：Don't Repeat Yourself

检测项目中的重复文件、相似文件和命名冗余
"""

import os
import hashlib
import difflib
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import json
from datetime import datetime


class RedundancyChecker:
    """冗余检查器"""

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
        self.skip_extensions = {".pyc", ".pyo", ".pyd", ".so", ".dylib", ".dll"}

        # 检查结果
        self.duplicate_files = defaultdict(list)  # 完全重复
        self.similar_files = []  # 高度相似
        self.redundant_names = []  # 命名冗余

        # 禁止的命名模式
        self.forbidden_names = {
            "utils.py",
            "helpers.py",
            "common.py",
            "misc.py",
            "test.py",
            "demo.py",
            "example.py",
            "sample.py",
            "temp.py",
            "temporary.py",
            "draft.py",
        }

        # 可疑的重复模式
        self.suspicious_patterns = [
            ("_backup", "_bak", "_old", "_orig"),
            ("copy", "copy_of", "duplicate"),
            ("new_", "old_", "temp_", "tmp_"),
            ("v1", "v2", "version1", "version2"),
        ]

    def calculate_file_hash(self, file_path: Path) -> str:
        """计算文件MD5哈希值"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (IOError, PermissionError):
            return None

    def is_text_file(self, file_path: Path) -> bool:
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
        }
        return file_path.suffix.lower() in text_extensions

    def check_duplicate_files(self) -> None:
        """检查完全重复的文件"""
        print("🔍 检查重复文件...")

        file_hashes = defaultdict(list)

        for root, dirs, files in os.walk(self.root_path):
            # 过滤掉要跳过的目录
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]

            for file in files:
                file_path = Path(root) / file

                # 跳过特定扩展名的文件
                if file_path.suffix.lower() in self.skip_extensions:
                    continue

                # 跳过空文件
                if file_path.stat().st_size == 0:
                    continue

                file_hash = self.calculate_file_hash(file_path)
                if file_hash:
                    file_hashes[file_hash].append(file_path)

        # 找出有多个文件的哈希值（重复文件）
        for file_hash, paths in file_hashes.items():
            if len(paths) > 1:
                self.duplicate_files[file_hash] = paths

    def check_similar_files(self) -> None:
        """检查高度相似的文本文件"""
        print("🔍 检查相似文件...")

        text_files = []

        # 收集所有文本文件
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]

            for file in files:
                file_path = Path(root) / file
                if self.is_text_file(file_path) and file_path.stat().st_size > 100:
                    text_files.append(file_path)

        # 比较文件内容相似度
        for i, file1 in enumerate(text_files):
            for file2 in text_files[i + 1 :]:
                if self._are_files_similar(file1, file2):
                    self.similar_files.append((file1, file2))

                    # 限制检查数量，避免过长时间
                    if len(self.similar_files) > 50:
                        print("⚠️  相似文件过多，停止深度检查")
                        return

    def _are_files_similar(
        self, file1: Path, file2: Path, threshold: float = 0.8
    ) -> bool:
        """检查两个文件是否相似"""
        try:
            with open(file1, "r", encoding="utf-8") as f1:
                content1 = f1.read()
            with open(file2, "r", encoding="utf-8") as f2:
                content2 = f2.read()

            # 使用difflib计算相似度
            similarity = difflib.SequenceMatcher(None, content1, content2).ratio()
            return similarity >= threshold

        except (UnicodeDecodeError, PermissionError, IOError):
            return False

    def check_redundant_naming(self) -> None:
        """检查命名冗余"""
        print("🔍 检查命名冗余...")

        all_files = []

        # 收集所有文件
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]

            for file in files:
                file_path = Path(root) / file
                all_files.append(file_path)

        # 检查禁止的文件名
        for file_path in all_files:
            if file_path.name.lower() in self.forbidden_names:
                self.redundant_names.append(
                    {
                        "type": "forbidden_name",
                        "file": file_path,
                        "reason": f"使用了禁止的通用文件名: {file_path.name}",
                    }
                )

        # 检查可疑的重复模式
        file_stems = defaultdict(list)
        for file_path in all_files:
            stem = file_path.stem.lower()
            file_stems[stem].append(file_path)

        for patterns in self.suspicious_patterns:
            for base_name in file_stems:
                matching_files = []
                for pattern in patterns:
                    for stem, files in file_stems.items():
                        if pattern in stem and base_name in stem:
                            matching_files.extend(files)

                if len(matching_files) > 1:
                    self.redundant_names.append(
                        {
                            "type": "suspicious_pattern",
                            "files": matching_files,
                            "reason": f"检测到可疑的重复命名模式: {patterns}",
                        }
                    )

    def generate_report(self) -> Dict:
        """生成检查报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "root_path": str(self.root_path),
            "summary": {
                "duplicate_groups": len(self.duplicate_files),
                "total_duplicates": sum(
                    len(files) for files in self.duplicate_files.values()
                ),
                "similar_pairs": len(self.similar_files),
                "redundant_names": len(self.redundant_names),
            },
            "details": {"duplicates": {}, "similar": [], "redundant_names": []},
        }

        # 转换重复文件为可序列化格式
        for hash_val, files in self.duplicate_files.items():
            report["details"]["duplicates"][hash_val] = [str(f) for f in files]

        # 转换相似文件
        for file1, file2 in self.similar_files:
            report["details"]["similar"].append(
                {
                    "file1": str(file1.relative_to(self.root_path)),
                    "file2": str(file2.relative_to(self.root_path)),
                }
            )

        # 转换冗余命名
        for item in self.redundant_names:
            if "files" in item:
                report["details"]["redundant_names"].append(
                    {
                        "type": item["type"],
                        "files": [
                            str(Path(f).relative_to(self.root_path))
                            for f in item["files"]
                        ],
                        "reason": item["reason"],
                    }
                )
            else:
                report["details"]["redundant_names"].append(
                    {
                        "type": item["type"],
                        "file": str(item["file"].relative_to(self.root_path)),
                        "reason": item["reason"],
                    }
                )

        return report

    def print_results(self) -> None:
        """打印检查结果"""
        print("\n" + "=" * 60)
        print("📊 冗余检查结果")
        print("=" * 60)

        # 重复文件
        if self.duplicate_files:
            print(f"\n❌ 发现 {len(self.duplicate_files)} 组重复文件:")
            for i, (hash_val, files) in enumerate(
                list(self.duplicate_files.items())[:5]
            ):
                print(f"\n  组 {i+1} (哈希: {hash_val[:8]}...):")
                for file_path in files:
                    rel_path = file_path.relative_to(self.root_path)
                    size = file_path.stat().st_size
                    print(f"    - {rel_path} ({size} bytes)")
        else:
            print("\n✅ 未发现重复文件")

        # 相似文件
        if self.similar_files:
            print(f"\n⚠️  发现 {len(self.similar_files)} 对相似文件:")
            for file1, file2 in self.similar_files[:5]:
                rel1 = file1.relative_to(self.root_path)
                rel2 = file2.relative_to(self.root_path)
                print(f"    - {rel1} ≈ {rel2}")
            if len(self.similar_files) > 5:
                print(f"    ... 还有 {len(self.similar_files) - 5} 对相似文件")
        else:
            print("\n✅ 未发现高度相似的文件")

        # 命名冗余
        if self.redundant_names:
            print(f"\n⚠️  发现 {len(self.redundant_names)} 个命名问题:")
            for item in self.redundant_names[:5]:
                print(f"    - {item['reason']}")
            if len(self.redundant_names) > 5:
                print(f"    ... 还有 {len(self.redundant_names) - 5} 个问题")
        else:
            print("\n✅ 未发现命名冗余问题")

        # 总结
        total_issues = (
            len(self.duplicate_files)
            + len(self.similar_files)
            + len(self.redundant_names)
        )
        if total_issues == 0:
            print("\n🎉 恭喜！项目没有发现明显的冗余问题")
        else:
            print(f"\n📋 总计发现 {total_issues} 个冗余问题需要关注")

    def run_check(self) -> bool:
        """运行完整的冗余检查"""
        print("🔍 开始冗余检查...")
        print(f"📁 检查路径: {self.root_path}")
        print("-" * 60)

        # 执行各项检查
        self.check_duplicate_files()
        self.check_similar_files()
        self.check_redundant_naming()

        # 显示结果
        self.print_results()

        # 保存报告
        report = self.generate_report()
        report_path = (
            self.root_path / "infrastructure" / "scripts" / "redundancy_report.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n📋 详细报告已保存: {report_path}")

        # 返回是否发现问题
        return (
            len(self.duplicate_files) == 0
            and len(self.similar_files) == 0
            and len(self.redundant_names) == 0
        )


def main():
    """主函数"""
    print("🔍 项目冗余检查工具")
    print("遵循Linus的DRY原则：Don't Repeat Yourself")
    print("=" * 50)

    checker = RedundancyChecker()
    is_clean = checker.run_check()

    if is_clean:
        print("\n✨ 项目代码库很干净！")
        exit(0)
    else:
        print("\n💡 建议清理发现的冗余问题以提高代码质量")
        exit(1)


if __name__ == "__main__":
    main()
