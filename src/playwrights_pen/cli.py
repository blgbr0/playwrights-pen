"""Command line interface for PlaywrightsPen."""

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .config import ConfirmationMode, settings
from .core import TestOrchestrator, TestParser
from .models import ExecutionMode, SessionStatus, TestCase
from .storage import Repository

app = typer.Typer(
    name="playwrights-pen",
    help="PlaywrightsPen - Natural language automated testing service",
    add_completion=False,
)

# Use ASCII-safe console for Windows compatibility
_is_windows = sys.platform.startswith('win')
console = Console(force_terminal=True, legacy_windows=_is_windows, emoji=not _is_windows)
repository = Repository()


@app.command()
def run(
    description: str = typer.Argument(..., help="Natural language test description"),
    name: str = typer.Option(None, "--name", "-n", help="Test case name"),
    mode: str = typer.Option(
        "exploration",
        "--mode",
        "-m",
        help="Execution mode: exploration, regression",
    ),
    confirm: str = typer.Option(
        "key_steps",
        "--confirm",
        "-c",
        help="Confirmation mode: every_step, key_steps, none",
    ),
    headless: bool = typer.Option(False, "--headless", help="Run in headless mode"),
):
    """Run a test from natural language description.
    
    Example:
        playwrights-pen run "打开百度，搜索Playwright，验证结果"
    """
    asyncio.run(_run_test(description, name, mode, confirm, headless))


async def _run_test(
    description: str,
    name: Optional[str],
    mode: str,
    confirm: str,
    headless: bool,
):
    """Async implementation of run command."""
    console.print(Panel.fit(
        "[bold blue]PlaywrightsPen[/bold blue] - 剧作家之笔",
        subtitle="Natural Language Test Automation",
    ))
    
    # Set headless mode
    if headless:
        settings.browser_headless = True
    
    # Parse confirmation mode
    try:
        confirmation_mode = ConfirmationMode(confirm)
    except ValueError:
        console.print(f"[red]Invalid confirmation mode: {confirm}[/red]")
        raise typer.Exit(1)
    
    # Create or find test case
    testcase_name = name or f"Test_{description[:20]}..."
    
    # Use ASCII spinner for Windows compatibility
    spinner_type = "line" if _is_windows else "dots"
    
    with Progress(
        SpinnerColumn(spinner_type),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing test description...", total=None)
        
        parser = TestParser()
        testcase = await parser.create_testcase(testcase_name, description)
        testcase.steps = parser.identify_key_steps(testcase.steps)
        repository.save_testcase(testcase)
        
        progress.update(task, description="Test case created")
    
    # Display parsed steps
    console.print("\n[bold]Parsed Steps:[/bold]")
    steps_table = Table(show_header=True)
    steps_table.add_column("#", style="dim", width=3)
    steps_table.add_column("Action", style="cyan")
    steps_table.add_column("Description")
    steps_table.add_column("Key", justify="center")
    
    for i, step in enumerate(testcase.steps, 1):
        key_marker = "[KEY]" if step.is_key_step else ""
        steps_table.add_row(
            str(i),
            step.action.value,
            step.description or step.selector_hint or step.url or "",
            key_marker,
        )
    
    console.print(steps_table)
    
    if not testcase.steps:
        console.print("[yellow]No steps parsed. Please check your description.[/yellow]")
        raise typer.Exit(1)
    
    # Confirm before running
    if not Confirm.ask("\nProceed with test execution?"):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    
    # Run test
    console.print("\n[bold]Running test...[/bold]\n")
    
    orchestrator = TestOrchestrator(confirmation_mode=confirmation_mode)
    
    step_results = []
    
    def on_step_complete(result):
        """Called after a step is executed (whether auto or manual)."""
        status_icon = "[green][OK][/green]" if result.passed else "[red][FAIL][/red]"
        step = result.step
        mode_note = " [dim](manual)[/dim]" if result.execution.user_modified else ""
        console.print(
            f"  {status_icon} Step {result.execution.step_index + 1}: "
            f"[cyan]{step.action.value}[/cyan] - {step.description or ''}{mode_note}"
        )
        if result.execution.error:
            console.print(f"      [red]Error: {result.execution.error}[/red]")
        step_results.append(result)
    
    def on_confirmation_needed(result):
        """Called BEFORE step execution to ask for confirmation."""
        step = result.step
        console.print(f"\n[yellow]━━━ Step {result.execution.step_index + 1} ━━━[/yellow]")
        console.print(f"  Action:      [cyan]{step.action.value}[/cyan]")
        console.print(f"  Description: {step.description or step.selector_hint or step.url or ''}")
        if step.text:
            console.print(f"  Input:       [dim]{step.text}[/dim]")
        console.print()
        console.print("[bold]Options:[/bold]")
        console.print("  [green]y[/green] = Auto-execute this step")
        console.print("  [yellow]n[/yellow] = I'll do it manually (record my action)")
        console.print("  [red]q[/red] = Abort test")
        
        choice = Prompt.ask("Choice", choices=["y", "n", "q"], default="y")
        if choice == "q":
            return False  # Will abort
        return choice == "y"  # True = auto execute, False = manual
    
    async def on_manual_record(step, step_index):
        """Called when user wants to perform the step manually."""
        from ..models import StepExecution, SessionStatus
        
        console.print(f"\n[cyan]>>> Manual mode: Please perform this action yourself <<<[/cyan]")
        console.print(f"    Expected: [dim]{step.description or step.action.value}[/dim]")
        console.print()
        
        # Wait for user to perform the action and confirm
        Prompt.ask("[dim]Press Enter when done[/dim]", default="")
        
        # Create a manual execution record
        execution = StepExecution(
            step_index=step_index,
            status=SessionStatus.PASSED,  # Assume success for manual
            user_modified=True,
        )
        
        console.print("  [blue][RECORDED][/blue] Manual action captured")
        return execution
    
    try:
        exec_mode = ExecutionMode(mode)
        if exec_mode == ExecutionMode.EXPLORATION:
            session = await orchestrator.run_exploration(
                testcase,
                on_step_complete=on_step_complete,
                on_confirmation_needed=on_confirmation_needed,
                on_manual_record=on_manual_record,
            )
        else:
            session = await orchestrator.run_regression(
                testcase,
                on_step_complete=on_step_complete,
            )
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)
    
    # Summary
    console.print("\n" + "─" * 50)
    
    if session.status == SessionStatus.PASSED:
        console.print(Panel.fit(
            f"[bold green]TEST PASSED[/bold green]\n"
            f"Steps: {session.passed_steps}/{session.total_steps}",
            title="Result",
        ))
    else:
        console.print(Panel.fit(
            f"[bold red]TEST FAILED[/bold red]\n"
            f"Passed: {session.passed_steps}, Failed: {session.failed_steps}\n"
            f"Error: {session.error_message or 'Unknown'}",
            title="Result",
        ))
        raise typer.Exit(1)


