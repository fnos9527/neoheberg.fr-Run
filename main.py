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
            
            # 使用更宽泛的选择器，防止 type="text" 导致找不到
            print("正在输入账号密码...")
            email_input = page.locator('input[type="email"], input[type="text"]').first
            email_input.wait_for(state="visible", timeout=30000)
            email_input.fill(EMAIL)
            
            page.locator('input[type="password"]').fill(PWD)
            print("已输入账号密码。")
            
            print("等待验证码加载...")
            time.sleep(3)
            
            try:
                cf_frame = page.frame_locator('iframe[src*="cloudflare"]')
                cf_frame.locator('.cb-tc').click(timeout=5000)
                print("已点击人机验证复选框，等待验证通过...")
                time.sleep(8) # 多等一会，让勾选动画转完
            except Exception:
                print("未检测到标准验证码 iframe，可能被自动跳过，继续执行。")

            # 【要求1】点击登录前，截取验证是否打勾的图
            page.screenshot(path="2_点击登录前(确认是否打勾).png")

            page.get_by_role("button", name="Se connecter").click()
            print("已点击登录按钮，等待跳转...")
            
            # 等待跳转完成
            page.wait_for_url('**/dashboard**', timeout=20000)
            print("登录成功！")

            print(f"正在跳转至容器面板: {VPS_URL}")
            page.goto(VPS_URL, timeout=30000)
            time.sleep(6) # 等待面板数据加载
            
            # 【要求2】截取跳转到第二页面的图
            page.screenshot(path="3_进入VPS面板后.png")

            if page.locator('text="Arrêté"').is_visible():
                print("检测到容器状态为 Arrêté (已关机)，准备执行开机...")
                
                start_btn = page.locator('button:has-text("Démarrer")')
                if start_btn.is_visible():
                    start_btn.click()
                    print("已点击 Démarrer，等待 5-8 秒确认状态...")
                    
                    time.sleep(8) # 等待开机指令生效
                    
                    # 【要求3】截取点击开机后的最终状态图
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
                    
            else:
                msg = "ℹ️ 容器状态正常(未处于 Arrêté)，不做任何处理，工作流结束。"
                print(msg)
                page.screenshot(path="4_无需开机的最终状态.png")
                send_telegram_msg(msg)

        except Exception as e:
            error_msg = f"❌ 执行过程中出现异常: {str(e)}"
            print(error_msg)
            # 【发生错误时截图】记录死亡瞬间
            try:
                page.screenshot(path="error_发生错误时的截图.png", full_page=True)
                print("已保存错误发生瞬间的截图！")
            except:
                pass
            send_telegram_msg(error_msg)
            raise e # 抛出异常让 Actions 显示红叉
        
        finally:
            browser.close()

if __name__ == "__main__":
    run()
