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
            viewport={'width': 1280, 'height': 800} # 固定窗口大小，保证坐标计算准确
        )
        page = context.new_page()
        
        try:
            print("正在打开登录页面...")
            page.goto('https://extranet.neoheberg.fr/login', timeout=60000)
            
            time.sleep(5)
            page.screenshot(path="1_刚打开页面时的状态.png")
            
            print("正在输入账号密码...")
            email_input = page.locator('input[type="email"], input[type="text"]').first
            email_input.wait_for(state="visible", timeout=30000)
            email_input.fill(EMAIL)
            
            page.locator('input[type="password"]').fill(PWD)
            print("已输入账号密码。")
            
            # ================= 终极验证码破解逻辑 =================
            print("等待验证码加载...")
            time.sleep(5) # 给验证码足够的加载时间
            
            try:
                # 获取页面上所有的 iframe
                iframes = page.locator('iframe').all()
                captcha_clicked = False
                
                for iframe in iframes:
                    # 获取 iframe 的物理尺寸和位置
                    box = iframe.bounding_box()
                    
                    # 过滤掉隐藏的跟踪像素，真正的验证码框通常宽度 > 150, 高度 > 40
                    if box and box['width'] > 150 and box['height'] > 40:
                        print(f"🎯 成功锁定验证码组件！物理尺寸: {box['width']}x{box['height']}")
                        
                        # 无论哪家验证码，复选框都在最左边。我们点击 x=30, y=高度的一半
                        click_y = box['height'] / 2
                        iframe.click(position={"x": 30, "y": click_y})
                        
                        print("👆 已点击人机验证左侧区域，等待验证通过 (等待 12 秒)...")
                        time.sleep(12) # 必须等待足够长的时间让它转圈打勾完毕
                        captcha_clicked = True
                        break # 点完就跳出循环
                        
                if not captcha_clicked:
                    print("⚠️ 未能在页面上扫描到符合尺寸的验证码框。")
            except Exception as e:
                print(f"⚠️ 验证码处理出现异常: {e}，尝试继续...")
            # ======================================================

            page.screenshot(path="2_点击登录前(确认是否打勾).png")

            page.get_by_role("button", name="Se connecter").click()
            print("已点击登录按钮，等待跳转...")
            
            try:
                page.wait_for_url(lambda url: "login" not in url, timeout=20000)
                print("页面已成功跳转！")
            except Exception:
                page.screenshot(path="error_登录失败未跳转.png")
                raise Exception("点击登录后页面未能跳转，请检查截图 2 确认验证码是否打勾，或账号密码是否正确！")

            print(f"正在前往容器面板: {VPS_URL}")
            page.goto(VPS_URL, timeout=30000)
            time.sleep(6) 
            
            page.screenshot(path="3_进入VPS面板后.png")

            if page.locator('text="Arrêté"').is_visible():
                print("检测到容器状态为 Arrêté (已关机)，准备执行开机...")
                
                start_btn = page.locator('button:has-text("Démarrer")')
                if start_btn.is_visible():
                    start_btn.click()
                    print("已点击 Démarrer，等待 8 秒确认状态...")
                    
                    time.sleep(8) 
                    
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
