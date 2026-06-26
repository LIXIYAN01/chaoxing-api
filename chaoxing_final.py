"""
学习通作业检查 - 生产版
登录 -> 获取课程列表(含已结束课程) -> 每门课程提取作业(名称+状态) -> 输出报告
"""

import requests, base64, json, time, re, sys, os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ==================== 编码处理 ====================
# Windows终端下UTF-8中文可能乱码，所有关键输出写入文件而非依赖print
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def safe_print(*args, **kwargs):
    """安全打印：编码失败时静默跳过（数据已写入文件，用Read工具查看）"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            print(*(str(a).encode('utf-8', errors='replace').decode('utf-8') for a in args), **kwargs)
        except Exception:
            pass

# ==================== 配置 ====================
# 优先从环境变量读取，否则使用默认值（请修改为你的账号）
PHONE = os.environ.get("CHAOXING_PHONE", "你的手机号")
PASSWORD = os.environ.get("CHAOXING_PASSWORD", "你的密码")
AES_KEY = "u2oh6Vu^HWe4_AES"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

def encrypt_aes(msg):
    key = AES_KEY.encode('utf-8')
    cipher = AES.new(key, AES.MODE_CBC, key)
    return base64.b64encode(cipher.encrypt(pad(msg.encode(), AES.block_size))).decode()


def login():
    """AES-CBC 登录学习通"""
    safe_print("=" * 60)
    safe_print("登录学习通...")
    session.get(
        "https://passport2.chaoxing.com/login?loginType=1&fid=-1"
        "&refer=http%3A%2F%2Fi.chaoxing.com", timeout=10)
    resp = session.post("http://passport2.chaoxing.com/fanyalogin", data={
        "fid": "-1",
        "uname": encrypt_aes(PHONE),
        "password": encrypt_aes(PASSWORD),
        "refer": "http%3A%2F%2Fi.chaoxing.com",
        "t": "true",
        "forbidotherlogin": "0",
    }, timeout=15)
    result = resp.json()
    if not result.get("status"):
        safe_print(f"登录失败: {result.get('msg2', result)}")
        return False
    safe_print(f"登录成功! UID={session.cookies.get('_uid')}")
    return True


def get_courses():
    """从 mooc2-ans 获取所有课程列表（含进行中和已结束课程）"""
    safe_print("\n获取课程列表...")
    url = (
        f"http://mooc2-ans.chaoxing.com/visit/courses/list?"
        f"v={int(time.time()*1000)}&rss=1&start=0&size=500"
    )
    r = session.get(url, timeout=15)

    # ✅ 结构化正则：一条正则同时提取链接和对应课程名
    # 避免分别匹配title属性导致映射错乱（页面中有大量非课程名的title）
    pattern = r'<a[^>]*href="(https?://[^"]*stucoursemiddle[^"]+)"[^>]*>.*?<span[^>]*title="([^"]+)"[^>]*>'
    matches = re.findall(pattern, r.text, re.S)

    courses = []
    for link, name in matches:
        cid_m = re.search(r'courseid=(\d+)', link)
        clid_m = re.search(r'clazzid=(\d+)', link)
        courses.append({
            "url": link,
            "courseId": cid_m.group(1) if cid_m else None,
            "classId": clid_m.group(1) if clid_m else None,
            "name": name,
        })

    # 保存课程列表到文件（避免终端编码问题影响查看）
    name_file = os.path.join(OUTPUT_DIR, "_course_list.txt")
    with open(name_file, "w", encoding="utf-8") as f:
        for i, c in enumerate(courses):
            f.write(f"[{i+1}] {c['name']} (ID:{c.get('courseId','')})\n")

    safe_print(f"共 {len(courses)} 门课程（含已结束，已保存至 _course_list.txt）")
    return courses


def get_homework_for_course(course):
    """
    进入一门课程的作业页面，提取作业列表
    返回: list of dict {name, status}
    """
    url = course["url"]
    try:
        cr = session.get(url, timeout=20, allow_redirects=True)
    except Exception:
        return []

    html = cr.text

    # 提取必要参数
    cid = re.search(r'name="courseid"[^v]*value="(\d+)"', html)
    clid = re.search(r'name="clazzid"[^v]*value="(\d+)"', html)
    enc = re.search(r'name="workEnc"[^v]*value="([^"]+)"', html)
    wurl = re.search(r'title="作业"[^>]*data-url="([^"]+)"', html)

    if not all([cid, clid, enc, wurl]):
        # 尝试备用字段名
        if not cid:
            cid = re.search(r'id="courseId"[^v]*value="(\d+)"', html)
        if not clid:
            clid = re.search(r'id="classId"[^v]*value="(\d+)"', html)
        if not enc:
            enc = re.search(r'id="enc"[^v]*value="([^"]+)"', html)

    if not all([cid, clid, enc, wurl]):
        return []

    hw_url = f"{wurl.group(1)}?courseId={cid.group(1)}&classId={clid.group(1)}&enc={enc.group(1)}"
    try:
        hr = session.get(hw_url, timeout=15, headers={
            "Referer": url,
            "X-Requested-With": "XMLHttpRequest",
        })
    except Exception:
        return []

    htext = hr.text

    # 解析 HTML 结构:
    # <li ... aria-label="作业名 ; 状态">
    #   <p class="overHidden2 fl">作业名</p>
    #   <p class="status fl">状态</p>
    # </li>
    homeworks = []
    li_blocks = re.findall(
        r'<li[^>]*aria-label="([^"]*)"[^>]*>(.*?)</li>',
        htext, re.S
    )

    for aria_label, content in li_blocks:
        # 从 aria-label 提取名称和状态
        if ";" in aria_label:
            parts = aria_label.split(";")
            name = parts[0].strip()
            status = parts[1].strip() if len(parts) > 1 else ""
        else:
            name = aria_label.strip()
            status = ""

        # 备用：从 <p> 标签提取
        if not name:
            p_name = re.search(r'<p class="overHidden2 fl">([^<]+)</p>', content)
            name = p_name.group(1).strip() if p_name else ""

        if not status:
            p_status = re.search(r'<p class="status fl">([^<]+)</p>', content)
            status = p_status.group(1).strip() if p_status else ""

        if name:
            homeworks.append({
                "name": name,
                "status": status,
                "is_done": any(k in status for k in ["已完成", "已提交"]),
            })

    return homeworks


# ==================== 主流程 ====================
if __name__ == "__main__":
    if not login():
        sys.exit(1)

    courses = get_courses()
    if not courses:
        safe_print("未获取到课程!")
        sys.exit(1)

    # 遍历每门课程获取作业
    safe_print("\n" + "=" * 60)
    safe_print("开始检查作业...")
    safe_print("=" * 60)

    ALL_RESULTS = []  # 所有课程的结果汇总

    for idx, course in enumerate(courses):
        cname = course["name"] or f"Course_{idx+1}"
        cid_val = course["courseId"]
        safe_print(f"\n[{idx+1}/{len(courses)}] {cname} (ID:{cid_val})")

        hws = get_homework_for_course(course)
        done_count = sum(1 for h in hws if h["is_done"])
        total = len(hws)

        course_result = {
            "course_name": cname,
            "course_id": cid_val,
            "total_homeworks": total,
            "done_count": done_count,
            "todo_count": total - done_count,
            "homeworks": hws,
        }
        ALL_RESULTS.append(course_result)

        if total == 0:
            safe_print(f"   无作业数据（可能已结课或非当前学期）")
        elif total == done_count:
            safe_print(f"   全部完成! ({done_count}/{total})")
            for h in hws:
                safe_print(f"     [DONE] {h['name']}")
        else:
            todo_list = [h for h in hws if not h["is_done"]]
            safe_print(f"   !! {done_count}/{total} 完成, "
                  f"{len(todo_list)} 个待做:")
            for h in hws:
                marker = "[TODO]" if not h["is_done"] else "[DONE]"
                safe_print(f"     {marker} {h['name']} ({h['status']})")

        time.sleep(1.2)

    # ==================== 输出最终报告 ====================
    total_hw = sum(c["total_homeworks"] for c in ALL_RESULTS)
    total_done = sum(c["done_count"] for c in ALL_RESULTS)
    total_todo = sum(c["todo_count"] for c in ALL_RESULTS)

    report = []
    report.append("# 学习通作业检查报告\n")
    report.append(f"- 账号: {PHONE}")
    report.append(f"- 检查时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"- 课程总数: {len(ALL_RESULTS)}")
    report.append(f"- 作业总数: {total_hw}, 已完成: {total_done}, 待完成: {total_todo}\n")

    if total_todo > 0:
        report.append("---\n## [!!] 未完成的作业\n")

    for cr in ALL_RESULTS:
        if cr["todo_count"] > 0:
            report.append(f"### {cr['course_name']}\n")
            for h in cr["homeworks"]:
                if not h["is_done"]:
                    report.append(f"- [ ] **{h['name']}** (状态: {h['status']})\n")

    if total_todo == 0:
        report.append("\n✅ **所有作业均已完成！无需操作。**\n")

    report_text = "".join(report)
    safe_print("\n" + "=" * 60)
    safe_print(report_text)
    safe_print("=" * 60)

    # 保存报告
    report_file = os.path.join(OUTPUT_DIR, "homework_report.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_text)

    json_file = os.path.join(OUTPUT_DIR, "homework_data.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(ALL_RESULTS, f, ensure_ascii=False, indent=2)

    safe_print(f"\n报告已保存:")
    safe_print(f"  Markdown: {report_file}")
    safe_print(f"  JSON数据: {json_file}")
