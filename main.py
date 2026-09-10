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

def solve_hcaptcha(page):
    """
    尝试勾选 hCaptcha 复选框，并返回是否成功勾选。
    优先用官方固定的 iframe title 精确定位；失败则回退到坐标点击兜底。
    """
    # 方案一：用 hCaptcha 固定的 iframe title 精确定位（最可靠）
    try:
        checkbox_frame = page.frame_locator(
            'iframe[title="Widget containing checkbox for hCaptcha security challenge"]'
        )
        checkbox = checkbox_frame.locator('#checkbox')
        checkbox.wait_for(state="visible", timeout=15000)
        checkbox.click()
        print("👆 已通过精确定位点击 hCaptcha 复选框，等待验证 (12秒)...")
        time.sleep(12)

        aria_checked = checkbox.get_attribute("aria-checked")
        if aria_checked == "true":
            print("✅ 验证码已成功勾选！")
            return True
        else:
            print(f"⚠️ 复选框 aria-checked = {aria_checked}，可能触发了图片验证挑战，而非简单勾选。")
            return False
    except Exception as e:
        print(f"⚠️ 精确定位 hCaptcha 复选框失败: {e}")

    # 方案二：兜底，遍历所有 iframe，按尺寸猜测并坐标点击
    print("尝试使用备用的坐标点击方案...")
    try:
        page.wait_for_selector('iframe', timeout=10000)
        iframes = page.locator('iframe').all()
        for iframe in iframes:
            box = iframe.bounding_box()
            if box and box['width'] > 150 and box['height'] > 40:
                print(f"🎯 兜底方案锁定验证码组件，物理尺寸: {box['width']}x{box['height']}")
                click_y = box['height'] / 2
                iframe.click(position={"x": 30, "y": click_y})
                print("👆 已点击人机验证左侧区域，等待验证通过 (等待 12 秒)...")
                time.sleep(12)
                return True
        print("⚠️ 兜底方案也未能扫描到符合尺寸的验证码框。")
        return False
    except Exception as e:
        print(f"⚠️ 兜底方案出现异常: {e}")
        return False


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

            # ================= 验证码处理逻辑（已修复） =================
            print("等待验证码加载...")
            time.sleep(5)

            captcha_ok = solve_hcaptcha(page)
            if not captcha_ok:
                print("⚠️ 验证码未确认勾选成功，仍继续尝试点击登录（可能会失败）...")
            # ======================================================

            page.screenshot(path="2_点击登录前(确认是否打勾).png")

            page.get_by_role("button", name="Se connecter").click()
            print("已点击登录按钮，等待跳转...")

            try:
                page.wait_for_url(lambda url: "login" not in url, timeout=20000)
                print("页面已成功跳转！")
            except Exception:
                page.screenshot(path="error_登录失败未跳转.png")
                # 打印当前 URL 和页面上可能的错误提示，方便下次排查
                print(f"当前仍停留的 URL: {page.url}")
                try:
                    body_text = page.locator("body").inner_text()[:500]
                    print(f"页面文本片段: {body_text}")
                except Exception:
                    pass
                if not captcha_ok:
                    raise Exception(
                        "点击登录后页面未能跳转：验证码复选框未确认勾选成功，"
                        "很可能是 hCaptcha 判定当前代理/机器行为为高风险，"
                        "弹出了图片验证挑战（脚本无法自动解答），而非简单勾选。"
                        "请查看截图 error_登录失败未跳转.png 确认。"
                    )
                else:
                    raise Exception(
                        "点击登录后页面未能跳转，验证码已确认勾选成功，"
                        "请检查账号密码是否正确，或网站是否有其他拦截逻辑。"
                    )

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
