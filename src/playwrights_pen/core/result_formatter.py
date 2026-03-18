"""Result formatters for different output formats."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import Session, SessionStatus, TestCase
from ..models.suite import SuiteExecution


class ResultFormatter:
    """Base class for result formatters."""
    
    def format_session(self, session: Session, testcase: TestCase | None = None) -> str:
        """Format a single session result."""
        raise NotImplementedError
    
    def format_suite(self, execution: SuiteExecution, sessions: list[Session]) -> str:
        """Format a suite execution result."""
        raise NotImplementedError


class JSONFormatter(ResultFormatter):
    """JSON output formatter."""
    
    def format_session(self, session: Session, testcase: TestCase | None = None) -> str:
        """Format session as JSON."""
        data = {
            "id": session.id,
            "test_case_id": session.test_case_id,
            "test_case_name": testcase.name if testcase else None,
            "status": session.status.value,
            "mode": session.mode.value,
            "total_steps": session.total_steps,
            "passed_steps": session.passed_steps,
            "failed_steps": session.failed_steps,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "duration_seconds": (
                (session.ended_at - session.started_at).total_seconds()
                if session.ended_at and session.started_at else 0
            ),
            "error": session.error_message,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def format_suite(self, execution: SuiteExecution, sessions: list[Session]) -> str:
        """Format suite execution as JSON."""
        data = {
            "id": execution.id,
            "suite_id": execution.suite_id,
            "suite_name": execution.suite_name,
            "status": execution.status,
            "total_cases": execution.total_cases,
            "passed_cases": execution.passed_cases,
            "failed_cases": execution.failed_cases,
            "skipped_cases": execution.skipped_cases,
            "pass_rate": execution.pass_rate,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "ended_at": execution.ended_at.isoformat() if execution.ended_at else None,
            "duration_seconds": execution.duration_seconds,
            "sessions": [
                {
                    "id": s.id,
                    "test_case_id": s.test_case_id,
                    "status": s.status.value,
                    "passed_steps": s.passed_steps,
                    "failed_steps": s.failed_steps,
                    "error": s.error_message,
                }
                for s in sessions
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)


class JUnitFormatter(ResultFormatter):
    """JUnit XML output formatter for CI integration."""
    
    def format_session(self, session: Session, testcase: TestCase | None = None) -> str:
        """Format session as JUnit XML."""
        duration = 0
        if session.ended_at and session.started_at:
            duration = (session.ended_at - session.started_at).total_seconds()
        
        name = testcase.name if testcase else session.test_case_id
        
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="{name}" tests="1" failures="{1 if session.status == SessionStatus.FAILED else 0}" time="{duration:.2f}">
    <testcase name="{name}" classname="playwrights_pen" time="{duration:.2f}">
'''
        if session.status == SessionStatus.FAILED:
            error = session.error_message or "Test failed"
            xml += f'      <failure message="{error}">{error}</failure>\n'
        
        xml += '''    </testcase>
  </testsuite>
</testsuites>'''
        return xml
    
    def format_suite(self, execution: SuiteExecution, sessions: list[Session]) -> str:
        """Format suite execution as JUnit XML."""
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="{execution.suite_name}" tests="{execution.total_cases}" failures="{execution.failed_cases}" time="{execution.duration_seconds:.2f}">
'''
        for s in sessions:
            duration = 0
            if s.ended_at and s.started_at:
                duration = (s.ended_at - s.started_at).total_seconds()
            
            xml += f'  <testsuite name="{s.test_case_id}" tests="{s.total_steps}" failures="{s.failed_steps}" time="{duration:.2f}">\n'
            xml += f'    <testcase name="{s.test_case_id}" classname="playwrights_pen" time="{duration:.2f}">\n'
            
            if s.status == SessionStatus.FAILED:
                error = s.error_message or "Test failed"
                xml += f'      <failure message="{error}">{error}</failure>\n'
            
            xml += '    </testcase>\n'
            xml += '  </testsuite>\n'
        
        xml += '</testsuites>'
        return xml


class HTMLReportGenerator:
    """Generate HTML test reports."""
    
    def __init__(self, output_dir: Path | None = None) -> None:
        """Initialize generator.
        
        Args:
            output_dir: Directory for report output
        """
        from ..config import settings
        self.output_dir = output_dir or settings.data_dir / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_suite_report(
        self,
        execution: SuiteExecution,
        sessions: list[Session],
        testcases: dict[str, TestCase] | None = None,
    ) -> Path:
        """Generate HTML report for suite execution.
        
        Args:
            execution: Suite execution result
            sessions: Session details
            testcases: Map of test case ID to TestCase
            
        Returns:
            Path to generated report
        """
        testcases = testcases or {}
        
        # Build test results HTML
        results_html = ""
        for s in sessions:
            tc = testcases.get(s.test_case_id)
            name = tc.name if tc else s.test_case_id
            
            status_class = "passed" if s.status == SessionStatus.PASSED else "failed"
            status_icon = "✓" if s.status == SessionStatus.PASSED else "✗"
            
            duration = 0
            if s.ended_at and s.started_at:
                duration = (s.ended_at - s.started_at).total_seconds()
            
            results_html += f"""
            <tr class="{status_class}">
                <td>{status_icon}</td>
                <td>{name}</td>
                <td>{s.passed_steps}/{s.total_steps}</td>
                <td>{duration:.1f}s</td>
                <td>{s.error_message or '-'}</td>
            </tr>
            """
        
        # Generate full HTML
        html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>测试报告 - {execution.suite_name}</title>
    <style>
        :root {{
            --bg: #0d1117;
            --card: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --text-muted: #8b949e;
            --green: #3fb950;
            --red: #f85149;
            --blue: #58a6ff;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: var(--blue); margin-bottom: 1rem; }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            text-align: center;
        }}
        .stat-value {{ font-size: 2rem; font-weight: bold; }}
        .stat-label {{ color: var(--text-muted); font-size: 0.9rem; }}
        .passed .stat-value {{ color: var(--green); }}
        .failed .stat-value {{ color: var(--red); }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card);
            border-radius: 8px;
            overflow: hidden;
        }}
        th, td {{
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{ background: var(--border); }}
        tr.passed td:first-child {{ color: var(--green); }}
        tr.failed td:first-child {{ color: var(--red); }}
        tr.failed {{ background: rgba(248, 81, 73, 0.1); }}
        .timestamp {{ color: var(--text-muted); font-size: 0.8rem; margin-top: 2rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 测试报告</h1>
        <h2 style="color: var(--text-muted); margin-bottom: 2rem;">{execution.suite_name}</h2>
        
        <div class="summary">
            <div class="stat-card">
                <div class="stat-value">{execution.total_cases}</div>
                <div class="stat-label">总用例数</div>
            </div>
            <div class="stat-card passed">
                <div class="stat-value">{execution.passed_cases}</div>
                <div class="stat-label">通过</div>
            </div>
            <div class="stat-card failed">
                <div class="stat-value">{execution.failed_cases}</div>
                <div class="stat-label">失败</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{execution.pass_rate:.1f}%</div>
                <div class="stat-label">通过率</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{execution.duration_seconds:.1f}s</div>
                <div class="stat-label">耗时</div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>状态</th>
                    <th>用例名称</th>
                    <th>步骤</th>
                    <th>耗时</th>
                    <th>错误信息</th>
                </tr>
            </thead>
            <tbody>
                {results_html}
            </tbody>
        </table>
        
        <p class="timestamp">
            生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
</body>
</html>
"""
        
        # Save report
        filename = f"report_{execution.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        report_path = self.output_dir / filename
        report_path.write_text(html, encoding='utf-8')
        
        return report_path
    
    def generate_session_report(
        self,
        session: Session,
        testcase: TestCase | None = None,
    ) -> Path:
        """Generate HTML report for a single test session.
        
        Args:
            session: Session result
            testcase: Associated test case
            
        Returns:
            Path to generated report
        """
        name = testcase.name if testcase else session.test_case_id
        description = testcase.description if testcase else ""
        duration = 0
        if session.ended_at and session.started_at:
            duration = (session.ended_at - session.started_at).total_seconds()
        
        status_class = "passed" if session.status == SessionStatus.PASSED else "failed"
        status_text = "✅ 通过" if session.status == SessionStatus.PASSED else "❌ 失败"
        
        # Build step details
        steps_html = ""
        steps = testcase.steps if testcase else []
        
        for i, exec_record in enumerate(session.step_executions):
            step = steps[i] if i < len(steps) else None
            step_status = "passed" if exec_record.status == SessionStatus.PASSED else "failed"
            step_icon = "✓" if exec_record.status == SessionStatus.PASSED else "✗"
            
            step_duration = 0
            if exec_record.ended_at and exec_record.started_at:
                step_duration = (exec_record.ended_at - exec_record.started_at).total_seconds()
            
            action = step.action.value if step else f"Step {i+1}"
            desc = step.description or "" if step else ""
            ref = exec_record.element_ref_used or "-"
            error = exec_record.error or "-"
            
            steps_html += f"""
            <tr class="{step_status}">
                <td>{step_icon}</td>
                <td>{i+1}</td>
                <td><span class="action-badge">{action}</span></td>
                <td>{desc}</td>
                <td><code>{ref}</code></td>
                <td>{step_duration:.1f}s</td>
                <td>{error}</td>
            </tr>
            """
        
        html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>测试报告 - {name}</title>
    <style>
        :root {{
            --bg: #0d1117;
            --card: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --text-muted: #8b949e;
            --green: #3fb950;
            --red: #f85149;
            --blue: #58a6ff;
            --purple: #bc8cff;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: var(--blue); margin-bottom: 0.5rem; }}
        .subtitle {{ color: var(--text-muted); margin-bottom: 2rem; }}
        .status-banner {{
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            font-size: 1.2rem;
            font-weight: bold;
        }}
        .status-banner.passed {{
            background: rgba(63, 185, 80, 0.15);
            border: 1px solid var(--green);
            color: var(--green);
        }}
        .status-banner.failed {{
            background: rgba(248, 81, 73, 0.15);
            border: 1px solid var(--red);
            color: var(--red);
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat-card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.2rem;
            text-align: center;
        }}
        .stat-value {{ font-size: 1.8rem; font-weight: bold; color: var(--blue); }}
        .stat-label {{ color: var(--text-muted); font-size: 0.85rem; }}
        .passed .stat-value {{ color: var(--green); }}
        .failed .stat-value {{ color: var(--red); }}
        h2 {{ color: var(--purple); margin: 2rem 0 1rem; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card);
            border-radius: 8px;
            overflow: hidden;
        }}
        th, td {{
            padding: 0.8rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{ background: var(--border); font-size: 0.85rem; text-transform: uppercase; }}
        tr.passed td:first-child {{ color: var(--green); }}
        tr.failed td:first-child {{ color: var(--red); }}
        tr.failed {{ background: rgba(248, 81, 73, 0.08); }}
        .action-badge {{
            background: var(--border);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-family: monospace;
        }}
        code {{
            background: var(--border);
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.85rem;
        }}
        .timestamp {{ color: var(--text-muted); font-size: 0.8rem; margin-top: 2rem; }}
        .meta {{ color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.5rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 {name}</h1>
        <p class="subtitle">{description}</p>
        
        <div class="status-banner {status_class}">
            {status_text} — {session.passed_steps}/{session.total_steps} 步骤通过 · 耗时 {duration:.1f}s
        </div>
        
        <div class="summary">
            <div class="stat-card">
                <div class="stat-value">{session.total_steps}</div>
                <div class="stat-label">总步骤</div>
            </div>
            <div class="stat-card passed">
                <div class="stat-value">{session.passed_steps}</div>
                <div class="stat-label">通过</div>
            </div>
            <div class="stat-card failed">
                <div class="stat-value">{session.failed_steps}</div>
                <div class="stat-label">失败</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{duration:.1f}s</div>
                <div class="stat-label">总耗时</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{session.mode.value}</div>
                <div class="stat-label">执行模式</div>
            </div>
        </div>
        
        <p class="meta">Session ID: <code>{session.id}</code></p>
        <p class="meta">Test Case ID: <code>{session.test_case_id}</code></p>
        {f'<p class="meta">错误: {session.error_message}</p>' if session.error_message else ''}
        
        <h2>📝 步骤详情</h2>
        <table>
            <thead>
                <tr>
                    <th>状态</th>
                    <th>#</th>
                    <th>动作</th>
                    <th>描述</th>
                    <th>元素引用</th>
                    <th>耗时</th>
                    <th>错误</th>
                </tr>
            </thead>
            <tbody>
                {steps_html}
            </tbody>
        </table>
        
        <p class="timestamp">
            开始时间: {session.started_at.strftime('%Y-%m-%d %H:%M:%S') if session.started_at else '-'} · 
            结束时间: {session.ended_at.strftime('%Y-%m-%d %H:%M:%S') if session.ended_at else '-'} · 
            报告生成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
</body>
</html>
"""
        
        filename = f"session_{session.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        report_path = self.output_dir / filename
        report_path.write_text(html, encoding='utf-8')
        
        return report_path