@app.command()
def replay(
    test_case_id: str = typer.Argument(..., help="ID of the test case to replay"),
    session_id: str = typer.Option(None, "--session", "-s", help="Optional: Reference session ID to use strictly for refs"),
    headless: bool = typer.Option(False, "--headless", help="Run in headless mode"),
):
    """Replay an existing test case in regression mode based on recorded references.
    
    Example:
        playwrights-pen replay e18b629525a2
    """
    asyncio.run(_run_replay(test_case_id, session_id, headless))


async def _run_replay(test_case_id: str, session_id: Optional[str], headless: bool):
    """Async implementation of replay command."""
    from .core.result_formatter import HTMLReportGenerator
    
    console.print(Panel.fit(
        "[bold blue]PlaywrightsPen[/bold blue] - 回放测试 (Regression Mode)",
        subtitle="Replay Existing Test Case",
    ))
    
    if headless:
        settings.browser_headless = True
        
    # Get test case
    testcase = repository.get_testcase(test_case_id)
    if not testcase:
        console.print(f"[red]Error: Test case '{test_case_id}' not found.[/red]")
        raise typer.Exit(1)
        
    # Get reference session if provided
    reference_session = None
    if session_id:
        reference_session = repository.get_session(session_id)
        if not reference_session:
            console.print(f"[yellow]Warning: Reference session '{session_id}' not found. Using latest recorded refs.[/yellow]")
            
    console.print(f"[bold]Replaying Test Case:[/bold] [cyan]{testcase.name}[/cyan] (ID: {testcase.id[:8]})")
    console.print("[dim]Using recorded element references (recorded_ref)...[/dim]\n")
    
    orchestrator = TestOrchestrator(confirmation_mode=ConfirmationMode.NONE)
    
    def on_step_complete(result):
        mode = "(回放)" if result.step.recorded_ref else "(重新定位)"
        status_icon = "[green][OK][/green]" if result.passed else "[red][FAIL][/red]"
        step = result.step
        console.print(
            f"  {status_icon} Step {result.execution.step_index + 1} {mode}: "
            f"[cyan]{step.action.value}[/cyan] - {step.description or ''}"
        )
        if result.execution.error:
            console.print(f"      [red]Error: {result.execution.error}[/red]")
            
    try:
        session = await orchestrator.run_regression(
            testcase,
            reference_session=reference_session,
            on_step_complete=on_step_complete,
        )
    except Exception as e:
        console.print(f"\n[red]Fatal Error: {e}[/red]")
        raise typer.Exit(1)
        
    # Generate HTML report
    console.print("\n[cyan]Generating HTML report...[/cyan]")
    generator = HTMLReportGenerator()
    report_path = generator.generate_session_report(session, testcase)
        
    console.print("\n" + "─" * 50)
    if session.status == SessionStatus.PASSED:
        console.print(Panel.fit(
            f"[bold green]REPLAY PASSED[/bold green]\n"
            f"Steps: {session.passed_steps}/{session.total_steps}\n"
            f"Report: {report_path}",
            title="Result",
        ))
    else:
        console.print(Panel.fit(
            f"[bold red]REPLAY FAILED[/bold red]\n"
            f"Passed: {session.passed_steps}, Failed: {session.failed_steps}\n"
            f"Error: {session.error_message or 'Unknown'}\n"
            f"Report: {report_path}",
            title="Result",
        ))
        raise typer.Exit(1)



