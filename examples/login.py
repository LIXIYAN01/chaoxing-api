#!/usr/bin/env python3
"""最小登录示例 — 演示 AES-CBC 加密登录学习通"""
import requests
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ============================================================
# 配置
# ============================================================
PHONE = "你的手机号"
PASSWORD = "你的密码"

# ============================================================
# AES-CBC 加密
# ============================================================
KEY = b"u2oh6Vu^HWe4_AES"
IV = KEY


def aes_encrypt(text: str) -> str:
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    padded = pad(text.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode("utf-8")


# ============================================================
# 创建会话并登录
# ============================================================
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
})

# Step 1: 获取初始 Cookie
session.get(
    "https://passport2.chaoxing.com/login?loginType=1&newversion=true"
    "&fid=-1&refer=http%3A%2F%2Fi.chaoxing.com"
)

# Step 2: 加密登录
resp = session.post("http://passport2.chaoxing.com/fanyalogin", data={
    "fid": "-1",
    "uname": aes_encrypt(PHONE),
    "password": aes_encrypt(PASSWORD),
    "refer": "http%3A%2F%2Fi.chaoxing.com",
    "t": "true",
    "forbidotherlogin": "0",
})

result = resp.json()
if result.get("status"):
    uid = session.cookies.get("_uid")
    print(f"登录成功! uid={uid}")
else:
    print(f"登录失败: {result}")
