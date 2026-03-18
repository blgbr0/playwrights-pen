# Playwright 离线安装指南 (Linux ARM64)

本指南将帮助你在有网的 Windows 电脑上下载包，并转移到无网的 ARM64 Linux 设备上安装。

## 第一步：在有网的电脑上下载 (Windows)

1.  **准备环境**：确保你的 Windows 电脑上已经安装了 Python（最好是 3.x 版本，版本号需注意）。
    > **⚠️ 重要提示**：请确认你的**目标设备 (Linux ARM64)** 上的 Python 版本是多少？
    > - 如果是 Python 3.11，脚本里的设置不需要改。
    > - over如果是其他版本（如 3.8, 3.9, 3.10），你需要右键编辑 `download_for_arm64.bat`，把 `--python-version 3.11` 改成对应的版本（如 `3.9`），同时把 `--abi cp311` 改成对应的（如 `cp39`）。

2.  **运行脚本**：
    - 在文件夹中找到 `download_for_arm64.bat`。
    - **双击运行**该文件。
    - **如果出现 'pip 不是内部或外部命令' 错误**：
      请在 PyCharm 中打开该项目，点击底部的 "Terminal" (终端) 标签页，然后输入 `.\download_for_arm64.bat` 运行。
      (因为 PyCharm 的终端会自动加载你的 Python 环境)
    - 等待运行结束。成功后你会看到提示 `[SUCCESS]`。
    - 此时你会发现当前目录下多了一个文件夹 `py_pkgs`，里面装满了 `.whl` 文件。

## 第二步：打包与传输

1.  **打包**：
    - 直接把 `py_pkgs` 整个文件夹复制到U盘里。
    - 或者右键 `py_pkgs` 文件夹 -> 发送到 -> 压缩(zipped)文件夹，生成一个 `py_pkgs.zip`，然后拷走。

2.  **传输**：
    - 将U盘插入你的离线 Linux ARM64 设备。
    - 把文件复制到 Linux 机器的某个目录，例如 `~/downloads/`。

## 第三步：在离线设备上安装 (Linux ARM64)

1.  **解压（如果是压缩包）**：
    打开终端 (Terminal)，进入你存放文件的目录：
    ```bash
    cd ~/downloads
    unzip py_pkgs.zip
    # 或者直接 cd 进入你复制过来的文件夹
    cd py_pkgs
    ```

2.  **离线安装**：
    在终端中运行以下命令（确保你在 `py_pkgs` 文件夹内）：
    ```bash
    # 使用当前文件夹(.)作为源进行安装
    pip install --no-index --find-links=. playwright pytest
    ```

3.  **验证安装**：
    ```bash
    pip list | grep playwright
    # 应该能看到 playwright 的版本号
    ```

## 第四步：编写测试脚本

在 Linux 设备上创建一个 Python 文件（例如 `test_app.py`），内容如下。
在 Linux 设备上创建一个 Python 文件（例如 `test_app.py`），内容如下。
**注意：由于 ARM64 离线包限制，我们采用“手动启动 + CDP 连接”的方式。**

```python
from playwright.sync_api import sync_playwright

# [重要] 启动应用前，请先在终端运行：
# /your/app/executable --remote-debugging-port=9222

def test_offline_app():
    # 鉴于 ARM64 版 Playwright 没有 _electron 属性，我们需要使用 CDP 连接方式
    # 前提：你需要先手动启动应用，并开启调试端口
    # 命令：/path/to/your/app --remote-debugging-port=9222
    
    cdp_endpoint = "http://localhost:9222"
    print(f"正在尝试通过 CDP 连接到: {cdp_endpoint}")
    
    with sync_playwright() as p:
        try:
            # 1. 连接到已运行的应用
            browser = p.chromium.connect_over_cdp(cdp_endpoint)
            
            # 2. 获取上下文和页面
            context = browser.contexts[0]
            # 有时候第一个页面是开发者工具，需要遍历一下找到真正的窗口
            # 这里简单取第一个可见的
            page = context.pages[0]
            
            print(f"✅ 连接成功！当前窗口标题: {page.title()}")
            
            # 3. 截图验证
            screenshot_path = "offline_capture.png"
            page.screenshot(path=screenshot_path)
            print(f"📸 已截图，保存为: {screenshot_path}")
            
            # 你的其他测试逻辑...
            # page.click("text=登录")
            
            # 注意：connect_over_cdp 连接的，close() 通常只是断开连接，不会杀掉应用进程
            browser.close()
            
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print("请确认应用是否已通过 --remote-debugging-port=9222 启动。")

if __name__ == "__main__":
    test_offline_app()
```

运行测试：
```bash
python3 test_app.py
```

## 常见问题排查

### Q: 报错 `AttributeError: 'Playwright' object has no attribute '_electron'`?
**可能原因 1 (最常见)**：你的文件名叫 `playwright.py`。
- 这会导致 Python 导入你自己而不是库。
- **解决方法**：把你的脚本改名为 `my_test.py` 或 `run_electron.py`，**千万不要**叫 `playwright.py`。

**可能原因 2**：安装了错误的版本或旧版本。
- 请运行命令 `pip list` 检查版本，确保是 1.8.0 以上（离线包通常是最新版 1.48+）。
- 运行我提供的 `debug_offline.py` 来检测环境。
