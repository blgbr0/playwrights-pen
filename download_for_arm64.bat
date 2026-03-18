@echo off
REM Create the directory if it doesn't exist
if not exist py_pkgs mkdir py_pkgs
cd py_pkgs

echo ========================================================
echo Downloading Playwright and Pytest for Linux ARM64 (Python 3.8.2)
echo Target Platform: manylinux2014_aarch64
echo ========================================================

REM pip download command for cross-platform download
REM --platform: Specifies the target platform (Linux ARM64)
REM --only-binary=:all:: Ensures we download wheels, not source tarballs (which require compilation)
REM --python-version 3.11: Downloads packages compatible with Python 3.11 (Adjust if your target uses a different version)
REM --implementation cp: CPython implementation
REM --abi cp311: CPython 3.11 ABI

"C:\ProgramData\miniconda3\python.exe" -m pip download playwright pytest ^
    --platform manylinux2014_aarch64 ^
    --only-binary=:all: ^
    --python-version 3.8 ^
    --implementation cp ^
    --abi cp38

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Download failed! Please check if pip is installed and you have internet access.
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Packages downloaded to py_pkgs directory.
echo You can now copy this 'py_pkgs' folder to your offline Linux ARM64 machine.
pause
