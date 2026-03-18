"""Quick test script: Parse and run Baidu search test."""
import asyncio
import traceback
import sys
import os

# Ensure we run from project root so .env is loaded
os.chdir(os.path.dirname(os.path.abspath(__file__)))
# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

async def main():
    print("=" * 60)
    print("Step 1: Verify config")
    print("=" * 60)
    try:
        from playwrights_pen.config import settings
        print(f"  LLM Model: {settings.llm_model}")
        print(f"  LLM URL:   {settings.llm_base_url}")
        print(f"  API Key:   {settings.llm_api_key[:10]}...")
        print(f"  MCP Cmd:   {settings.mcp_command}")
        print(f"  MCP Args:  {settings.mcp_args}")
        print(f"  Headless:  {settings.browser_headless}")
        print("  [OK] Config loaded")
    except Exception as e:
        print(f"  [FAIL] Config error: {e}")
        traceback.print_exc()
        return

    print()
    print("=" * 60)
    print("Step 2: Parse test case with LLM")
    print("=" * 60)
    try:
        from playwrights_pen.core.parser import TestParser
        parser = TestParser()
        description = "打开百度首页，在搜索框输入Playwright，点击搜索按钮"
        print(f"  Description: {description}")
        print("  Calling LLM to parse...")
        testcase = await parser.create_testcase("百度搜索测试", description)
        print(f"  Parsed {len(testcase.steps)} steps:")
        for i, step in enumerate(testcase.steps, 1):
            print(f"    Step {i}: action={step.action.value}, desc={step.description}, "
                  f"url={step.url}, text={step.text}, hint={step.selector_hint}")
        print("  [OK] Parse successful")
    except Exception as e:
        print(f"  [FAIL] Parse error: {e}")
        traceback.print_exc()
        return

    print()
    print("=" * 60)
    print("Step 3: Connect to MCP and execute")
    print("=" * 60)
    try:
        from playwrights_pen.mcp import MCPClient
        mcp = MCPClient()
        print("  Connecting to MCP server...")
        async with mcp.connect():
            print("  [OK] MCP connected")
            
            # Navigate to Baidu
            print("  Navigating to baidu.com...")
            result = await mcp.navigate("https://www.baidu.com")
            print(f"  Navigate result: {str(result)[:200]}")
            
            # Get snapshot
            print("  Getting snapshot...")
            snapshot = await mcp.get_snapshot()
            print(f"  Snapshot length: {len(snapshot)} chars")
            print(f"  Snapshot preview: {snapshot[:300]}...")
            
            # Try to find search box
            from playwrights_pen.llm import LLMClient
            llm = LLMClient()
            print("  Finding search input element...")
            loc_result = await llm.locate_element(snapshot, "搜索框/搜索输入框")
            print(f"  Locate result: {loc_result}")
            
            if loc_result and loc_result.get("ref"):
                ref = loc_result["ref"]
                print(f"  Typing 'Playwright' into ref={ref}...")
                await mcp.type(ref, "Playwright", element="搜索框", submit=False)
                
                # Get new snapshot and find search button
                await asyncio.sleep(1)
                snapshot2 = await mcp.get_snapshot()
                print("  Finding search button...")
                btn_result = await llm.locate_element(snapshot2, "搜索按钮/百度一下")
                print(f"  Button locate result: {btn_result}")
                
                if btn_result and btn_result.get("ref"):
                    btn_ref = btn_result["ref"]
                    print(f"  Clicking search button ref={btn_ref}...")
                    await mcp.click(btn_ref, element="搜索按钮")
                    
                    await asyncio.sleep(3)
                    
                    # Take screenshot
                    print("  Taking screenshot...")
                    ss_result = await mcp.screenshot()
                    print(f"  Screenshot result: {str(ss_result)[:200]}")
                    
                    # Final snapshot
                    snapshot3 = await mcp.get_snapshot()
                    print(f"  Final snapshot length: {len(snapshot3)} chars")
                    print(f"  Final snapshot preview: {snapshot3[:300]}...")
                    
                    print("  [OK] Test completed!")
                else:
                    print("  [FAIL] Could not find search button")
            else:
                print("  [FAIL] Could not find search input")
    except Exception as e:
        print(f"  [FAIL] MCP execution error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
