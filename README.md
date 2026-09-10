# neoheberg.fr-Run

NEO_EMAIL

NEO_PWD

VPS_PANEL_URL(容器)

PROXY_URL(代理)

TG_BOT_TOKEN(可选)、TG_CHAT_ID(可选)。

<img width="442" height="110" alt="2026-09-10_21-46" src="https://github.com/user-attachments/assets/95208d79-1832-412e-9713-5c72fededaa2" />

开源的 Cap（tiagozip/cap）——一个基于"工作量证明"（Proof-of-Work）的验证码组件.Cap 用的是 <cap-widget> 自定义元素 + Shadow DOM，提供的 solve 事件确认拿到 token 即可.
用 page.locator('cap-widget') 定位——Playwright 会自动穿透 Shadow DOM
点击前先往页面里注入一段 JS，监听 Cap 组件官方派发的 solve（成功，带 token）和 error（失败，带原因）事件，把结果存到 window.__capToken / window.__capError。
用 Playwright 的真实点击触发验证，然后轮询最多 25 秒等 token 出现——这是判断验证码到底过没过的唯一可靠依据
