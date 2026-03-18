import sys
import os

print("=== Playwright Offline Environment Debug ===")
print(f"Python Version: {sys.version}")

try:
    import playwright
    print(f"Playwright Module Location: {playwright.__file__}")
    try:
        from importlib.metadata import version
        print(f"Playwright Package Version: {version('playwright')}")
    except Exception as e:
        print(f"Could not check version: {e}")
except ImportError:
    print("[FATAL] Playwright package is NOT installed!")
    sys.exit(1)

# Check for shadowing by file OR directory
current_dir = os.getcwd()
conflict_file = os.path.join(current_dir, "playwright.py")
conflict_dir = os.path.join(current_dir, "playwright")

if os.path.exists(conflict_file):
    print(f"\n[CRITICAL WARNING] Found a FILE named 'playwright.py' in {current_dir}!")
    print("This file overrides the installed library. Please RENAME this file (e.g., to run_test.py).")
    print("This is 99% likely the cause of your error.")

if os.path.exists(conflict_dir):
    print(f"\n[CRITICAL WARNING] Found a FOLDER named 'playwright' in {current_dir}!")
    print("This folder overrides the installed library. Please RENAME this folder.")
    print("This is 99% likely the cause of your error.")

try:
    with sync_playwright() as p:
        print(f"Playwright Object: {p}")
        print("\n[INFO] ALL Available Attributes on 'p':")
        print(dir(p))
        
        if "_electron" in dir(p):
            print("\n[SUCCESS] '_electron' attribute IS present.")
        else:
            print("\n[ERROR] '_electron' attribute is MISSING from the instance.")
            
            # Deep inspection: Check source code
            import inspect
            import playwright.sync_api
            
            src_file = inspect.getfile(playwright.sync_api.Playwright)
            print(f"\n[DEBUG] Inspecting Source File: {src_file}")
            
            try:
                with open(src_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if "_electron" in content:
                        print("[INFO] Found '_electron' string in source code file!")
                        # Print context
                        lines = content.splitlines()
                        for i, line in enumerate(lines):
                            if "_electron" in line and "def" in line:
                                print(f"  Line {i+1}: {line.strip()}")
                    else:
                        print("[FATAL] '_electron' text NOT found in source code file. It seems this architecture's wheel stripped it out.")
            except Exception as read_err:
                print(f"Could not read source file: {read_err}")

except Exception as e:
    print(f"\n[ERROR] Failed to start Playwright: {e}")

print("\n=== End Debug ===")
