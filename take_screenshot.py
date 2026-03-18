from playwright.sync_api import sync_playwright

def test_screenshot_robust():
    cdp_url = "http://localhost:9222"
    print(f"Connecting to {cdp_url} ...")
    
    with sync_playwright() as p:
        try:
            # 连接浏览器/Electron
            browser = p.chromium.connect_over_cdp(cdp_url)
            
            if not browser.contexts:
                print("[Error] No browser contexts found.")
                return

            # 遍历所有上下文和页面
            total_pages = 0
            for c_idx, context in enumerate(browser.contexts):
                print(f"\n--- Context {c_idx} ---")
                for p_idx, page in enumerate(context.pages):
                    total_pages += 1
                    title = page.title()
                    url = page.url
                    print(f"Page {p_idx}: Title='{title}' URL='{url}'")
                    
                    # 尝试截图
                    filename = f"screenshot_c{c_idx}_p{p_idx}.png"
                    try:
                        print(f"  Attempting screenshot -> {filename} ...")
                        # 增加超时时间到 60秒，并禁用动画以防卡死
                        page.screenshot(
                            path=filename, 
                            timeout=60000, 
                            animations="disabled"
                        )
                        print(f"  [SUCCESS] Saved.")
                    except Exception as e:
                        print(f"  [FAILED] Screenshot timed out or failed: {e}")
            
            if total_pages == 0:
                print("\n[Warning] No pages found! Is the app window actually open?")

            browser.close()
            
        except Exception as e:
            print(f"[Error] Connection failed: {e}")

if __name__ == "__main__":
    test_screenshot_robust()
