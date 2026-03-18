
import zipfile
import os

whl_path = "py_pkgs/playwright-1.48.0-py3-none-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"
target_file = "playwright/sync_api.py"

print(f"Inspecting {whl_path}...")

try:
    with zipfile.ZipFile(whl_path, 'r') as z:
        # Check if file exists in zip
        # Search for any file with 'electron' in name
        electron_files = [f for f in z.namelist() if "electron" in f.lower()]
        print("\n[INFO] Files with 'electron' in name:")
        for f in electron_files:
            print(f" - {f}")

        # Check _impl/_playwright.py
        target = "playwright/_impl/_playwright.py"
        if target in z.namelist():
            print(f"\nChecking {target}...")
            with z.open(target) as f:
                content = f.read().decode('utf-8')
                if "electron" in content.lower():
                     print(f"[SUCCESS] Found 'electron' in {target}")
                     lines = content.splitlines()
                     for i, line in enumerate(lines):
                         if "electron" in line.lower():
                             print(f"  Line {i+1}: {line.strip()}")
                else:
                    print(f"[FAILURE] 'electron' text NOT found in {target}")
        else:
            with z.open(target_file) as f:
                content = f.read().decode('utf-8')
                if "_electron" in content:
                    print(f"[SUCCESS] Found '_electron' in {target_file}")
                    
                    # Print the context to be sure it's a property/method definition
                    lines = content.splitlines()
                    for i, line in enumerate(lines):
                         if "_electron" in line and ("def" in line or "@property" in line):
                             print(f"  Line {i+1}: {line.strip()}")
                else:
                    print(f"[FAILURE] '_electron' text NOT found in {target_file}")
                    
except FileNotFoundError:
    print(f"[ERROR] Wheel file not found at {whl_path}")
except Exception as e:
    print(f"[ERROR] An error occurred: {e}")
