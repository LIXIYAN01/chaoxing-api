#!/usr/bin/env python3
"""超星学习通 API 研究工具集"""
import os
import json
import time
import pickle
import hashlib
import re
import base64
from pathlib import Path

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache"
RESPONSES_DIR = CACHE_DIR / "responses"
COOKIE_FILE = CACHE_DIR / "cookies.pkl"

# ============================================================
# AES 加密
# ============================================================
KEY = b"u2oh6Vu^HWe4_AES"
IV = KEY


def aes_encrypt(text: str) -> str:
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    padded = pad(text.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode("utf-8")


# ============================================================
# ChaoxingSession
# ============================================================
class ChaoxingSession:
    """学习通会话管理器：登录 + Cookie 持久化 + 缓存"""

    def __init__(self, phone: str, password: str):
        self.phone = phone
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })
        self._uid = None

    def login(self, force: bool = False) -> bool:
        """登录，优先使用缓存 Cookie"""
        if not force and COOKIE_FILE.exists():
            try:
                with open(COOKIE_FILE, "rb") as f:
                    cookies = pickle.load(f)
                self.session.cookies.update(cookies)
                # 验证 Cookie 有效性
                test_resp = self.session.get(
                    "http://mooc2-ans.chaoxing.com/visit/courses/list?v="
                    f"{int(time.time()*1000)}&rss=1&start=0&size=1"
                )
                if "课程" in test_resp.text or "stucoursemiddle" in test_resp.text:
                    self._uid = self.session.cookies.get("_uid", "unknown")
                    print(f"[Session] Cookie 缓存有效, uid={self._uid}")
                    return True
                print("[Session] Cookie 已过期，重新登录...")
            except Exception as e:
                print(f"[Session] Cookie 读取失败: {e}")

        # AES 加密登录
        self.session.get(
            "https://passport2.chaoxing.com/login?loginType=1&newversion=true"
            "&fid=-1&refer=http%3A%2F%2Fi.chaoxing.com"
        )

        resp = self.session.post(
            "http://passport2.chaoxing.com/fanyalogin",
            data={
                "fid": "-1",
                "uname": aes_encrypt(self.phone),
                "password": aes_encrypt(self.password),
                "refer": "http%3A%2F%2Fi.chaoxing.com",
                "t": "true",
                "forbidotherlogin": "0",
            },
        )

        result = resp.json()
        if result.get("status") != True:
            print(f"[Session] 登录失败: {result}")
            return False

        # 持久化 Cookie
        with open(COOKIE_FILE, "wb") as f:
            pickle.dump(self.session.cookies, f)

        self._uid = self.session.cookies.get("_uid", "unknown")
        print(f"[Session] 登录成功, uid={self._uid}, Cookie 已缓存")
        return True

    def get(self, url: str, **kwargs) -> requests.Response:
        """封装的 GET，自动处理编码"""
        resp = self.session.get(url, **kwargs)
        resp.encoding = "utf-8"
        return resp

    def get_json(self, url: str, **kwargs) -> dict | None:
        """GET 并解析 JSON"""
        resp = self.get(url, **kwargs)
        if resp.status_code != 200:
            print(f"  [WARN] HTTP {resp.status_code} on {url[:80]}")
            return None
        try:
            return resp.json()
        except Exception:
            return None

    def dump_page(self, url: str, name: str, headers: dict = None) -> str:
        """抓取页面并缓存到磁盘，返回响应文本"""
        path = RESPONSES_DIR / f"{name}.html"
        req_headers = headers or {}
        if "X-Requested-With" in req_headers:
            # Temporarily add the header
            old_h = self.session.headers.get("X-Requested-With")
            self.session.headers["X-Requested-With"] = req_headers["X-Requested-With"]
            resp = self.session.get(url)
            if old_h:
                self.session.headers["X-Requested-With"] = old_h
            else:
                del self.session.headers["X-Requested-With"]
        else:
            resp = self.session.get(url)

        resp.encoding = "utf-8"
        path.write_text(resp.text, encoding="utf-8")
        size_kb = len(resp.text) / 1024
        print(f"  [Cache] {name}.html ({size_kb:.1f} KB)")
        return resp.text

    @property
    def uid(self) -> str:
        return self._uid or "unknown"


# ============================================================
# HTML 分析工具
# ============================================================
def extract_hidden_inputs(html: str) -> dict[str, str]:
    """提取所有 <input type="hidden"> 字段"""
    fields = {}
    for m in re.finditer(
        r'<input[^>]*type="hidden"[^>]*'
        r'name="([^"]*)"[^>]*'
        r'value="([^"]*)"[^>]*/?>',
        html,
    ):
        fields[m.group(1)] = m.group(2)
    return fields


def extract_data_urls(html: str) -> list[dict]:
    """提取所有带有 data-url 属性的元素"""
    results = []
    # 匹配任意标签中的 data-url
    for m in re.finditer(
        r'<[^>]*'
        r'data-url="([^"]+)"'
        r'[^>]*'
        r'(?:title="([^"]*)"|aria-label="([^"]*)")?'
        r'[^>]*>',
        html,
    ):
        entry = {"data_url": m.group(1)}
        if m.group(2):
            entry["title"] = m.group(2)
        elif m.group(3):
            entry["aria_label"] = m.group(3)
        # Try to find inner text
        results.append(entry)
    return results


def extract_iframes(html: str) -> list[str]:
    """提取所有 iframe src"""
    return re.findall(r'<iframe[^>]*src="([^"]+)"', html)


