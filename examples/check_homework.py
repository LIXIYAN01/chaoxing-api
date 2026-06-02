#!/usr/bin/env python3
"""超星学习通 - 登录并查看作业完成情况"""
import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
import time
import re
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ============================================================
# 账号配置
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
# 创建 Session
# ============================================================
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
})


# ============================================================
# 解析单道题目的 HTML
# ============================================================
def parse_question(q_block: str) -> dict:
    """从一道题的HTML中提取题目信息"""
    info = {
        "type": "",
        "title": "",
        "options": [],
        "my_answer": "",
        "right_answer": "",
        "score": 0.0,
        "is_correct": False,
        "is_wrong": False,
        "is_half": False,
    }

    # 题型
    m = re.search(r'<span[^>]*class="[^"]*colorShallow[^"]*"[^>]*>(\(.*?\))</span>', q_block)
    info["type"] = m.group(1) if m else ""

    # 题目文本
    m = re.search(r'<span[^>]*class="[^"]*qtContent[^"]*"[^>]*>(.*?)</span>', q_block, re.DOTALL)
    info["title"] = m.group(1).strip() if m else ""

    # 选项
    for opt_m in re.finditer(r'<li[^>]*class="[^"]*workTextWrap[^"]*"[^>]*>(.*?)</li>', q_block, re.DOTALL):
        info["options"].append(opt_m.group(1).strip())

    # 我的答案
    m = re.search(r'<span[^>]*class="[^"]*stuAnswerContent[^"]*"[^>]*>(.*?)</span>', q_block)
    info["my_answer"] = m.group(1).strip() if m else ""

    # 正确答案
    m = re.search(r'<span[^>]*class="[^"]*rightAnswerContent[^"]*"[^>]*>(.*?)</span>', q_block)
    info["right_answer"] = m.group(1).strip() if m else ""

    # 得分
    m = re.search(r'<div[^>]*class="[^"]*totalScore[^"]*"[^>]*>([\d.]+)分?</div>', q_block)
    info["score"] = float(m.group(1)) if m else 0.0

    # 对错
    info["is_correct"] = "marking_dui" in q_block
    info["is_wrong"] = "marking_cuo" in q_block
    info["is_half"] = "marking_bandui" in q_block

    return info


# ============================================================
# Step 1: 登录
# ============================================================
print("=" * 60)
print("Step 1: 登录中...")

session.get(
    "https://passport2.chaoxing.com/login?loginType=1&newversion=true&fid=-1"
    "&refer=http%3A%2F%2Fi.chaoxing.com"
)

resp = session.post(
    "http://passport2.chaoxing.com/fanyalogin",
    data={
        "fid": "-1",
        "uname": aes_encrypt(PHONE),
        "password": aes_encrypt(PASSWORD),
        "refer": "http%3A%2F%2Fi.chaoxing.com",
        "t": "true",
        "forbidotherlogin": "0",
    },
)

result = resp.json()
if result.get("status") != True:
    print(f"[FAIL] 登录失败: {result}")
    sys.exit(1)

print(f"[OK] 登录成功! uid={session.cookies.get('_uid', 'N/A')}")

# ============================================================
# Step 2: 获取课程列表
# ============================================================
print("\n" + "=" * 60)
print("Step 2: 获取课程列表...")

ts = int(time.time() * 1000)
courses_url = f"http://mooc2-ans.chaoxing.com/visit/courses/list?v={ts}&rss=1&start=0&size=500"
resp = session.get(courses_url)
resp.encoding = "utf-8"
html = resp.text

links = re.findall(r'href="(https?://[^"]*stucoursemiddle\?[^"]+)"', html)
titles = re.findall(r'title="([^"]+)"', html)

print(f"[OK] 找到 {len(links)} 门课程")

# ============================================================
# Step 3-5: 逐课程获取作业
# ============================================================
print("\n" + "=" * 60)
print("Step 3-5: 获取作业详情...\n")

all_homeworks = []

