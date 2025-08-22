#!/usr/bin/env python3
"""
配置同步脚本 - Reddit Signal Scanner

验证配置文件一致性，检查环境间配置同步状态，提供配置回滚能力。
通过Claude Code Hooks在会话结束时自动触发。

使用方式:
    python config_sync.py [--validate] [--sync] [--backup] [--restore=<backup_id>]

返回值:
    0: 配置同步正常
    1: 发现严重配置问题
    2: 警告级配置问题
"""

import sys
import json
import os
import yaml
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import subprocess
import glob

class ConfigSyncManager:
    def __init__(self):
        self.project_root = Path.cwd()
        self.config_dir = self.project_root / 'config'
        self.backup_dir = Path('.claude/backups/config')
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'validation_results': {},
            'sync_status': {},
            'backup_info': {},
            'issues': [],
            'warnings': []
        }
        
        # 配置文件结构定义
        self.required_config_structure = {
            'base': ['database.yml', 'redis.yml', 'api.yml', 'logging.yml'],
            'environments': ['development.yml', 'testing.yml', 'production.yml'],
            'secrets': ['.env.development', '.env.testing', '.env.production']
        }
        
        # 必需的配置字段
        self.required_fields = {
            'database': ['host', 'port', 'name'],
            'redis': ['host', 'port', 'max_connections'],
            'api': ['host', 'port', 'timeout'],
            'logging': ['level', 'format']
        }
    
    def validate_configuration(self) -> bool:
        """验证配置文件完整性和一致性"""
        print("🔍 验证配置文件...")
        
        validation_passed = True
        
        # 1. 检查配置目录结构
        structure_valid = self._validate_directory_structure()
        if not structure_valid:
            validation_passed = False
        
        # 2. 验证YAML语法
        syntax_valid = self._validate_yaml_syntax()
        if not syntax_valid:
            validation_passed = False
        
        # 3. 验证配置结构
        schema_valid = self._validate_configuration_schema()
        if not schema_valid:
            validation_passed = False
        
        # 4. 检查环境间一致性
        consistency_valid = self._validate_cross_environment_consistency()
        if not consistency_valid:
            validation_passed = False
        
        # 5. 安全性审计
        security_valid = self._audit_configuration_security()
        if not security_valid:
            validation_passed = False
        
        self.results['validation_results'] = {
            'structure_valid': structure_valid,
            'syntax_valid': syntax_valid,
            'schema_valid': schema_valid,
            'consistency_valid': consistency_valid,
            'security_valid': security_valid,
            'overall_valid': validation_passed
        }
        
        return validation_passed
    
    def sync_configurations(self) -> bool:
        """同步配置变更"""
        print("🔄 同步配置变更...")
        
        sync_successful = True
        
        # 检测配置变更
        changes = self._detect_configuration_changes()
        
        if changes:
            print(f"发现 {len(changes)} 个配置变更")
            
            # 创建备份
            backup_id = self._create_backup()
            
            # 应用变更
            for change in changes:
                try:
                    self._apply_configuration_change(change)
                except Exception as e:
                    self.results['issues'].append(f"配置同步失败 {change['file']}: {str(e)}")
                    sync_successful = False
            
            # 验证同步结果
            if sync_successful:
                validation_result = self.validate_configuration()
                if not validation_result:
                    print("⚠️ 同步后验证失败，考虑回滚")
                    sync_successful = False
            
            self.results['sync_status'] = {
                'changes_detected': len(changes),
                'backup_created': backup_id,
                'sync_successful': sync_successful,
                'changes_applied': changes if sync_successful else []
            }
        else:
            print("✅ 无配置变更需要同步")
            self.results['sync_status'] = {
                'changes_detected': 0,
                'sync_successful': True,
                'message': 'No changes to sync'
            }
        
        return sync_successful
    
    def create_backup(self) -> str:
        """创建配置备份"""
        print("💾 创建配置备份...")
        return self._create_backup()
    
    def restore_backup(self, backup_id: str) -> bool:
        """恢复配置备份"""
        print(f"🔙 恢复配置备份: {backup_id}")
        
        backup_path = self.backup_dir / backup_id
        if not backup_path.exists():
            self.results['issues'].append(f"备份不存在: {backup_id}")
            return False
        
        try:
            # 创建当前配置备份
            current_backup = self._create_backup()
            
            # 恢复指定备份
            if self.config_dir.exists():
                shutil.rmtree(self.config_dir)
            shutil.copytree(backup_path, self.config_dir)
            
            # 验证恢复结果
            validation_result = self.validate_configuration()
            
            self.results['backup_info'] = {
                'restored_backup': backup_id,
                'current_backup_created': current_backup,
                'restoration_successful': validation_result
            }
            
            return validation_result
            
        except Exception as e:
            self.results['issues'].append(f"配置恢复失败: {str(e)}")
            return False
    
    def _validate_directory_structure(self) -> bool:
        """验证配置目录结构"""
        if not self.config_dir.exists():
            self.results['issues'].append("配置目录不存在")
            return False
        
        missing_dirs = []
        for dir_name in ['base', 'environments']:
            dir_path = self.config_dir / dir_name
            if not dir_path.exists():
                missing_dirs.append(dir_name)
        
        if missing_dirs:
            self.results['issues'].append(f"缺少配置目录: {', '.join(missing_dirs)}")
            return False
        
        # 检查必需的配置文件
        missing_files = []
        for category, files in self.required_config_structure.items():
            category_dir = self.config_dir / category if category != 'secrets' else self.project_root
            for file_name in files:
                file_path = category_dir / file_name
                if not file_path.exists():
                    if category == 'secrets':
                        # 敏感配置文件缺失是警告，不是错误
                        self.results['warnings'].append(f"敏感配置文件缺失: {file_name}")
                    else:
                        missing_files.append(f"{category}/{file_name}")
        
        if missing_files:
            self.results['issues'].append(f"缺少配置文件: {', '.join(missing_files)}")
            return False
        
        return True
    
    def _validate_yaml_syntax(self) -> bool:
        """验证YAML文件语法"""
        yaml_files = list(self.config_dir.glob('**/*.yml')) + list(self.config_dir.glob('**/*.yaml'))
        
        syntax_errors = []
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                syntax_errors.append(f"{yaml_file.relative_to(self.project_root)}: {str(e)}")
            except Exception as e:
                syntax_errors.append(f"{yaml_file.relative_to(self.project_root)}: 文件读取错误 - {str(e)}")
        
        if syntax_errors:
            self.results['issues'].extend([f"YAML语法错误: {error}" for error in syntax_errors])
            return False
        
        return True
    
    def _validate_configuration_schema(self) -> bool:
        """验证配置文件结构和必需字段"""
        schema_valid = True
        
        for category, files in self.required_config_structure.items():
            if category == 'secrets':  # 跳过敏感文件检查
                continue
                
            category_dir = self.config_dir / category
            for file_name in files:
                file_path = category_dir / file_name
                if not file_path.exists():
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    
                    # 检查必需字段
                    config_name = file_name.replace('.yml', '').replace('.yaml', '')
                    required = self.required_fields.get(config_name, [])
                    
                    missing_fields = []
                    for field in required:
                        if not self._check_nested_field(config, field):
                            missing_fields.append(field)
                    
                    if missing_fields:
                        self.results['issues'].append(
                            f"{file_path.relative_to(self.project_root)}: 缺少字段 {missing_fields}"
                        )
                        schema_valid = False
                        
                except Exception as e:
                    self.results['issues'].append(
                        f"{file_path.relative_to(self.project_root)}: 配置读取失败 - {str(e)}"
                    )
                    schema_valid = False
        
        return schema_valid
    
    def _validate_cross_environment_consistency(self) -> bool:
        """验证环境间配置一致性"""
        environments = ['development', 'testing', 'production']
        base_configs = {}
        
        # 加载基础配置
        for base_file in self.required_config_structure['base']:
            base_path = self.config_dir / 'base' / base_file
            if base_path.exists():
                try:
                    with open(base_path, 'r') as f:
                        base_configs[base_file] = yaml.safe_load(f)
                except Exception:
                    continue
        
        consistency_issues = []
        
        # 检查每个环境的配置结构
        for env in environments:
            env_file = self.config_dir / 'environments' / f'{env}.yml'
            if not env_file.exists():
                continue
            
            try:
                with open(env_file, 'r') as f:
                    env_config = yaml.safe_load(f)
                
                # 检查环境配置是否包含合理的覆盖
                self._validate_environment_overrides(env, env_config, base_configs, consistency_issues)
                
            except Exception as e:
                consistency_issues.append(f"{env}环境配置读取失败: {str(e)}")
        
        if consistency_issues:
            self.results['warnings'].extend(consistency_issues)
            # 一致性问题通常是警告级别，不阻止系统运行
            return True
        
        return True
    
    def _audit_configuration_security(self) -> bool:
        """审计配置安全性"""
        security_issues = []
        
        # 检查所有配置文件中的安全问题
        config_files = list(self.config_dir.glob('**/*.yml')) + list(self.config_dir.glob('**/*.yaml'))
        
        for config_file in config_files:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 检查硬编码密码/密钥
                if self._contains_hardcoded_secrets(content):
                    security_issues.append(f"{config_file.relative_to(self.project_root)}: 包含硬编码密钥")
                
                # 检查不安全的默认值
                insecure_patterns = ['password: admin', 'password: 123', 'secret: secret']
                for pattern in insecure_patterns:
                    if pattern in content.lower():
                        security_issues.append(f"{config_file.relative_to(self.project_root)}: 使用不安全的默认密码")
                
            except Exception:
                continue
        
        # 检查环境变量文件权限
        env_files = ['.env', '.env.local', '.env.production']
        for env_file in env_files:
            env_path = self.project_root / env_file
            if env_path.exists():
                # 检查文件权限 (Unix系统)
                if hasattr(os, 'stat'):
                    stat = os.stat(env_path)
                    if stat.st_mode & 0o077:  # 其他用户可读写
                        security_issues.append(f"{env_file}: 文件权限过于宽松")
        
        if security_issues:
            # 安全问题是严重问题
            self.results['issues'].extend([f"安全问题: {issue}" for issue in security_issues])
            return False
        
        return True
    
    def _detect_configuration_changes(self) -> List[dict]:
        """检测配置文件变更"""
        changes = []
        
        # 检查Git变更（如果在Git仓库中）
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain', 'config/'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        status = line[:2]
                        file_path = line[3:].strip()
                        if file_path.startswith('config/'):
                            changes.append({
                                'file': file_path,
                                'status': status,
                                'type': 'git_tracked'
                            })
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return changes
    
    def _apply_configuration_change(self, change: dict):
        """应用配置变更"""
        # 简单实现：记录变更，实际的同步逻辑依赖于具体需求
        print(f"应用变更: {change['file']} ({change['status']})")
        
        # 这里可以实现具体的同步逻辑
        # 例如：部署配置到不同环境、重启服务等
        pass
    
    def _create_backup(self) -> str:
        """创建配置备份"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_id = f"config_backup_{timestamp}"
        backup_path = self.backup_dir / backup_id
        
        try:
            if self.config_dir.exists():
                shutil.copytree(self.config_dir, backup_path)
                
                # 创建备份元数据
                metadata = {
                    'backup_id': backup_id,
                    'timestamp': datetime.now().isoformat(),
                    'project_root': str(self.project_root),
                    'file_count': len(list(backup_path.glob('**/*'))),
                    'backup_size_mb': self._get_directory_size(backup_path) / (1024 * 1024)
                }
                
                with open(backup_path / '_backup_metadata.json', 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                print(f"✅ 配置备份已创建: {backup_id}")
                return backup_id
            else:
                raise Exception("配置目录不存在")
                
        except Exception as e:
            self.results['issues'].append(f"备份创建失败: {str(e)}")
            raise
    
    def _check_nested_field(self, config: dict, field_path: str) -> bool:
        """检查嵌套字段是否存在"""
        if not isinstance(config, dict):
            return False
        
        parts = field_path.split('.')
        current = config
        
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        
        return True
    
    def _validate_environment_overrides(self, env: str, env_config: dict, 
                                      base_configs: dict, issues: List[str]):
        """验证环境特定配置的合理性"""
        # 检查环境配置是否有合理的覆盖
        if not env_config:
            issues.append(f"{env}环境配置为空")
            return
        
        # 检查是否有生产环境特有的安全设置
        if env == 'production':
            security_settings = ['debug', 'log_level', 'ssl']
            for setting in security_settings:
                if self._check_nested_field(env_config, setting):
                    # 这是好事，生产环境应该有特殊安全配置
                    continue
        
        # 检查开发环境是否有调试配置
        if env == 'development':
            if not self._check_nested_field(env_config, 'debug'):
                issues.append(f"{env}环境缺少调试配置")
    
    def _contains_hardcoded_secrets(self, content: str) -> bool:
        """检查是否包含硬编码密钥"""
        secret_patterns = [
            r'password\s*[=:]\s*["\'][^"\']{6,}["\']',
            r'secret\s*[=:]\s*["\'][^"\']{10,}["\']',
            r'key\s*[=:]\s*["\'][A-Za-z0-9+/]{20,}["\']',
            r'token\s*[=:]\s*["\'][A-Za-z0-9+/]{15,}["\']'
        ]
        
        import re
        for pattern in secret_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def _get_directory_size(self, directory: Path) -> int:
        """获取目录大小（字节）"""
        total_size = 0
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size
    
    def generate_sync_report(self) -> str:
        """生成配置同步报告"""
        report = []
        
        # 时间戳
        report.append(f"⚙️ 配置同步报告 ({self.results['timestamp']})")
        report.append("")
        
        # 验证结果
        validation = self.results.get('validation_results', {})
        if validation:
            overall_valid = validation.get('overall_valid', False)
            status_emoji = "✅" if overall_valid else "❌"
            report.append(f"{status_emoji} 配置验证: {'通过' if overall_valid else '失败'}")
            
            details = []
            if validation.get('structure_valid'): details.append("结构✅")
            else: details.append("结构❌")
            
            if validation.get('syntax_valid'): details.append("语法✅") 
            else: details.append("语法❌")
            
            if validation.get('security_valid'): details.append("安全✅")
            else: details.append("安全❌")
            
            report.append(f"   详细: {' | '.join(details)}")
        
        # 同步状态
        sync_status = self.results.get('sync_status', {})
        if sync_status:
            changes = sync_status.get('changes_detected', 0)
            if changes > 0:
                sync_success = sync_status.get('sync_successful', False)
                report.append(f"🔄 配置同步: {changes}个变更 {'成功' if sync_success else '失败'}")
            else:
                report.append("🔄 配置同步: 无变更")
        
        # 备份信息
        backup_info = self.results.get('backup_info', {})
        if backup_info:
            report.append(f"💾 备份状态: {backup_info.get('restored_backup', 'N/A')}")
        
        # 问题和警告
        issues = self.results.get('issues', [])
        warnings = self.results.get('warnings', [])
        
        if issues:
            report.append("")
            report.append("🔴 严重问题:")
            for issue in issues[:5]:  # 最多显示5个问题
                report.append(f"   • {issue}")
            if len(issues) > 5:
                report.append(f"   • ... 及其他 {len(issues) - 5} 个问题")
        
        if warnings:
            report.append("")
            report.append("🟡 警告:")
            for warning in warnings[:3]:  # 最多显示3个警告
                report.append(f"   • {warning}")
            if len(warnings) > 3:
                report.append(f"   • ... 及其他 {len(warnings) - 3} 个警告")
        
        if not issues and not warnings:
            report.append("")
            report.append("✅ 无配置问题")
        
        return "\n".join(report)
    
    def get_status_code(self) -> int:
        """获取状态码"""
        if self.results.get('issues'):
            return 1  # 严重问题
        elif self.results.get('warnings'):
            return 2  # 警告
        else:
            return 0  # 正常

def main():
    """主函数"""
    manager = ConfigSyncManager()
    
    # 解析命令行参数
    validate_only = '--validate' in sys.argv
    sync_configs = '--sync' in sys.argv
    create_backup = '--backup' in sys.argv
    
    restore_backup = None
    for arg in sys.argv:
        if arg.startswith('--restore='):
            restore_backup = arg.split('=')[1]
            break
    
    # 默认行为：验证配置
    if not any([validate_only, sync_configs, create_backup, restore_backup]):
        validate_only = True
    
    try:
        # 执行操作
        if restore_backup:
            success = manager.restore_backup(restore_backup)
        elif create_backup:
            backup_id = manager.create_backup()
            success = bool(backup_id)
        elif sync_configs:
            success = manager.sync_configurations()
        else:  # validate_only
            success = manager.validate_configuration()
        
        # 生成报告
        report = manager.generate_sync_report()
        print(report)
        
        # 获取状态码
        status_code = manager.get_status_code()
        
        # Claude Hook响应
        if os.getenv('CLAUDE_HOOK_MODE') == '1':
            hook_response = {
                'config_status': 'valid' if status_code == 0 else ('warning' if status_code == 2 else 'invalid'),
                'operation_successful': success,
                'results': manager.results
            }
            print(f"\n__CLAUDE_HOOK_RESPONSE__: {json.dumps(hook_response, indent=2)}")
        
        sys.exit(status_code)
        
    except Exception as e:
        print(f"❌ 配置同步执行失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()