@app.command()
def list_cases():
    """List all saved test cases."""
    testcases = repository.list_testcases()
    
    if not testcases:
        console.print("[yellow]No test cases found.[/yellow]")
        return
    
    table = Table(title="Test Cases")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Steps", justify="right")
    table.add_column("Tags")
    
    for tc in testcases:
        table.add_row(
            tc.id[:8],
            tc.name,
            str(len(tc.steps)),
            ", ".join(tc.tags) if tc.tags else "-",
        )
    
    console.print(table)


@app.command()
def list_sessions(
    test_case_id: str = typer.Option(None, "--case", "-c", help="Filter by test case ID"),
):
    """List execution sessions."""
    sessions = repository.list_sessions(test_case_id)
    
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return
    
    table = Table(title="Sessions")
    table.add_column("ID", style="dim")
    table.add_column("Test Case")
    table.add_column("Mode")
    table.add_column("Status")
    table.add_column("Result", justify="right")
    
    for s in sessions:
        status_color = {
            SessionStatus.PASSED: "green",
            SessionStatus.FAILED: "red",
            SessionStatus.RUNNING: "yellow",
            SessionStatus.PAUSED: "blue",
            SessionStatus.ABORTED: "magenta",
        }.get(s.status, "white")
        
        table.add_row(
            s.id[:8],
            s.test_case_id[:8],
            s.mode.value,
            f"[{status_color}]{s.status.value}[/{status_color}]",
            f"{s.passed_steps}/{s.total_steps}",
        )
    
    console.print(table)


@app.command()
def run_electron(
    description: str = typer.Argument(..., help="Natural language test description"),
    app_path: str = typer.Option(
        None, "--app", "-a", help="Path to Electron app executable or project directory"
    ),
    name: str = typer.Option(None, "--name", "-n", help="Test case name"),
    dev_mode: bool = typer.Option(
        False, "--dev", "-d", help="Run in development mode (requires project path)"
    ),
    confirm: str = typer.Option(
        "key_steps", "--confirm", "-c", help="Confirmation mode: every_step, key_steps, none"
    ),
):
    """Run a test on a local Electron application.
    
    Examples:
        # Test packaged app
        playwrights-pen run-electron "点击设置按钮" --app /path/to/app.exe
        
        # Test dev project
        playwrights-pen run-electron "打开主窗口" --app /path/to/project --dev
    """
    asyncio.run(_run_electron_test(description, app_path, name, dev_mode, confirm))


