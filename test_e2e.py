"""End-to-end test: exploration → replay → report generation."""
import asyncio
import json
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

async def main():
    from playwrights_pen.config import ConfirmationMode
    from playwrights_pen.core import TestOrchestrator, TestParser
    from playwrights_pen.models import ExecutionMode, SessionStatus, TestCase
    from playwrights_pen.storage import Repository
    from playwrights_pen.core.result_formatter import HTMLReportGenerator, JSONFormatter
    from playwrights_pen.models.suite import SuiteExecution
    from datetime import datetime

    repository = Repository()
    
    # ===== Phase 1: Exploration =====
    print("=" * 60)
    print("Phase 1: EXPLORATION MODE - First Run")
    print("=" * 60)
    
    parser = TestParser()
    description = "打开百度首页，在搜索框输入Playwright，点击搜索按钮"
    testcase = await parser.create_testcase("百度搜索测试", description)
    testcase.steps = parser.identify_key_steps(testcase.steps)
    repository.save_testcase(testcase)
    
    print(f"  TestCase ID: {testcase.id}")
    print(f"  Steps: {len(testcase.steps)}")
    for i, s in enumerate(testcase.steps, 1):
        print(f"    {i}. {s.action.value}: {s.description}")
    
    orchestrator = TestOrchestrator(confirmation_mode=ConfirmationMode.NONE)
    
    def on_step(result):
        icon = "[OK]" if result.passed else "[FAIL]"
        step = result.step
        print(f"  {icon} Step {result.execution.step_index + 1}: "
              f"{step.action.value} - {step.description or ''}")
        if result.execution.element_ref_used:
            print(f"       ref={result.execution.element_ref_used}")
        if result.execution.error:
            print(f"       Error: {result.execution.error}")
    
    try:
        session1 = await orchestrator.run_exploration(testcase, on_step_complete=on_step)
        print(f"\n  Session ID: {session1.id}")
        print(f"  Status: {session1.status.value}")
        print(f"  Steps: {session1.passed_steps}/{session1.total_steps}")
        
        # Print what was recorded
        print(f"\n  Recorded {len(session1.step_executions)} step executions:")
        for se in session1.step_executions:
            print(f"    Step {se.step_index}: status={se.status.value}, ref={se.element_ref_used}")
    except Exception as e:
        print(f"  [ERROR] Exploration failed: {e}")
        import traceback; traceback.print_exc()
        return
    
    # Save testcase with recorded refs
    # Copy recorded refs to step.recorded_ref for replay
    for se in session1.step_executions:
        if se.element_ref_used and se.step_index < len(testcase.steps):
            testcase.steps[se.step_index].recorded_ref = se.element_ref_used
    repository.save_testcase(testcase)
    print("\n  [OK] Testcase saved with recorded refs")
    
    # ===== Phase 2: Regression (Replay) =====
    print()
    print("=" * 60)
    print("Phase 2: REGRESSION MODE - Replay")
    print("=" * 60)
    
    # Load testcase fresh from storage
    loaded_tc = repository.get_testcase(testcase.id)
    if not loaded_tc:
        print("  [FAIL] Could not load testcase!")
        return
    
    print(f"  Loaded TestCase: {loaded_tc.name}")
    print(f"  Steps with recorded refs:")
    for i, s in enumerate(loaded_tc.steps, 1):
        print(f"    {i}. {s.action.value}: ref={s.recorded_ref}")
    
    try:
        session2 = await orchestrator.run_regression(loaded_tc, 
                                                       reference_session=session1,
                                                       on_step_complete=on_step)
        print(f"\n  Session ID: {session2.id}")
        print(f"  Status: {session2.status.value}")
        print(f"  Steps: {session2.passed_steps}/{session2.total_steps}")
        print("  [OK] Regression completed!")
    except Exception as e:
        print(f"  [ERROR] Regression failed: {e}")
        import traceback; traceback.print_exc()
    
    # ===== Phase 3: Report Generation =====
    print()
    print("=" * 60)
    print("Phase 3: REPORT GENERATION")
    print("=" * 60)
    
    # JSON Report
    formatter = JSONFormatter()
    json_output = formatter.format_session(session1, testcase)
    print(f"  JSON report generated ({len(json_output)} chars)")
    
    # HTML Report  
    all_sessions = repository.list_sessions()
    passed = sum(1 for s in all_sessions if s.status == SessionStatus.PASSED)
    failed = sum(1 for s in all_sessions if s.status == SessionStatus.FAILED)
    
    execution = SuiteExecution(
        suite_id="e2e_test",
        suite_name="End-to-End Verification",
        total_cases=len(all_sessions),
        passed_cases=passed,
        failed_cases=failed,
        status="passed" if failed == 0 else "failed",
    )
    execution.started_at = datetime.now()
    execution.ended_at = datetime.now()
    
    generator = HTMLReportGenerator()
    tc_map = {tc.id: tc for tc in repository.list_testcases()}
    report_path = generator.generate_suite_report(execution, all_sessions, tc_map)
    print(f"  HTML report generated: {report_path}")
    
    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Exploration:  {session1.status.value} ({session1.passed_steps}/{session1.total_steps})")
    if 'session2' in dir():
        print(f"  Regression:   {session2.status.value} ({session2.passed_steps}/{session2.total_steps})")
    print(f"  Test Cases:   {len(repository.list_testcases())}")
    print(f"  Sessions:     {len(repository.list_sessions())}")
    print(f"  HTML Report:  {report_path}")
    print("  [ALL DONE]")

if __name__ == "__main__":
    asyncio.run(main())