def extract_scripts(html: str) -> list[str]:
    """提取所有 script 标签内容"""
    scripts = []
    for m in re.finditer(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
        src = re.search(r'src="([^"]+)"', m.group(0))
        if src:
            scripts.append(f"[external] {src.group(1)}")
        else:
            inner = m.group(1).strip()
            if inner:
                scripts.append(inner[:500])  # 截断
    return scripts


def extract_all_urls(html: str) -> list[str]:
    """提取 HTML 中所有 URL"""
    urls = set()
    # href
    for m in re.finditer(r'href="([^"]+)"', html):
        urls.add(m.group(1))
    # src
    for m in re.finditer(r'src="([^"]+)"', html):
        urls.add(m.group(1))
    # data-url
    for m in re.finditer(r'data-url="([^"]+)"', html):
        urls.add(m.group(1))
    # action
    for m in re.finditer(r'action="([^"]+)"', html):
        urls.add(m.group(1))
    return sorted(urls)


def find_urls_by_pattern(html: str, pattern: str) -> list[str]:
    """按正则模式查找 URL"""
    return list(set(re.findall(pattern, html)))


def analyze_response(resp_text: str) -> dict:
    """分析响应的基本特征"""
    info = {
        "size_kb": len(resp_text) / 1024,
        "is_html_page": bool(re.search(r'<!DOCTYPE\s+html|<html\b', resp_text)),
        "is_html_fragment": False,
        "is_json": False,
        "is_empty": len(resp_text.strip()) < 10,
        "has_iframe": '<iframe' in resp_text.lower(),
        "has_table": '<table' in resp_text.lower(),
        "has_form": '<form' in resp_text.lower(),
        "link_count": len(re.findall(r'href="([^"]+)"', resp_text)),
        "data_url_count": len(re.findall(r'data-url="([^"]+)"', resp_text)),
    }

    if not info["is_html_page"] and not info["is_empty"]:
        info["is_html_fragment"] = bool(
            re.search(r'<(div|ul|li|table|span|a)\b', resp_text)
        )

    try:
        json.loads(resp_text)
        info["is_json"] = True
    except Exception:
        pass

    return info


# ============================================================
# 课程解析
# ============================================================
def parse_course_list(html: str) -> list[dict]:
    """解析课程列表 HTML"""
    courses = []
    links = re.findall(r'href="(https?://[^"]*stucoursemiddle\?[^"]+)"', html)
    titles = re.findall(r'title="([^"]+)"', html)

    for title, link in zip(titles, links):
        courseid = re.search(r"courseid=(\d+)", link)
        clazzid = re.search(r"clazzid=(\d+)", link)

        courses.append({
            "title": title,
            "url": link,
            "courseId": courseid.group(1) if courseid else "",
            "classId": clazzid.group(1) if clazzid else "",
        })
    return courses


def parse_course_page(html: str) -> dict:
    """解析课程主页，提取所有关键信息"""
    info = {
        "hidden_inputs": extract_hidden_inputs(html),
        "data_urls": extract_data_urls(html),
        "iframes": extract_iframes(html),
        "navigation": [],
    }

    # 提取导航 tab（侧边栏）
    nav_patterns = [
        # 标准导航 a 标签
        r'<a[^>]*title="([^"]*)"[^>]*(?:data-url|onclick|href)[^>]*>',
        # li 中的导航项
        r'<li[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>',
    ]

    # 找 sidebar
    sidebar_match = re.search(
        r'<div[^>]*class="[^"]*sider[^"]*"[^>]*>(.*?)</div>\s*<div[^>]*class="[^"]*main',
        html,
        re.DOTALL,
    )
    if sidebar_match:
        sidebar = sidebar_match.group(1)
        tabs = re.findall(r'title="([^"]+)"', sidebar)
        data_urls_in_sidebar = re.findall(r'data-url="([^"]+)"', sidebar)
        for i, tab in enumerate(tabs):
            entry = {"title": tab}
            if i < len(data_urls_in_sidebar):
                entry["data_url"] = data_urls_in_sidebar[i]
            info["navigation"].append(entry)

    # 寻找功能入口 URL 模式
    info["feature_urls"] = {
        "chapters": re.findall(r'data-url="([^"]*knowl[^"]*|chapter[^"]*)"', html, re.I),
        "homework": re.findall(r'data-url="([^"]*work[^"]*)"', html, re.I),
        "exam": re.findall(r'data-url="([^"]*exam[^"]*|test[^"]*)"', html, re.I),
        "resources": re.findall(r'data-url="([^"]*resource[^"]*|material[^"]*)"', html, re.I),
        "discussion": re.findall(r'data-url="([^"]*bbs[^"]*|discuss[^"]*|forum[^"]*)"', html, re.I),
        "notification": re.findall(r'data-url="([^"]*notic[^"]*|notify[^"]*)"', html, re.I),
        "statistics": re.findall(r'data-url="([^"]*stat[^"]*|report[^"]*)"', html, re.I),
    }

    return info


# ============================================================
# 工具函数
# ============================================================
def save_json(data, filename: str):
    """保存 JSON 到 cache 目录"""
    path = CACHE_DIR / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [Save] {filename}")


def load_json(filename: str) -> dict | list | None:
    """从 cache 读取 JSON"""
    path = CACHE_DIR / filename
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def safestr(text, maxlen=80):
    """安全截断字符串用于打印"""
    if not text:
        return "(empty)"
    s = str(text).replace("\n", " ").replace("\r", "")
    if len(s) > maxlen:
        return s[:maxlen] + "..."
    return s


def url_base(url: str) -> str:
    """提取 URL 的基础路径"""
    return re.sub(r"\?.*$", "", url)
