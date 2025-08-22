#!/usr/bin/env python3
"""
性能监控脚本 - Reddit Signal Scanner

监控系统性能指标，包括API响应时间、Redis缓存命中率、系统资源使用。
通过Claude Code Hooks在关键操作后自动触发。

使用方式:
    python perf_metrics.py [--api-check] [--redis-check] [--system-check] [--all]

返回值:
    0: 性能正常
    1: 发现严重性能问题
    2: 警告级性能问题
"""

import sys
import json
import os
import time
import subprocess
import psutil
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import statistics

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'timestamp': datetime.now().isoformat(),
            'api_performance': {},
            'cache_performance': {},
            'system_resources': {},
            'alerts': []
        }
        
        # 性能阈值
        self.thresholds = {
            'api_response_time': {
                'excellent': 100,    # <100ms
                'good': 200,         # 100-200ms
                'acceptable': 500,   # 200-500ms
                'poor': 1000,        # 500ms-1s
                'critical': 2000     # >2s
            },
            'cache_hit_rate': {
                'excellent': 0.9,    # >90%
                'good': 0.85,        # 85-90%
                'acceptable': 0.75,  # 75-85%
                'poor': 0.6,         # 60-75%
                'critical': 0.5      # <50%
            },
            'system_resources': {
                'cpu_warning': 70,    # CPU使用率>70%
                'cpu_critical': 85,   # CPU使用率>85%
                'memory_warning': 80, # 内存使用率>80%
                'memory_critical': 90, # 内存使用率>90%
                'disk_warning': 85,   # 磁盘使用率>85%
                'disk_critical': 95   # 磁盘使用率>95%
            }
        }
    
    def check_api_performance(self) -> dict:
        """检查API性能"""
        print("🌐 检查API性能...")
        
        api_endpoints = [
            {'name': 'health_check', 'url': 'http://localhost:8000/health'},
            {'name': 'api_status', 'url': 'http://localhost:8000/api/status'},
        ]
        
        # 尝试检测本地服务
        local_endpoints = self._discover_local_endpoints()
        api_endpoints.extend(local_endpoints)
        
        results = {}
        
        for endpoint in api_endpoints:
            try:
                start_time = time.time()
                response = requests.get(endpoint['url'], timeout=10)
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000  # 转换为毫秒
                
                results[endpoint['name']] = {
                    'response_time_ms': response_time,
                    'status_code': response.status_code,
                    'success': response.status_code == 200,
                    'performance_grade': self._grade_api_performance(response_time)
                }
                
            except requests.exceptions.RequestException as e:
                results[endpoint['name']] = {
                    'response_time_ms': None,
                    'status_code': None,
                    'success': False,
                    'error': str(e),
                    'performance_grade': 'failed'
                }
        
        # 计算总体API健康度
        successful_calls = [r for r in results.values() if r['success']]
        if successful_calls:
            avg_response_time = statistics.mean([r['response_time_ms'] for r in successful_calls])
            success_rate = len(successful_calls) / len(results)
            
            self.metrics['api_performance'] = {
                'average_response_time': avg_response_time,
                'success_rate': success_rate,
                'endpoint_details': results,
                'overall_grade': self._grade_api_performance(avg_response_time)
            }
            
            # 性能告警检查
            if avg_response_time > self.thresholds['api_response_time']['critical']:
                self.metrics['alerts'].append({
                    'type': 'critical',
                    'component': 'api',
                    'message': f'API响应时间严重超时: {avg_response_time:.1f}ms'
                })
            elif avg_response_time > self.thresholds['api_response_time']['poor']:
                self.metrics['alerts'].append({
                    'type': 'warning',
                    'component': 'api',
                    'message': f'API响应时间较慢: {avg_response_time:.1f}ms'
                })
        else:
            self.metrics['api_performance'] = {
                'average_response_time': None,
                'success_rate': 0.0,
                'endpoint_details': results,
                'overall_grade': 'failed'
            }
            self.metrics['alerts'].append({
                'type': 'critical',
                'component': 'api',
                'message': '所有API端点都无法访问'
            })
        
        return self.metrics['api_performance']
    
    def check_redis_performance(self) -> dict:
        """检查Redis缓存性能"""
        print("🗄️ 检查Redis缓存性能...")
        
        try:
            # 尝试连接Redis并获取统计信息
            redis_info = self._get_redis_info()
            if redis_info:
                cache_hit_rate = self._calculate_cache_hit_rate(redis_info)
                memory_usage = redis_info.get('used_memory_human', 'unknown')
                connected_clients = redis_info.get('connected_clients', 0)
                
                self.metrics['cache_performance'] = {
                    'hit_rate': cache_hit_rate,
                    'memory_usage': memory_usage,
                    'connected_clients': connected_clients,
                    'performance_grade': self._grade_cache_performance(cache_hit_rate),
                    'redis_available': True
                }
                
                # 缓存性能告警
                if cache_hit_rate < self.thresholds['cache_hit_rate']['critical']:
                    self.metrics['alerts'].append({
                        'type': 'critical',
                        'component': 'cache',
                        'message': f'Redis缓存命中率过低: {cache_hit_rate:.1%}'
                    })
                elif cache_hit_rate < self.thresholds['cache_hit_rate']['poor']:
                    self.metrics['alerts'].append({
                        'type': 'warning',
                        'component': 'cache',
                        'message': f'Redis缓存命中率较低: {cache_hit_rate:.1%}'
                    })
            else:
                self.metrics['cache_performance'] = {
                    'redis_available': False,
                    'error': 'Redis连接失败或未启动'
                }
                
        except Exception as e:
            self.metrics['cache_performance'] = {
                'redis_available': False,
                'error': str(e)
            }
            self.metrics['alerts'].append({
                'type': 'warning',
                'component': 'cache',
                'message': f'Redis状态检查失败: {str(e)}'
            })
        
        return self.metrics['cache_performance']
    
    def check_system_resources(self) -> dict:
        """检查系统资源使用"""
        print("💻 检查系统资源使用...")
        
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 磁盘使用
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # 网络连接数
            connections = len(psutil.net_connections())
            
            # 进程数
            process_count = len(psutil.pids())
            
            self.metrics['system_resources'] = {
                'cpu_usage_percent': cpu_percent,
                'memory_usage_percent': memory_percent,
                'disk_usage_percent': disk_percent,
                'network_connections': connections,
                'process_count': process_count,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
            }
            
            # 系统资源告警检查
            if cpu_percent > self.thresholds['system_resources']['cpu_critical']:
                self.metrics['alerts'].append({
                    'type': 'critical',
                    'component': 'system',
                    'message': f'CPU使用率过高: {cpu_percent:.1f}%'
                })
            elif cpu_percent > self.thresholds['system_resources']['cpu_warning']:
                self.metrics['alerts'].append({
                    'type': 'warning',
                    'component': 'system',
                    'message': f'CPU使用率较高: {cpu_percent:.1f}%'
                })
            
            if memory_percent > self.thresholds['system_resources']['memory_critical']:
                self.metrics['alerts'].append({
                    'type': 'critical',
                    'component': 'system',
                    'message': f'内存使用率过高: {memory_percent:.1f}%'
                })
            elif memory_percent > self.thresholds['system_resources']['memory_warning']:
                self.metrics['alerts'].append({
                    'type': 'warning',
                    'component': 'system',
                    'message': f'内存使用率较高: {memory_percent:.1f}%'
                })
                
            if disk_percent > self.thresholds['system_resources']['disk_critical']:
                self.metrics['alerts'].append({
                    'type': 'critical',
                    'component': 'system',
                    'message': f'磁盘使用率过高: {disk_percent:.1f}%'
                })
            elif disk_percent > self.thresholds['system_resources']['disk_warning']:
                self.metrics['alerts'].append({
                    'type': 'warning',
                    'component': 'system',
                    'message': f'磁盘使用率较高: {disk_percent:.1f}%'
                })
                
        except Exception as e:
            self.metrics['system_resources'] = {
                'error': str(e)
            }
            self.metrics['alerts'].append({
                'type': 'error',
                'component': 'system',
                'message': f'系统资源检查失败: {str(e)}'
            })
        
        return self.metrics['system_resources']
    
    def _discover_local_endpoints(self) -> List[dict]:
        """自动发现本地运行的API端点"""
        endpoints = []
        
        # 检查常用端口
        common_ports = [3000, 5000, 8000, 8080, 3001, 5173]
        
        for port in common_ports:
            try:
                response = requests.get(f'http://localhost:{port}', timeout=2)
                if response.status_code in [200, 404]:  # 服务运行中
                    endpoints.append({
                        'name': f'local_service_{port}',
                        'url': f'http://localhost:{port}'
                    })
            except:
                pass
        
        return endpoints
    
    def _grade_api_performance(self, response_time_ms: float) -> str:
        """给API性能评分"""
        if response_time_ms <= self.thresholds['api_response_time']['excellent']:
            return 'excellent'
        elif response_time_ms <= self.thresholds['api_response_time']['good']:
            return 'good'
        elif response_time_ms <= self.thresholds['api_response_time']['acceptable']:
            return 'acceptable'
        elif response_time_ms <= self.thresholds['api_response_time']['poor']:
            return 'poor'
        else:
            return 'critical'
    
    def _grade_cache_performance(self, hit_rate: float) -> str:
        """给缓存性能评分"""
        if hit_rate >= self.thresholds['cache_hit_rate']['excellent']:
            return 'excellent'
        elif hit_rate >= self.thresholds['cache_hit_rate']['good']:
            return 'good'
        elif hit_rate >= self.thresholds['cache_hit_rate']['acceptable']:
            return 'acceptable'
        elif hit_rate >= self.thresholds['cache_hit_rate']['poor']:
            return 'poor'
        else:
            return 'critical'
    
    def _get_redis_info(self) -> Optional[dict]:
        """获取Redis信息"""
        try:
            # 尝试使用redis-cli获取信息
            result = subprocess.run(
                ['redis-cli', 'INFO'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                info = {}
                for line in result.stdout.split('\n'):
                    if ':' in line and not line.startswith('#'):
                        key, value = line.strip().split(':', 1)
                        # 尝试转换为数值
                        try:
                            if '.' in value:
                                info[key] = float(value)
                            else:
                                info[key] = int(value)
                        except ValueError:
                            info[key] = value
                return info
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return None
    
    def _calculate_cache_hit_rate(self, redis_info: dict) -> float:
        """计算缓存命中率"""
        keyspace_hits = redis_info.get('keyspace_hits', 0)
        keyspace_misses = redis_info.get('keyspace_misses', 0)
        
        total_requests = keyspace_hits + keyspace_misses
        if total_requests > 0:
            return keyspace_hits / total_requests
        return 0.0
    
    def generate_performance_report(self) -> str:
        """生成性能报告"""
        report = []
        
        # 生成时间戳
        report.append(f"📊 性能监控报告 ({self.metrics['timestamp']})")
        report.append("")
        
        # API性能报告
        api_perf = self.metrics.get('api_performance', {})
        if api_perf:
            avg_time = api_perf.get('average_response_time')
            if avg_time:
                report.append(f"🌐 API性能: {api_perf['overall_grade'].upper()}")
                report.append(f"   平均响应时间: {avg_time:.1f}ms")
                report.append(f"   成功率: {api_perf['success_rate']:.1%}")
            else:
                report.append("🌐 API性能: 无法访问")
        
        # 缓存性能报告
        cache_perf = self.metrics.get('cache_performance', {})
        if cache_perf.get('redis_available'):
            hit_rate = cache_perf.get('hit_rate', 0)
            report.append(f"🗄️ 缓存性能: {cache_perf.get('performance_grade', 'unknown').upper()}")
            report.append(f"   命中率: {hit_rate:.1%}")
            report.append(f"   内存使用: {cache_perf.get('memory_usage', 'unknown')}")
        else:
            report.append("🗄️ 缓存性能: Redis不可用")
        
        # 系统资源报告
        sys_res = self.metrics.get('system_resources', {})
        if 'error' not in sys_res:
            report.append(f"💻 系统资源:")
            report.append(f"   CPU使用: {sys_res.get('cpu_usage_percent', 0):.1f}%")
            report.append(f"   内存使用: {sys_res.get('memory_usage_percent', 0):.1f}%")
            report.append(f"   磁盘使用: {sys_res.get('disk_usage_percent', 0):.1f}%")
        
        # 告警信息
        alerts = self.metrics.get('alerts', [])
        if alerts:
            report.append("")
            report.append("⚠️ 性能告警:")
            for alert in alerts:
                emoji = "🔴" if alert['type'] == 'critical' else "🟡"
                report.append(f"   {emoji} {alert['message']}")
        else:
            report.append("")
            report.append("✅ 无性能告警")
        
        return "\n".join(report)
    
    def get_alert_level(self) -> int:
        """获取告警级别"""
        alerts = self.metrics.get('alerts', [])
        if any(alert['type'] == 'critical' for alert in alerts):
            return 1  # 严重问题
        elif any(alert['type'] in ['warning', 'error'] for alert in alerts):
            return 2  # 警告
        else:
            return 0  # 正常
    
    def save_metrics_history(self):
        """保存性能历史数据"""
        history_dir = Path('.claude/logs/performance')
        history_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        history_file = history_dir / f'metrics_{date_str}.jsonl'
        
        with open(history_file, 'a') as f:
            f.write(json.dumps(self.metrics) + '\n')

def main():
    """主函数"""
    monitor = PerformanceMonitor()
    
    # 解析命令行参数
    check_api = '--api-check' in sys.argv or '--all' in sys.argv
    check_redis = '--redis-check' in sys.argv or '--all' in sys.argv  
    check_system = '--system-check' in sys.argv or '--all' in sys.argv
    
    # 默认检查所有项目
    if not any([check_api, check_redis, check_system]):
        check_api = check_redis = check_system = True
    
    # 执行检查
    if check_api:
        monitor.check_api_performance()
    
    if check_redis:
        monitor.check_redis_performance()
    
    if check_system:
        monitor.check_system_resources()
    
    # 生成报告
    report = monitor.generate_performance_report()
    print(report)
    
    # 保存历史数据
    monitor.save_metrics_history()
    
    # 获取告警级别
    alert_level = monitor.get_alert_level()
    
    # Claude Hook响应
    if os.getenv('CLAUDE_HOOK_MODE') == '1':
        hook_response = {
            'performance_status': 'critical' if alert_level == 1 else ('warning' if alert_level == 2 else 'normal'),
            'metrics': monitor.metrics,
            'alert_count': len(monitor.metrics.get('alerts', []))
        }
        print(f"\n__CLAUDE_HOOK_RESPONSE__: {json.dumps(hook_response, indent=2)}")
    
    sys.exit(alert_level)

if __name__ == '__main__':
    main()