for i, (title, link) in enumerate(zip(titles, links)):
    short_title = title[:40] + ".." if len(title) > 40 else title
    print(f"--- [{i+1}/{len(links)}] {short_title} ---")

    resp = session.get(link)
    resp.encoding = "utf-8"
    course_html = resp.text

    # 提取隐藏参数
    m_cid = re.search(r'name="courseid"\s+value="(\d+)"', course_html)
    m_clid = re.search(r'name="clazzid"\s+value="(\d+)"', course_html)
    m_wenc = re.search(r'name="workEnc"\s+value="([^"]*)"', course_html)

    if not m_cid or not m_clid:
        print("  [SKIP] 无法获取课程参数")
        continue

    cid = m_cid.group(1)
    clid = m_clid.group(1)
    wenc = m_wenc.group(1) if m_wenc else ""

    if not wenc:
        print(f"  [SKIP] 无 workEnc")
        continue

    # 找作业 data-url
    # title="作业" = "作业"
    work_url_match = re.search(
        r'title="\\u4f5c\\u4e1a"[^>]*data-url="([^"]+)"', course_html
    )
    if not work_url_match:
        work_url_match = re.search(r'title="作业"[^>]*data-url="([^"]+)"', course_html)
    if not work_url_match:
        work_url_match = re.search(r'data-url="([^"]*work[^"]*)"', course_html)

    if not work_url_match:
        print("  [SKIP] 找不到作业入口 URL")
        continue

    data_url = work_url_match.group(1)

    # 请求作业列表
    work_list_url = f"{data_url}?courseId={cid}&classId={clid}&enc={wenc}"
    session.headers["X-Requested-With"] = "XMLHttpRequest"
    resp = session.get(work_list_url)
    resp.encoding = "utf-8"
    work_html = resp.text

    # 解析作业项
    work_items = re.findall(
        r'<li[^>]*data="([^"]+)"[^>]*aria-label="([^"]*)"',
        work_html,
    )

    if not work_items:
        print("  [INFO] 该课程暂无作业")
        continue

    for j, (w_data_url, aria_label) in enumerate(work_items):
        parts = aria_label.replace("&nbsp;", "").split(";")
        hw_name = parts[0].strip() if parts else "未知作业"
        status = parts[1].strip() if len(parts) > 1 else "未知"

        wid = ""
        aid = ""
        m = re.search(r"workId=(\d+)", w_data_url)
        if m:
            wid = m.group(1)
        m = re.search(r"answerId=(\d+)", w_data_url)
        if m:
            aid = m.group(1)

        status_tag = {
            "已完成": "[DONE]",
            "未交": "[TODO]",
            "未完成": "[TODO]",
        }.get(status, "[???]")

        print(f"  {status_tag} {hw_name} | workId={wid} | answerId={aid or '(未提交)'}")

        # 获取已提交作业的详情
        if aid:
            resp = session.get(w_data_url)
            resp.encoding = "utf-8"
            detail_html = resp.text

            # 按 questionLi 切割题目
            q_blocks = re.split(
                r'(?=<div class="questionLi[^"]*")',
                detail_html,
            )
            q_blocks = [b for b in q_blocks if 'questionLi' in b]

            if not q_blocks:
                print(f"    [WARN] 解析题目失败")
                continue

            total_score = 0
            correct = 0
            wrong = 0
            half = 0

            for bi, block in enumerate(q_blocks):
                qi = parse_question(block)
                total_score += qi["score"]
                if qi["is_correct"]:
                    correct += 1
                elif qi["is_wrong"]:
                    wrong += 1
                elif qi["is_half"]:
                    half += 1

                # 只展示前3道题的详情
                if bi < 3:
                    ans_tag = (
                        "[对]" if qi["is_correct"]
                        else "[错]" if qi["is_wrong"]
                        else "[半对]" if qi["is_half"]
                        else "[-]"
                    )
                    title_short = qi["title"][:60] if qi["title"] else "(空)"
                    print(f"     {ans_tag} Q{bi+1} {qi['type']}: {title_short}")
                    print(f"         我的: {qi['my_answer'] or '-'}  正确: {qi['right_answer'] or '-'}  ({qi['score']}分)")

            total_q = len(q_blocks)
            print(f"     >> 共{total_q}题 | 对{correct} | 错{wrong} | 半对{half} | 总分{total_score}")

        all_homeworks.append({
            "course": title,
            "name": hw_name,
            "status": status,
            "workId": wid,
            "answerId": aid,
        })

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
print("作业总览")
print("=" * 60)

for hw in all_homeworks:
    tag = "[DONE]" if "完成" in hw["status"] else "[TODO]"
    short_course = hw["course"][:35] + ".." if len(hw["course"]) > 35 else hw["course"]
    print(f"  {tag} [{hw['status']}] {short_course}")
    print(f"       -> {hw['name']}")

print(f"\n共 {len(all_homeworks)} 项作业")
print(f"  已完成: {len([h for h in all_homeworks if '完成' in h['status']])}")
print(f"  未完成: {len([h for h in all_homeworks if '完成' not in h['status']])}")
print("完成!")
