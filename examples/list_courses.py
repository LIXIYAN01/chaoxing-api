#!/usr/bin/env python3
"""课程列表示例 — 获取所有课程及其 courseId/classId"""
import sys
import time
import re
import base64
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

PHONE = "你的手机号"
PASSWORD = "你的密码"
KEY = b"u2oh6Vu^HWe4_AES"
IV = KEY


def aes_encrypt(text: str) -> str:
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    padded = pad(text.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode("utf-8")


session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
})

# 登录
session.get(
    "https://passport2.chaoxing.com/login?loginType=1&newversion=true"
    "&fid=-1&refer=http%3A%2F%2Fi.chaoxing.com"
)
resp = session.post("http://passport2.chaoxing.com/fanyalogin", data={
    "fid": "-1",
    "uname": aes_encrypt(PHONE),
    "password": aes_encrypt(PASSWORD),
    "refer": "http%3A%2F%2Fi.chaoxing.com",
    "t": "true",
    "forbidotherlogin": "0",
})
if not resp.json().get("status"):
    print("登录失败:", resp.json())
    sys.exit(1)

uid = session.cookies.get("_uid")
print(f"登录成功, uid={uid}\n")

# 获取课程列表
ts = int(time.time() * 1000)
resp = session.get(
    f"http://mooc2-ans.chaoxing.com/visit/courses/list"
    f"?v={ts}&rss=1&start=0&size=500"
)
resp.encoding = "utf-8"

links = re.findall(r'href="(https?://[^"]*stucoursemiddle\?[^"]+)"', resp.text)
titles = re.findall(r'title="([^"]+)"', resp.text)

# 去重（同一 courseId 只保留第一个）
seen = set()
for title, link in zip(titles, links):
    courseid = re.search(r"courseid=(\d+)", link).group(1)
    clazzid = re.search(r"clazzid=(\d+)", link).group(1)
    if courseid in seen:
        continue
    seen.add(courseid)
    short_title = title[:50] + "..." if len(title) > 50 else title
    print(f"[{courseid}] {short_title}")
    print(f"       classId={clazzid}")
    print(f"       URL: {link}")
    print()

print(f"共 {len(seen)} 门课程（已去重）")
