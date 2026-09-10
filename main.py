import os
import time
import requests
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get('NEO_EMAIL')
PWD = os.environ.get('NEO_PWD')
VPS_URL = os.environ.get('VPS_PANEL_URL')
TG_TOKEN = os.environ.get('TG_BOT_TOKEN')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID')

def send_telegram_msg(message):
    if TG_TOKEN and TG_CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": TG_CHAT_ID, "text": message}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"TG通知发送失败: {e}")

def run():
    proxy_settings = {"server": "socks5://127.0.0.1:1080"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy=proxy_settings)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800} # 固定窗口大小保证截图完整
        )
        page = context.new_page()
        
        try:
            print("正在打开登录页面...")
            page.goto('https://extranet.neoheberg.fr/login', timeout=60000)
            
            # 等待 5 秒，防止有前置的 Cloudflare 盾
            time.sleep(5)
            page.screenshot(path="1_刚打开页面时的状态.png")
            
            print("正在输入账号密码...")
            email_input = page.locator('input[type="email"], input[type="text"]').first
            email_input.wait_for(state="visible", timeout=30000)
            email_input.fill(EMAIL)
            
            page.locator('input[type="password"]').fill(PWD)
            print("已输入账号密码。")
            
            # --- 优化后的验证码处理逻辑 ---
            print("等待验证码加载...")
            time.sleep(3)
            
            try:
                # 寻找包含 cloudflare 的 iframe
                cf_iframe = page.locator('iframe[src*="cloudflare"]').first
                cf_iframe.wait_for(state="visible", timeout=10000)
                
                # 精确点击 iframe 的偏左侧 (即复选框所在的位置)
                # Cloudflare Turnstile 验证码组件通常是 300x65 大小，x=30, y=30 正好是打勾的位置
                cf_iframe.click(position={"x": 30, "y": 30})
                print("已点击人机验证区域，等待验证通过转圈完成 (10秒)...")
                time.sleep(10) # 必须等待，转圈打勾需要时间
            except Exception as e:
                print(f"验证码点击出现异常: {e}，尝试继续...")

            # 截取点击登录前的状态图，确认是否成功打勾
            page.screenshot(path="2_点击登录前(确认是否打勾).png")

            page.get_by_role("button", name="Se connecter").click()
            print("已点击登录按钮，等待跳转...")
            
            # 优化跳转判断：只要 URL 里不再包含 "login"，就说明跳走登录成功了
            try:
                page.wait_for_url(lambda url: "login" not in url, timeout=20000)
                print("页面已成功跳转！")
            except Exception:
                page.screenshot(path="error_登录失败未跳转.png")
                raise Exception("点击登录后页面未能跳转，可能是验证码未打上勾或账号密码错误！")

            # -----------------------------

            print(f"正在前往容器面板: {VPS_URL}")
            page.goto(VPS_URL, timeout=30000)
            time.sleep(6) # 等待面板数据加载
            
            page.screenshot(path="3_进入VPS面板后.png")

            if page.locator('text="Arrêté"').is_visible():
                print("检测到容器状态为 Arrêté (已关机)，准备执行开机...")
                
                start_btn = page.locator('button:has-text("Démarrer")')
                if start_btn.is_visible():
                    start_btn.click()
                    print("已点击 Démarrer，等待 8 秒确认状态...")
                    
                    time.sleep(8) # 等待开机指令生效
                    
                    page.screenshot(path="4_开机指令执行后的最终状态.png")
                    
                    if not page.locator('text="Arrêté"').is_visible():
                        msg = "✅ 任务完成：NeoHeberg VPS 处于 Arrêté 状态，已成功发送开机指令并启动！"
                        print(msg)
                        send_telegram_msg(msg)
                    else:
                        msg = "⚠️ 警告：已点击开机，但状态仍显示为 Arrêté，请查看截图。"
                        print(msg)
                        send_telegram_msg(msg)
                else:
                    print("未找到 Démarrer 按钮。")
                    page.screenshot(path="error_未找到开机按钮.png")
                    
            else:
                msg = "ℹ️ 容器状态正常(未处于 Arrêté)，不做任何处理，工作流结束。"
                print(msg)
                page.screenshot(path="4_无需开机的最终状态.png")
                send_telegram_msg(msg)

        except Exception as e:
            error_msg = f"❌ 执行过程中出现异常: {str(e)}"
            print(error_msg)
            try:
                page.screenshot(path="error_发生错误时的截图.png", full_page=True)
                print("已保存错误发生瞬间的截图！")
            except:
                pass
            send_telegram_msg(error_msg)
            raise e
        
        finally:
            browser.close()

if __name__ == "__main__":
    run()
