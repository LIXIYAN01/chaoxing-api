"""Fetch and analyze Chaoxing JS files for API endpoints"""
import re
from research_tools import ChaoxingSession, RESPONSES_DIR

cx = ChaoxingSession("你的手机号", "你的密码")
cx.login()

js_files = [
    "http://mooc1.chaoxing.com/mooc2-ans/js/ServerHost.js?2020-0923-1630",
    "http://mooc1.chaoxing.com/mooc2-ans/js/contentLoader.js?v=2025-0919-1507",
    "http://mooc1.chaoxing.com/mooc2-ans/js/course-stu.js?v=2026-0410-1447",
    "http://mooc1.chaoxing.com/mooc2-ans/static/js/domain.js",
    "http://mooc1.chaoxing.com/mooc2-ans/js/common.js?v=2023-0606-1826",
]

KEYWORDS = (
    "api", "mooc", "knowl", "chapter", "exam", "work", "discuss",
    "bbs", "forum", "stat", "data", "notic", "ananas", "getPage",
    "loadContent", "card", "video", "resource", "upload", "mycourse",
    "coursedata", "wrongque", "attendance", "signin"
)

for url in js_files:
    resp = cx.session.get(url, timeout=10)
    fname = url.split("/")[-1].split("?")[0]
    text = resp.text
    print(f"--- {fname} ({len(text)} bytes) ---")

    # Save raw file
    (RESPONSES_DIR / f"js_{fname}").write_text(text, encoding="utf-8")

    # Find URLs with keywords
    for kw in KEYWORDS:
        pattern = r'[\'"]([^\'"]*' + kw + r'[^\'"]*)[\'"]'
        for m in re.findall(pattern, text, re.I):
            if len(m) > 3:
                print(f"  [{kw}] {m[:150]}")

    # Find config variables
    for m in re.findall(
        r'(?:var|let|const)\s+(\w*(?:Url|Host|Domain|Path|API|url|host|domain|path|api|root)\w*)\s*=\s*[\'"]([^\'"]+)[\'"]',
        text,
    ):
        print(f"  [CONFIG] {m[0]} = {m[1][:150]}")

    # Direct URL-like strings
    for m in re.findall(r'[\'"](/[^\'"*]+)[\'"]', text):
        if any(kw in m.lower() for kw in KEYWORDS):
            print(f"  [PATH] {m[:150]}")

    print()
