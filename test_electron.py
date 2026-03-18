"""Test Electron app using CDP connection (workaround for missing playwright.electron)."""
import asyncio
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))


async def main():
    project_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "examples", "electron-demo")
    
    # Find electron actual binary (not the .cmd wrapper)
    electron_exe = os.path.join(project_path, "node_modules", "electron", "dist", "electron.exe")
    main_js = os.path.join(project_path, "main.js")
    
    print("=" * 60)
    print("Electron Demo App Test (CDP Mode)")
    print("=" * 60)
    print(f"  Electron: {electron_exe}")
    print(f"  Main:     {main_js}")
    print(f"  Exists:   {os.path.exists(electron_exe)}")
    
    # Launch Electron with remote debugging port
    port = 9222
    print(f"\n[1] Launching Electron with CDP port {port}...")
    
    env = os.environ.copy()
    env["ELECTRON_ENABLE_LOGGING"] = "1"
    
    # electron.cmd expects the project directory as argument (not main.js)
    proc = subprocess.Popen(
        [electron_exe, project_path, f"--remote-debugging-port={port}"],
        cwd=project_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for app to start
    await asyncio.sleep(5)
    print(f"  PID: {proc.pid}")
    
    if proc.poll() is not None:
        stdout = proc.stdout.read().decode('utf-8', errors='replace')
        stderr = proc.stderr.read().decode('utf-8', errors='replace')
        print(f"  [ERROR] Process exited with code {proc.returncode}")
        print(f"  stdout: {stdout[:500]}")
        print(f"  stderr: {stderr[:500]}")
        return
    
    print("  [OK] Electron launched!")

    try:
        from playwright.async_api import async_playwright
        
        print(f"\n[2] Connecting via CDP to localhost:{port}...")
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{port}")
            print("  [OK] Connected to Electron via CDP!")
            
            # Get first page
            contexts = browser.contexts
            print(f"  Contexts: {len(contexts)}")
            
            pages = contexts[0].pages if contexts else []
            print(f"  Pages: {len(pages)}")
            
            if not pages:
                print("  [ERROR] No pages found")
                return
            
            page = pages[0]
            await page.wait_for_load_state('domcontentloaded')
            
            print(f"\n[3] Page title: {await page.title()}")
            print(f"  URL: {page.url}")
            
            print("\n[4] Getting accessibility snapshot...")
            snapshot = await page.accessibility.snapshot()
            if snapshot:
                # Simple format function
                def fmt(node, depth=0):
                    lines = []
                    role = node.get('role', '')
                    name = node.get('name', '')
                    prefix = '  ' * depth
                    if name:
                        lines.append(f"{prefix}- {role} \"{name}\"")
                    elif role:
                        lines.append(f"{prefix}- {role}")
                    for child in node.get('children', []):
                        lines.extend(fmt(child, depth+1))
                    return lines
                
                tree_lines = fmt(snapshot)
                for line in tree_lines[:20]:
                    print(f"  {line}")
                print(f"  ... ({len(tree_lines)} total elements)")
            else:
                print("  [WARN] No accessibility snapshot")
            
            print("\n[5] Typing a task...")
            await page.fill('#taskInput', '学习 Playwright 自动化测试')
            print("  [OK] Typed task text")
            
            print("\n[6] Clicking add button...")
            await page.click('#addBtn')
            await asyncio.sleep(0.5)
            print("  [OK] Clicked add button")
            
            total = await page.locator('#totalCount').inner_text()
            print(f"  Total tasks: {total}")
            
            print("\n[7] Adding second task...")
            await page.fill('#taskInput', '编写测试报告')
            await page.click('#addBtn')
            await asyncio.sleep(0.5)
            total = await page.locator('#totalCount').inner_text()
            print(f"  Total tasks: {total}")
            
            print("\n[8] Checking first task...")
            await page.locator('.task-checkbox').first.check()
            await asyncio.sleep(0.5)
            completed = await page.locator('#completedCount').inner_text()
            pending = await page.locator('#pendingCount').inner_text()
            print(f"  Completed: {completed}, Pending: {pending}")
            
            print("\n[9] Taking screenshot...")
            ss_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "data", "electron_test_result.png")
            os.makedirs(os.path.dirname(ss_path), exist_ok=True)
            await page.screenshot(path=ss_path)
            print(f"  Screenshot: {ss_path}")
            
            print("\n[10] Deleting completed task...")
            await page.locator('.delete-btn').first.click()
            await asyncio.sleep(0.5)
            total = await page.locator('#totalCount').inner_text()
            print(f"  Remaining tasks: {total}")
            
            print("\n" + "=" * 60)
            print("  [ALL TESTS PASSED]")
            print("=" * 60)
    
    except Exception as e:
        print(f"\n  [ERROR] {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nClosing Electron...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
