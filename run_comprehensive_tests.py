"""
综合测试脚本
运行所有测试并生成最终报告
(修复版：解决 Windows 乱码问题)
"""

import os
import sys
import subprocess
import time
import json
from typing import Dict, Any, List

class ComprehensiveTestRunner:
    """综合测试运行器"""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.end_time = None
    
    def run_command(self, command: str, description: str) -> Dict[str, Any]:
        """运行命令并返回结果"""
        print(f"\n{'='*60}")
        print(f"运行: {description}")
        print(f"命令: {command}")
        print('='*60)
        
        start_time = time.time()
        
        # === 关键修复：设置环境变量，强制 Python 子进程输出 UTF-8 ===
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=600,
                encoding='utf-8',
                errors='replace',
                env=env  # 传入修改后的环境变量
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            if result.stdout:
                print("--- 输出摘要 ---")
                print("\n".join(result.stdout.splitlines()[:5]))
                if len(result.stdout.splitlines()) > 5:
                    print("...")
            
            if result.stderr and result.returncode != 0:
                print("--- 错误摘要 ---")
                print("\n".join(result.stderr.splitlines()[:5]))
            
            return {
                'command': command,
                'description': description,
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'execution_time': execution_time,
                'success': result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            print("!!! 命令超时 !!!")
            return {
                'command': command,
                'description': description,
                'exit_code': -1,
                'stdout': '',
                'stderr': 'Command timed out after 10 minutes',
                'execution_time': 600,
                'success': False
            }
        except Exception as e:
            print(f"!!! 执行异常: {e} !!!")
            return {
                'command': command,
                'description': description,
                'exit_code': -1,
                'stdout': '',
                'stderr': str(e),
                'execution_time': 0,
                'success': False
            }
    
    def check_prerequisites(self) -> bool:
        """检查先决条件"""
        print("检查先决条件...")
        python_check = self.run_command("python --version", "检查Python版本")
        if not python_check['success']:
            print("错误: 未找到Python或Python不可用")
            return False
        
        print(f"Python版本: {python_check['stdout'].strip()}")
        
        if not os.path.exists(".env"):
            print("警告: 未找到 .env 配置文件")
        else:
            print("✓ 已找到 .env 配置文件")

        return True
    
    def run_unit_tests(self):
        """运行单元测试"""
        print("\n>>> 阶段 1/5: 单元测试")
        if not os.path.exists("tests"):
            self.test_results['unit_tests'] = {'success': False, 'message': '未找到tests目录'}
            return
        res = self.run_command("python -m pytest tests/ -v", "运行单元测试")
        self.test_results['unit_tests'] = res
    
    def run_system_tests(self):
        """运行系统测试"""
        print("\n>>> 阶段 2/5: 系统测试")
        if not os.path.exists("test_system.py"):
            self.test_results['system_tests'] = {'success': False, 'message': '未找到test_system.py'}
            return
        res = self.run_command("python test_system.py", "运行系统测试")
        self.test_results['system_tests'] = res
    
    def run_performance_tests(self):
        """运行性能测试"""
        print("\n>>> 阶段 3/5: 性能测试")
        if not os.path.exists("test_performance.py"):
            self.test_results['performance_tests'] = {'success': False, 'message': '未找到test_performance.py'}
            return
        res = self.run_command("python test_performance.py", "运行性能测试")
        self.test_results['performance_tests'] = res
    
    def run_database_analysis(self):
        """运行数据库分析"""
        print("\n>>> 阶段 4/5: 数据库分析")
        if not os.path.exists("analyze_database.py"):
            self.test_results['database_analysis'] = {'success': False, 'message': '未找到analyze_database.py'}
            return
        res = self.run_command("python analyze_database.py", "运行数据库分析")
        self.test_results['database_analysis'] = res
    
    def run_security_analysis(self):
        """运行安全分析"""
        print("\n>>> 阶段 5/5: 安全分析")
        if not os.path.exists("analyze_security.py"):
            self.test_results['security_analysis'] = {'success': False, 'message': '未找到analyze_security.py'}
            return
        res = self.run_command("python analyze_security.py", "运行安全分析")
        self.test_results['security_analysis'] = res
    
    def generate_comprehensive_report(self):
        """生成综合报告"""
        print("\n生成综合报告...")
        report = []
        report.append("# 综合测试报告\n")
        report.append(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.start_time))}\n")
        report.append(f"总耗时: {self.end_time - self.start_time:.2f} 秒\n")
        
        report.append("## 测试结果摘要\n")
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results.values() if r.get('success', False))
        failed = total - passed
        
        report.append(f"- 总任务数: {total}\n")
        report.append(f"- 通过: {passed}\n")
        report.append(f"- 失败: {failed}\n")
        report.append(f"- 成功率: {passed/total*100:.1f}%\n")
        
        report.append("## 详细结果\n")
        for name, result in self.test_results.items():
            status = "✅ 通过" if result.get('success') else "❌ 失败"
            report.append(f"### {name} ({status})\n")
            if 'execution_time' in result:
                report.append(f"- 耗时: {result['execution_time']:.2f}s\n")
            if not result.get('success') and result.get('stderr'):
                report.append("#### 错误输出:\n")
                report.append(f"```\n{result['stderr'][-1000:]}\n```\n")
            report.append("---\n")
            
        with open("comprehensive_test_report.md", 'w', encoding='utf-8') as f:
            f.write("".join(report))
        print("综合报告已保存到 comprehensive_test_report.md")

    def run_all_tests(self):
        print("开始综合测试流程...")
        self.start_time = time.time()
        
        if not self.check_prerequisites():
            return
            
        self.run_unit_tests()
        self.run_system_tests()
        self.run_performance_tests()
        self.run_database_analysis()
        self.run_security_analysis()
        
        self.end_time = time.time()
        self.generate_comprehensive_report()
        print("\n所有测试流程结束！")

if __name__ == "__main__":
    runner = ComprehensiveTestRunner()
    runner.run_all_tests()