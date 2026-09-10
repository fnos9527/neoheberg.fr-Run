import os
import time
import requests
from playwright.sync_api import sync_playwright

EMAIL = os.environ.get("NEO_EMAIL")
PWD = os.environ.get("NEO_PWD")
VPS_URL = os.environ.get("VPS_PANEL_URL")
TG_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")


def send_telegram_msg(message):
    if TG_TOKEN and TG_CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": TG_CHAT_ID, "text": message}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"TG通知发送失败: {e}")


def solve_cap_widget(page):
    """
    处理开源验证码组件 Cap (tiagozip/cap)。
    它不是 iframe，而是一个 <cap-widget> 自定义元素 (Shadow DOM)，
    本质是"工作量证明"验证码——真实浏览器执行 JS 即可自动算出结果，
    不需要任何打码平台。这里用它官方的 solve/error 事件来确认结果，
    而不是靠 sleep 猜时间。
    """
    try:
        widget = page.locator("cap-widget")
        widget.wait_for(state="visible", timeout=20000)
        print("🎯 已定位到 cap-widget 验证组件")

        page.evaluate(
            """
            () => {
                window.__capToken = null;
                window.__capError = null;
                const w = document.querySelector('cap-widget');
                if (w) {
                    w.addEventListener('solve', (e) => { window.__capToken = e.detail.token; });
                    w.addEventListener('error', (e) => { window.__capError = e.detail.message; });
                }
            }
        """
        )

        widget.click(timeout=10000)
        print("👆 已点击 Cap 验证组件，等待其自动完成工作量证明计算...")

        token = None
        for _ in range(25):
            token = page.evaluate("window.__capToken")
            error = page.evaluate("window.__capError")
            if token:
                print("✅ Cap 验证已通过，已成功拿到 token！")
                break
            if error:
                print(f"⚠️ Cap 验证组件返回错误: {error}")
                break
            time.sleep(1)

        return bool(token)
    except Exception as e:
        print(f"⚠️ 处理 Cap 验证组件失败: {e}")
        return False


def is_vps_stopped(page):
    """只认状态徽章上的 Arrêté，不要误伤 Arrêter（关机按钮）。"""
    badge = page.get_by_text("Arrêté", exact=True)
    try:
        return badge.count() > 0 and badge.first.is_visible()
    except Exception:
        return False


def run():
    proxy_settings = {"server": "socks5://127.0.0.1:1080"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy=proxy_settings)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            print("正在打开登录页面...")
            page.goto("https://extranet.neoheberg.fr/login", timeout=60000)

            time.sleep(5)
            page.screenshot(path="1_刚打开页面时的状态.png")

            print("正在输入账号密码...")
            email_input = page.locator('input[type="email"], input[type="text"]').first
            email_input.wait_for(state="visible", timeout=30000)
            email_input.fill(EMAIL)

            page.locator('input[type="password"]').fill(PWD)
            print("已输入账号密码。")

            print("等待验证码组件加载...")
            time.sleep(3)

            captcha_ok = solve_cap_widget(page)
            if not captcha_ok:
                print("⚠️ 验证码未确认通过，仍继续尝试点击登录（大概率会失败，便于留存排查截图）...")

            page.screenshot(path="2_点击登录前(确认是否打勾).png")

            page.get_by_role("button", name="Se connecter").click()
            print("已点击登录按钮，等待跳转...")

            try:
                page.wait_for_url(lambda url: "login" not in url, timeout=20000)
                print("页面已成功跳转！")
            except Exception:
                page.screenshot(path="error_登录失败未跳转.png")
                print(f"当前仍停留的 URL: {page.url}")
                try:
                    body_text = page.locator("body").inner_text()[:500]
                    print(f"页面文本片段: {body_text}")
                except Exception:
                    pass
                if not captcha_ok:
                    raise Exception(
                        "点击登录后页面未能跳转：Cap 验证码未能拿到有效 token，"
                        "可能是组件加载较慢、点击位置未命中，或该代理节点的网络环境下 "
                        "WASM/验证请求被拦截。请查看截图 error_登录失败未跳转.png 确认。"
                    )
                else:
                    raise Exception(
                        "点击登录后页面未能跳转，Cap 验证码已确认拿到 token，"
                        "请检查账号密码是否正确，或网站是否有其他拦截逻辑。"
                    )

            print(f"正在前往容器面板: {VPS_URL}")
            page.goto(VPS_URL, timeout=30000)
            time.sleep(6)

            page.screenshot(path="3_进入VPS面板后.png")

            if is_vps_stopped(page):
                print("检测到容器状态为 Arrêté (已关机)，准备执行开机...")

                # 关键修复：用 title 精确定位开机按钮，避开 Redémarrer
                start_btn = page.locator('button[title="Démarrer le VPS"]')
                start_btn.wait_for(state="visible", timeout=15000)

                if start_btn.is_enabled():
                    start_btn.click()
                    print("已点击 Démarrer，等待容器启动（最多 30 秒）...")

                    started = False
                    try:
                        page.get_by_text("Arrêté", exact=True).first.wait_for(
                            state="hidden", timeout=30000
                        )
                        started = True
                    except Exception:
                        started = not is_vps_stopped(page)

                    page.screenshot(path="4_开机指令执行后的最终状态.png")

                    if started:
                        msg = "✅ 任务完成：NeoHeberg VPS 处于 Arrêté 状态，已成功发送开机指令并启动！"
                        print(msg)
                        send_telegram_msg(msg)
                    else:
                        msg = "⚠️ 警告：已点击开机，但状态仍显示为 Arrêté，请查看截图。"
                        print(msg)
                        send_telegram_msg(msg)
                else:
                    print("找到了 Démarrer 按钮，但当前不可点击（disabled）。")
                    page.screenshot(path="error_开机按钮不可点击.png")
                    send_telegram_msg("⚠️ 找到了 Démarrer 按钮，但当前处于 disabled 状态。")
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
            except Exception:
                pass
            send_telegram_msg(error_msg)
            raise e

        finally:
            browser.close()


if __name__ == "__main__":
    run()
