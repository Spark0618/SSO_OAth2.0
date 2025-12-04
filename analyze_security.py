"""
安全分析脚本
用于检查代码的安全性和性能问题
"""

import os
import re
import sys
import mimetypes
from typing import List, Dict, Any

class SecurityAnalyzer:
    """安全分析器"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = os.path.abspath(project_root)
        self.security_issues = []
        self.performance_issues = []
        self.file_types = {
            '.html': 'HTML',
            '.js': 'JavaScript',
            '.css': 'CSS',
            '.jsx': 'React JSX',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript React',
            '.vue': 'Vue',
            '.json': 'JSON',
            '.py': 'Python'  # 明确添加 Python
        }
    
    def get_file_type(self, file_path: str) -> str:
        """获取文件类型"""
        _, ext = os.path.splitext(file_path)
        return self.file_types.get(ext, 'Unknown')
    
    def find_files(self) -> List[str]:
        """查找项目中的文件"""
        # 定义要扫描的扩展名
        extensions = ['.html', '.js', '.jsx', '.ts', '.tsx', '.vue', '.css', '.json', '.py']
        
        # 定义要忽略的目录
        ignore_dirs = {
            '.git', '__pycache__', 'node_modules', '.venv', 'venv', 
            '.idea', '.vscode', 'htmlcov', '.pytest_cache',
            'tests'  # 忽略测试目录，避免误报硬编码密码
        }
        
        files = []
        for root, dirs, filenames in os.walk(self.project_root):
            # 修改 dirs 列表以跳过忽略的目录 (必须原地修改)
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for filename in filenames:
                _, ext = os.path.splitext(filename)
                if ext in extensions:
                    # 排除本脚本自身
                    if filename == 'analyze_security.py':
                        continue
                    files.append(os.path.join(root, filename))
        
        return files
    
    def read_file(self, file_path: str) -> str:
        """读取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            print(f"读取文件 {file_path} 失败: {str(e)}")
            return ""
    
    def check_security_issues(self, file_path: str, content: str):
        """检查通用安全问题"""
        file_type = self.get_file_type(file_path)
        
        # 1. 检查硬编码凭据 (所有文件)
        credential_patterns = [
            r'(password|passwd|pwd|secret|token|api_key|access_key)\s*=\s*["\'][^"\']+["\']',
            r'(password|passwd|pwd|secret|token|api_key|access_key)\s*:\s*["\'][^"\']+["\']'
        ]
        
        # 排除示例配置和环境变量文件
        if not file_path.endswith(('.env.example', 'config.json', '.md')):
            for pattern in credential_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # 忽略空值或常见占位符
                    val = match.group()
                    if "your-" in val or "change-" in val or '""' in val or "''" in val:
                        continue
                        
                    line_no = content[:match.start()].count('\n') + 1
                    self.security_issues.append({
                        'type': 'Hardcoded Credentials',
                        'severity': 'High',
                        'file': file_path,
                        'line': line_no,
                        'description': '发现潜在的硬编码凭据',
                        'code': val[:50] + "..." if len(val) > 50 else val,
                        'recommendation': '使用环境变量存储敏感信息'
                    })

        # 2. Python SQL 注入检查
        if file_type == 'Python':
            # 检查简单的 f-string 拼接 SQL
            sql_pattern = r'execute\s*\(\s*f["\'].*?(SELECT|INSERT|UPDATE|DELETE).*?\{.*?\}'
            matches = re.finditer(sql_pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                line_no = content[:match.start()].count('\n') + 1
                self.security_issues.append({
                    'type': 'SQL Injection',
                    'severity': 'High',
                    'file': file_path,
                    'line': line_no,
                    'description': '在 SQL 执行中使用 f-string 拼接，存在注入风险',
                    'code': match.group().strip()[:50] + "...",
                    'recommendation': '使用参数化查询 (例如 :name 或 %s)'
                })

        # 3. 前端 XSS 检查
        if file_type in ['HTML', 'JavaScript', 'TypeScript', 'React JSX', 'Vue']:
            xss_patterns = [
                (r'\.innerHTML\s*=', '使用 .innerHTML 可能导致 XSS'),
                (r'dangerouslySetInnerHTML', 'React 危险属性使用'),
                (r'v-html', 'Vue v-html 指令使用')
            ]
            for pattern, desc in xss_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    line_no = content[:match.start()].count('\n') + 1
                    self.security_issues.append({
                        'type': 'XSS Risk',
                        'severity': 'Medium',
                        'file': file_path,
                        'line': line_no,
                        'description': desc,
                        'code': match.group(),
                        'recommendation': '确保内容已转义，或使用安全的替代方法'
                    })

    def check_performance_issues(self, file_path: str, content: str):
        """检查性能问题"""
        # 简单检查大文件
        if len(content) > 500 * 1024: # 500KB
            self.performance_issues.append({
                'type': 'Large File',
                'severity': 'Low',
                'file': file_path,
                'line': 1,
                'description': f'文件过大 ({len(content)/1024:.1f} KB)',
                'code': 'N/A',
                'recommendation': '考虑拆分文件或进行代码压缩'
            })

    def analyze_project(self):
        """分析整个项目"""
        files = self.find_files()
        print(f"找到 {len(files)} 个文件进行分析")
        
        for file_path in files:
            # 使用相对路径显示，更整洁
            rel_path = os.path.relpath(file_path, self.project_root)
            self.analyze_file(rel_path, file_path)
        
        print(f"分析完成，发现 {len(self.security_issues)} 个安全问题，{len(self.performance_issues)} 个性能问题")
    
    def analyze_file(self, rel_path: str, abs_path: str):
        content = self.read_file(abs_path)
        if not content:
            return
        
        self.check_security_issues(rel_path, content)
        self.check_performance_issues(rel_path, content)

    def generate_report(self, output_file: str = "security_analysis.md"):
        """生成分析报告"""
        report = []
        report.append("# 代码安全与性能分析报告\n")
        
        # 安全问题
        report.append("## 安全问题\n")
        if not self.security_issues:
            report.append("✅ 未发现明显的安全问题。\n")
        else:
            for i, issue in enumerate(self.security_issues, 1):
                report.append(f"### {i}. {issue['type']} ({issue['severity']})")
                report.append(f"- **文件**: `{issue['file']}` (行 {issue['line']})")
                report.append(f"- **描述**: {issue['description']}")
                report.append(f"- **代码**: `{issue['code'].strip()}`")
                report.append(f"- **建议**: {issue['recommendation']}\n")

        # 性能问题
        report.append("## 性能问题\n")
        if not self.performance_issues:
            report.append("✅ 未发现明显的性能问题。\n")
        else:
            for i, issue in enumerate(self.performance_issues, 1):
                report.append(f"### {i}. {issue['type']} ({issue['severity']})")
                report.append(f"- **文件**: `{issue['file']}`")
                report.append(f"- **描述**: {issue['description']}")
                report.append(f"- **建议**: {issue['recommendation']}\n")

        # 保存
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        print(f"\n分析报告已保存到 {output_file}")
        
        # 打印摘要
        print("\n=== 分析摘要 ===")
        print(f"安全问题: {len(self.security_issues)}")
        print(f"性能问题: {len(self.performance_issues)}")

def main():
    analyzer = SecurityAnalyzer()
    print("开始代码静态分析...")
    analyzer.analyze_project()
    analyzer.generate_report()

if __name__ == "__main__":
    main()