async def _run_electron_test(
    description: str,
    app_path: Optional[str],
    name: Optional[str],
    dev_mode: bool,
    confirm: str,
):
    """Async implementation of run-electron command."""
    from .targets.electron import ElectronTarget, ElectronTargetConfig
    from .config import ConfirmationMode
    from .core import TestParser, TestOrchestrator
    
    console.print(Panel.fit(
        "[bold blue]PlaywrightsPen[/bold blue] - Electron 应用测试",
        subtitle="Local Electron App Testing",
    ))
    
    # Validate app path
    if not app_path:
        app_path = settings.electron_executable_path or settings.electron_project_path
    
    if not app_path:
        console.print("[red]Error: Please provide --app path or set ELECTRON_EXECUTABLE_PATH[/red]")
        raise typer.Exit(1)
    
    # Parse confirmation mode
    try:
        confirmation_mode = ConfirmationMode(confirm)
    except ValueError:
        console.print(f"[red]Invalid confirmation mode: {confirm}[/red]")
        raise typer.Exit(1)
        
    # Determine mode
    from pathlib import Path
    path = Path(app_path).expanduser().resolve()
    
    if dev_mode or (path.is_dir() and (path / "package.json").exists()):
        console.print(f"[cyan]Mode:[/cyan] Development (project: {path})")
        config = ElectronTargetConfig(project_path=str(path))
    else:
        console.print(f"[cyan]Mode:[/cyan] Packaged App ({path})")
        config = ElectronTargetConfig(executable_path=str(path))
        
    # Create or find test case
    testcase_name = name or f"Test_{description[:20]}..."
    
    # Use ASCII spinner for Windows compatibility
    spinner_type = "line" if _is_windows else "dots"
    
    with Progress(
        SpinnerColumn(spinner_type),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing test description...", total=None)
        
        parser = TestParser()
        testcase = await parser.create_testcase(testcase_name, description)
        testcase.steps = parser.identify_key_steps(testcase.steps)
        repository.save_testcase(testcase)
        
        progress.update(task, description="Test case created")
    
    # Display parsed steps
    console.print("\n[bold]Parsed Steps:[/bold]")
    steps_table = Table(show_header=True)
    steps_table.add_column("#", style="dim", width=3)
    steps_table.add_column("Action", style="cyan")
    steps_table.add_column("Description")
    steps_table.add_column("Key", justify="center")
    
    for i, step in enumerate(testcase.steps, 1):
        key_marker = "[KEY]" if step.is_key_step else ""
        steps_table.add_row(
            str(i),
            step.action.value,
            step.description or step.selector_hint or step.url or "",
            key_marker,
        )
    
    console.print(steps_table)
    
    if not testcase.steps:
        console.print("[yellow]No steps parsed. Please check your description.[/yellow]")
        raise typer.Exit(1)
    
    # Confirm before running
    if not Confirm.ask("\nProceed with test execution?"):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    
    # Create Electron target
    target = ElectronTarget(config)
    
    try:
        console.print("\n[yellow]Launching Electron app...[/yellow]")
        await target.connect()
        console.print("[green][OK] Electron app launched[/green]")
        
        # Run test
        console.print("\n[bold]Running test on Electron...[/bold]\n")
        
        orchestrator = TestOrchestrator(
            mcp_client=target,
            confirmation_mode=confirmation_mode
        )
        
        step_results = []
        
        def on_step_complete(result):
            """Called after a step is executed (whether auto or manual)."""
            status_icon = "[green][OK][/green]" if result.passed else "[red][FAIL][/red]"
            step = result.step
            mode_note = " [dim](manual)[/dim]" if result.execution.user_modified else ""
            console.print(
                f"  {status_icon} Step {result.execution.step_index + 1}: "
                f"[cyan]{step.action.value}[/cyan] - {step.description or ''}{mode_note}"
            )
            if result.execution.error:
                console.print(f"      [red]Error: {result.execution.error}[/red]")
            step_results.append(result)
        
        def on_confirmation_needed(result):
            """Called BEFORE step execution to ask for confirmation."""
            step = result.step
            console.print(
                f"\n[bold yellow]Next Step ({result.execution.step_index + 1}/{len(testcase.steps)}):[/bold yellow] "
                f"[cyan]{step.action.value}[/cyan] - {step.description or ''}"
            )
            
            choices = ["y", "n", "m"]
            choice = Prompt.ask(
                "Execute this step?",
                choices=choices,
                default="y",
            )
            
            if choice == "y":
                return True
            elif choice == "n":
                console.print("[yellow]User cancelled execution.[/yellow]")
                raise typer.Exit(0)
            else:
                return False
                
        def on_manual_record(step, index):
            console.print(f"[cyan]Please perform step {index+1} manually in the Electron app...[/cyan]")
            Prompt.ask("Press Enter when done")
            
            from .models import StepExecution
            import datetime
            return StepExecution(
                step_index=index,
                status=SessionStatus.PASSED,
                started_at=datetime.datetime.now(),
                ended_at=datetime.datetime.now(),
                result="Manually executed by user",
                user_modified=True
            )
        
        session = await orchestrator.run_exploration(
            testcase,
            on_step_complete=on_step_complete,
            on_confirmation_needed=on_confirmation_needed,
            on_manual_record=on_manual_record,
        )
        
        console.print("\n[bold]Test Execution Summary:[/bold]")
        if session.status == SessionStatus.PASSED:
            console.print(f"[green]SUCCESS:[/green] All {session.total_steps} steps passed!")
        else:
            console.print(f"[red]FAILED:[/red] {session.failed_steps} steps failed. Check session log.")
            
        console.print(f"Session ID: {session.id}")
        
        # Keep app running a bit after test
        console.print("\n[dim]Test finished. Press Ctrl+C to close Electron app...[/dim]")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
            
    finally:
        await target.disconnect()
        console.print("[green]Electron app closed.[/green]")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Enable auto-reload"),
):
    """Start the REST API server."""
    import uvicorn
    
    console.print(Panel.fit(
        f"[bold blue]PlaywrightsPen API Server[/bold blue]\n"
        f"URL: http://{host}:{port}\n"
        f"Docs: http://{host}:{port}/docs",
    ))
    
    uvicorn.run(
        "playwrights_pen.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def config():
    """Show current configuration."""
    table = Table(title="Configuration")
    table.add_column("Setting")
    table.add_column("Value")
    
    table.add_row("LLM Base URL", settings.llm_base_url)
    table.add_row("LLM Model", settings.llm_model)
    table.add_row("API Key Set", "Yes" if settings.llm_api_key else "[red]No[/red]")
    table.add_row("Browser Headless", str(settings.browser_headless))
    table.add_row("Confirmation Mode", settings.default_confirmation_mode.value)
    table.add_row("Data Directory", str(settings.data_dir))
    
    console.print(table)


@app.command()
def run_suite(
    tags: list[str] = typer.Argument(None, help="Tags to filter test cases, e.g. @smoke @login"),
    retry: int = typer.Option(0, "--retry", "-r", help="Number of retries for failed tests"),
    stop_on_fail: bool = typer.Option(False, "--stop-on-fail", help="Stop on first failure"),
    output: str = typer.Option("terminal", "--output", "-o", help="Output format: terminal, json, junit"),
    report: bool = typer.Option(False, "--report", help="Generate HTML report"),
):
    """Run multiple test cases by tags.
    
    Examples:
        # Run all smoke tests
        playwrights-pen run-suite @smoke
        
        # Run login and order tests with retry
        playwrights-pen run-suite @login @order --retry 2
        
        # Generate HTML report
        playwrights-pen run-suite @smoke --report
    """
    asyncio.run(_run_suite(tags, retry, stop_on_fail, output, report))


async def _run_suite(
    tags: list[str] | None,
    retry: int,
    stop_on_fail: bool,
    output: str,
    generate_report: bool,
):
    """Async implementation of run-suite command."""
    from .core.suite_runner import SuiteRunner
    from .core.result_formatter import JSONFormatter, JUnitFormatter, HTMLReportGenerator
    from .models.suite import TestSuite
    
    console.print(Panel.fit(
        "[bold blue]PlaywrightsPen[/bold blue] - 批量测试执行",
        subtitle="Test Suite Runner",
    ))
    
    # Parse tags (remove @ prefix if present)
    tag_list = [t.lstrip('@') for t in (tags or [])]
    
    # Create suite
    suite = TestSuite(
        name=f"Tag Filter: {', '.join(tag_list) if tag_list else 'All Tests'}",
        include_tags=tag_list,
        retry_count=retry,
        stop_on_failure=stop_on_fail,
    )
    
    # Get runner
    runner = SuiteRunner(
        repository=repository,
        confirmation_mode=ConfirmationMode.NONE,  # Auto-run for batch
    )
    
    # Check test cases
    test_cases = runner.get_test_cases(suite)
    
    if not test_cases:
        console.print("[yellow]No test cases found matching criteria.[/yellow]")
        raise typer.Exit(0)
    
    console.print(f"Found [bold]{len(test_cases)}[/bold] test cases to run")
    console.print()
    
    # Progress tracking
    results_table = Table(title="Execution Results")
    results_table.add_column("#", style="dim", width=3)
    results_table.add_column("Test Case")
    results_table.add_column("Status")
    results_table.add_column("Steps")
    results_table.add_column("Time")
    
    sessions = []
    
    def on_case_start(tc, idx, total):
        console.print(f"[{idx+1}/{total}] Running: [cyan]{tc.name}[/cyan]...")
    
    def on_case_complete(tc, session, idx, total):
        sessions.append(session)
        if session:
            status = "[green]PASS[/green]" if session.status == SessionStatus.PASSED else "[red]FAIL[/red]"
            duration = ""
            if session.ended_at and session.started_at:
                duration = f"{(session.ended_at - session.started_at).total_seconds():.1f}s"
            results_table.add_row(
                str(idx + 1),
                tc.name[:30],
                status,
                f"{session.passed_steps}/{session.total_steps}",
                duration,
            )
    
    # Run suite
    try:
        execution = await runner.run_suite(
            suite,
            on_case_start=on_case_start,
            on_case_complete=on_case_complete,
        )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    
    console.print()
    
    # Output based on format
    if output == "json":
        formatter = JSONFormatter()
        print(formatter.format_suite(execution, sessions))
    elif output == "junit":
        formatter = JUnitFormatter()
        print(formatter.format_suite(execution, sessions))
    else:
        # Terminal output
        console.print(results_table)
        console.print()
        
        # Summary
        status_color = "green" if execution.status == "passed" else "red"
        console.print(Panel.fit(
            f"[bold {status_color}]{execution.status.upper()}[/bold {status_color}]\n\n"
            f"Total: {execution.total_cases} | "
            f"[green]Passed: {execution.passed_cases}[/green] | "
            f"[red]Failed: {execution.failed_cases}[/red] | "
            f"Skipped: {execution.skipped_cases}\n"
            f"Pass Rate: [bold]{execution.pass_rate:.1f}%[/bold] | "
            f"Duration: {execution.duration_seconds:.1f}s",
            title="Summary",
        ))
    
    # Generate HTML report
    if generate_report:
        generator = HTMLReportGenerator()
        tc_map = {tc.id: tc for tc in test_cases}
        report_path = generator.generate_suite_report(execution, sessions, tc_map)
        console.print(f"\n[green]Report generated:[/green] {report_path}")
    
    # Exit code based on result
    if execution.failed_cases > 0:
        raise typer.Exit(1)


@app.command()
def smoke():
    """Quick smoke test - run all tests tagged with @smoke.
    
    Equivalent to: playwrights-pen run-suite @smoke
    """
    asyncio.run(_run_suite(["smoke"], 0, False, "terminal", False))


@app.command()
def report(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to include"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate HTML report from recent executions.
    
    Example:
        playwrights-pen report --days 7
    """
    from .core.result_formatter import HTMLReportGenerator
    from .models.suite import SuiteExecution
    from datetime import datetime, timedelta
    
    console.print("[cyan]Generating report...[/cyan]")
    
    # Get recent sessions
    sessions = repository.list_sessions()
    
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        raise typer.Exit(0)
    
    # Filter by date
    cutoff = datetime.now() - timedelta(days=days)
    recent_sessions = [s for s in sessions if s.started_at and s.started_at > cutoff]
    
    if not recent_sessions:
        console.print(f"[yellow]No sessions in the last {days} days.[/yellow]")
        raise typer.Exit(0)
    
    # Create pseudo suite execution for report
    passed = sum(1 for s in recent_sessions if s.status == SessionStatus.PASSED)
    failed = sum(1 for s in recent_sessions if s.status == SessionStatus.FAILED)
    
    execution = SuiteExecution(
        suite_id="report",
        suite_name=f"Last {days} Days Report",
        total_cases=len(recent_sessions),
        passed_cases=passed,
        failed_cases=failed,
        status="passed" if failed == 0 else "failed",
    )
    execution.started_at = min(s.started_at for s in recent_sessions if s.started_at)
    execution.ended_at = datetime.now()
    
    # Generate report
    generator = HTMLReportGenerator()
    tc_map = {tc.id: tc for tc in repository.list_testcases()}
    report_path = generator.generate_suite_report(execution, recent_sessions, tc_map)
    
    console.print(f"[green]Report generated:[/green] {report_path}")
    console.print(f"  Total: {len(recent_sessions)} | Passed: {passed} | Failed: {failed}")


if __name__ == "__main__":
    app()

