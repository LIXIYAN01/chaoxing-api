"""
学习通 - 高级财务会计作业提取脚本
登录 -> 查找课程 -> 获取作业列表 -> 解析每道题的题目+选项+答案+解析 -> 输出表格
"""
import requests, base64, json, time, re, sys, os, csv
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ==================== 配置 ====================
# 优先从环境变量读取，否则使用默认值（请修改为你的账号）
PHONE = os.environ.get("CHAOXING_PHONE", "你的手机号")
PASSWORD = os.environ.get("CHAOXING_PASSWORD", "你的密码")
AES_KEY = "u2oh6Vu^HWe4_AES"
TARGET_COURSE = "高级财务会计"  # 要提取作业的课程名（支持模糊匹配）

def find_target_fuzzy(courses):
    """宽松匹配课程名"""
    # 先精确匹配
    for c in courses:
        if TARGET_COURSE in c.get("name", ""):
            return c, "exact"
    # 关键词匹配
    keywords = ["高级财务", "财务会计", "高级会计", "高级 财务"]
    for c in courses:
        name = c.get("name", "")
        for kw in keywords:
            if kw in name:
                return c, f"keyword({kw})"
    return None, ""
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
    print("=" * 60)
    print("[1/5] 登录学习通...")
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
        print(f"登录失败: {result.get('msg2', result)}")
        return False
    print(f"登录成功! UID={session.cookies.get('_uid')}")
    return True

def get_courses():
    print("\n[2/5] 获取课程列表...")
    url = f"http://mooc2-ans.chaoxing.com/visit/courses/list?v={int(time.time()*1000)}&rss=1&start=0&size=500"
    r = session.get(url, timeout=15)

    # 使用结构化正则，将链接和课程名配对提取
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

    # 保存课程列表到文件（避免终端乱码）
    course_names = [f"[{i+1}] {c['name']} (ID:{c.get('courseId','')})" for i, c in enumerate(courses)]
    with open(os.path.join(OUTPUT_DIR, "_course_list.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(course_names))

    print(f"共 {len(courses)} 门课程（已保存至 _course_list.txt）")
    return courses

def find_target_course(courses):
    c, method = find_target_fuzzy(courses)
    if c:
        print(f"  匹配成功 [{method}]: {c['name']} (ID:{c.get('courseId','')})")
        return c
    return None

def get_homework_list(course):
    """获取一门课程的所有作业条目"""
    print("\n[3/5] 进入课程页面，获取作业列表...")
    url = course["url"]
    cr = session.get(url, timeout=20, allow_redirects=True)
    html = cr.text

    cid = re.search(r'name="courseid"[^v]*value="(\d+)"', html) or \
          re.search(r'id="courseId"[^v]*value="(\d+)"', html)
    clid = re.search(r'name="clazzid"[^v]*value="(\d+)"', html) or \
           re.search(r'id="classId"[^v]*value="(\d+)"', html)
    enc = re.search(r'name="workEnc"[^v]*value="([^"]+)"', html) or \
          re.search(r'id="enc"[^v]*value="([^"]+)"', html)
    wurl = re.search(r'title="作业"[^>]*data-url="([^"]+)"', html)

    if not all([cid, clid, enc, wurl]):
        # Fallback: try finding workEnc and work URL differently
        workEnc_m = re.search(r'id="workEnc"[^v]*value="([^"]+)"', html)
        if workEnc_m:
            enc = workEnc_m
        # Try to find any data-url for work
        wurl2 = re.search(r'data-url="([^"]*/work/list[^"]*)"', html)
        if wurl2:
            wurl = wurl2
        if not all([cid, clid, enc, wurl]):
            print("  无法提取课程参数!")
            print(f"  cid={cid}, clid={clid}, enc={enc}, wurl={wurl}")
            return []

    hw_url = f"{wurl.group(1)}?courseId={cid.group(1)}&classId={clid.group(1)}&enc={enc.group(1)}"
    hr = session.get(hw_url, timeout=15, headers={
        "Referer": url,
        "X-Requested-With": "XMLHttpRequest",
    })
    htext = hr.text

    homeworks = []
    # Parse <li> blocks with data attribute (contains full detail URL)
    li_blocks = re.findall(
        r'<li[^>]*data="([^"]*)"[^>]*aria-label="([^"]*)"[^>]*>',
        htext
    )

    for data_url, aria_label in li_blocks:
        if ";" in aria_label:
            parts = aria_label.split(";")
            name = parts[0].strip()
            status = parts[1].strip()
        else:
            name = aria_label.strip()
            status = ""

        # Extract workId, answerId, enc from data_url
        w_id = re.search(r'workId=(\d+)', data_url)
        a_id = re.search(r'answerId=(\d+)', data_url)
        e_enc = re.search(r'enc=([^&]+)', data_url)

        if name:
            homeworks.append({
                "name": name,
                "status": status,
                "detail_url": data_url,
                "workId": w_id.group(1) if w_id else "",
                "answerId": a_id.group(1) if a_id else "",
                "enc": e_enc.group(1) if e_enc else "",
            })

    # If no li blocks found, try simpler parsing
    if not homeworks:
        simple_blocks = re.findall(
            r'<li[^>]*aria-label="([^"]*)"[^>]*>(.*?)</li>',
            htext, re.S
        )
        for aria_label, content in simple_blocks:
            if ";" in aria_label:
                parts = aria_label.split(";")
                name = parts[0].strip()
                status = parts[1].strip() if len(parts) > 1 else ""
            else:
                name = aria_label.strip()
                status = ""
            if name:
                homeworks.append({
                    "name": name,
                    "status": status,
                    "detail_url": "",
                    "workId": "",
                    "answerId": "",
                    "enc": "",
                })

    print(f"  找到 {len(homeworks)} 个作业")
    for h in homeworks:
        print(f"    - {h['name']} [{h['status']}]")
    return homeworks

def parse_question_detail(html):
    """解析作业详情页，提取每道题的信息"""
    questions = []

    # Find all question blocks - match content from one questionLi opening to the next (or end)
    ques_blocks = re.findall(
        r'<div[^>]*class="[^"]*questionLi[^"]*"[^>]*>([\s\S]*?)(?=<div[^>]*class="[^"]*questionLi[^"]*"|$)',
        html
    )

    for block in ques_blocks:
        q = {}

        # Question type - from span.colorShallow
        type_m = re.search(r'class="[^"]*colorShallow[^"]*"[^>]*>\s*[(（]?([^)）<]*?)[)）]?\s*</span>', block)
        q["type"] = type_m.group(1).strip() if type_m else ""
        # Clean: remove leading/trailing parens and any extra content after comma
        q["type"] = q["type"].strip("()（）")
        # Remove trailing score info like ",5分" but keep the type name
        q["type"] = re.sub(r',\s*\d*\s*分', '', q["type"])

        # Question text - from span.qtContent
        title_m = re.search(
            r'<span[^>]*class="[^"]*qtContent[^"]*"[^>]*>(.*?)</span>',
            block, re.S
        )
        if title_m:
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            # Clean &nbsp; etc
            title = title.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            # Collapse multiple spaces
            title = re.sub(r'\s+', ' ', title).strip()
            q["title"] = title
        else:
            q["title"] = ""

        # Options - ul.mark_letter > li.workTextWrap
        options = []
        opt_blocks = re.findall(
            r'<li[^>]*class="[^"]*workTextWrap[^"]*"[^>]*>(.*?)</li>',
            block, re.S
        )
        for opt in opt_blocks:
            # Strip HTML tags and clean
            opt_text = re.sub(r'<[^>]+>', '', opt).strip()
            opt_text = opt_text.replace('&nbsp;', ' ').replace('&amp;', '&')
            opt_text = re.sub(r'\s+', ' ', opt_text).strip()
            options.append(opt_text)

        q["options"] = options

        # Student answer
        stu_m = re.search(
            r'<span[^>]*class="[^"]*stuAnswerContent[^"]*"[^>]*>(.*?)</span>',
            block, re.S
        )
        if stu_m:
            ans = re.sub(r'<[^>]+>', '', stu_m.group(1)).strip()
            q["student_answer"] = ans
        else:
            q["student_answer"] = ""

        # Correct answer - also check hidden span for full text
        right_m = re.search(
            r'<span[^>]*class="[^"]*rightAnswerContent[^"]*"[^>]*>(.*?)</span>',
            block, re.S
        )
        if right_m:
            q["correct_answer"] = re.sub(r'<[^>]+>', '', right_m.group(1)).strip()
        else:
            q["correct_answer"] = ""

        # Hidden answer text (full option text) - element-invisible-hidden after 正确答案
        hidden_answers = re.findall(
            r'正确答案[^<]*</i><span[^>]*class="[^"]*element-invisible-hidden[^"]*"[^>]*>(.*?)</span>',
            block, re.S
        )
        q["correct_answer_full"] = ""
        if hidden_answers:
            fulls = [re.sub(r'<[^>]+>', '', h).strip().replace('&nbsp;', ' ') for h in hidden_answers]
            q["correct_answer_full"] = "; ".join(fulls)

        # Score
        score_m = re.search(
            r'<div[^>]*class="[^"]*totalScore[^"]*"[^>]*>(.*?)</div>',
            block, re.S
        )
        if score_m:
            q["score"] = re.sub(r'<[^>]+>', '', score_m.group(1)).strip()
        else:
            q["score"] = ""

        # Mark
        mark_m = re.search(
            r'<span[^>]*class="[^"]*marking_(dui|cuo|bandui)[^"]*"[^>]*>',
            block
        )
        q["mark"] = mark_m.group(1) if mark_m else ""

        # Explanation from answer_detail div
        expl_m = re.search(
            r'class="[^"]*answer_detail[^"]*"[^>]*>([\s\S]*?)(?=</div>|$)',
            block
        )
        if expl_m:
            q["explanation"] = re.sub(r'<[^>]+>', '', expl_m.group(1)).strip()
        else:
            q["explanation"] = ""

        if q["title"]:
            questions.append(q)

    return questions

def get_homework_detail(homework):
    """获取单个作业的详情页，解析题目"""
    detail_url = homework.get("detail_url", "")
    if not detail_url:
        print(f"  [SKIP] {homework['name']} - 无详情URL")
        return []

    print(f"\n[4/5] 获取作业详情: {homework['name']}...")

    try:
        resp = session.get(detail_url, timeout=30, headers={
            "Referer": "http://mooc1.chaoxing.com/",
        })
    except Exception as e:
        print(f"  请求失败: {e}")
        return []

    html = resp.text
    print(f"  响应长度: {len(html)} 字节")

    questions = parse_question_detail(html)
    print(f"  解析到 {len(questions)} 道题")

    return questions

def generate_explanation(q):
    """当没有解析时，根据题目、选项、答案自动生成解析"""
    if q.get("explanation"):
        return q["explanation"]

    qtype = q.get("type", "")
    title = q.get("title", "")
    correct = q.get("correct_answer", "").strip()
    options = q.get("options", [])
    correct_full = q.get("correct_answer_full", "")

    if not correct:
        return "（暂无解析）"

    # 如果有隐藏的完整答案文本，直接使用
    if correct_full:
        return f"正确答案为 {correct}。{correct_full}"

    # 判断题
    if "判断" in qtype:
        if "√" in correct or "对" in correct or correct.upper() in ("A", "T", "TRUE"):
            return "该说法正确。"
        elif "×" in correct or "错" in correct or correct.upper() in ("B", "F", "FALSE"):
            return "该说法错误。"

    # 拆分为单个标签
    if "、" in correct or "," in correct:
        labels = [x.strip() for x in correct.replace("、", ",").split(",") if x.strip()]
    else:
        labels = list(correct)

    correct_texts = []
    for label in labels:
        if len(label) == 1 and 'A' <= label.upper() <= 'Z':
            idx = ord(label.upper()) - ord('A')
            if 0 <= idx < len(options):
                # 去掉选项前已有的字母前缀，避免重复
                opt_text = options[idx]
                # 如果选项以"A. "或"A、"开头，去掉前缀
                opt_text = re.sub(r'^[A-Z][.、\s]+', '', opt_text)
                correct_texts.append(opt_text)
            else:
                correct_texts.append(label)
        else:
            correct_texts.append(label)

    if correct_texts:
        return "正确答案为 " + correct + "。即：" + "；".join(correct_texts)

    return f"正确答案为 {correct}。"

# ==================== 主流程 ====================
if __name__ == "__main__":
    if not login():
        sys.exit(1)

    courses = get_courses()
    if not courses:
        print("未获取到课程!")
        sys.exit(1)

    # 查找目标课程
    target = find_target_course(courses)
    if not target:
        print(f"\n未找到包含'{TARGET_COURSE}'的课程!")
        print("可用课程:")
        for c in courses:
            print(f"  - {c['name']}")
        sys.exit(1)

    print(f"\n找到目标课程: {target['name']} (ID:{target['courseId']})")

    # 获取作业列表
    homeworks = get_homework_list(target)
    if not homeworks:
        print("该课程没有作业数据!")
        sys.exit(1)

    # 逐一获取作业详情
    print("\n" + "=" * 60)
    print("[4/5] 逐份获取作业详情...")
    all_data = []

    for idx, hw in enumerate(homeworks):
        print(f"\n--- 作业 [{idx+1}/{len(homeworks)}]: {hw['name']} ---")
        questions = get_homework_detail(hw)
        for q in questions:
            q["assignment_name"] = hw["name"]
            q["assignment_status"] = hw["status"]
            q["explanation"] = generate_explanation(q)
        all_data.extend(questions)
        if questions:
            print(f"  成功提取 {len(questions)} 道题")
            for q in questions[:3]:
                print(f"    Q: {q['title'][:60]}...")
                print(f"    A: {q['correct_answer']}")
        else:
            print(f"  未提取到题目（可能未提交或页面结构不同）")
        time.sleep(1.0)

    # ==================== 输出 ====================
    print("\n" + "=" * 60)
    print("[5/5] 生成表格...")
    print(f"共提取 {len(all_data)} 道题目")

    # 1. 保存 JSON
    json_file = os.path.join(OUTPUT_DIR, "高级财务会计_作业.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"JSON: {json_file}")

    # 2. 保存 CSV
    csv_file = os.path.join(OUTPUT_DIR, "高级财务会计_作业.csv")
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["序号", "所属作业", "题型", "题目", "选项", "正确答案", "我的答案", "得分", "解析"])
        for i, q in enumerate(all_data, 1):
            opts = "\n".join(q.get("options", []))
            writer.writerow([
                i,
                q.get("assignment_name", ""),
                q.get("type", ""),
                q.get("title", ""),
                opts,
                q.get("correct_answer", ""),
                q.get("student_answer", ""),
                q.get("score", ""),
                q.get("explanation", ""),
            ])
    print(f"CSV: {csv_file}")

    # 3. 生成 Markdown 表格
    md_file = os.path.join(OUTPUT_DIR, "高级财务会计_作业.md")
    md_lines = []
    md_lines.append(f"# 高级财务会计 - 作业汇总\n")
    md_lines.append(f"- 课程: {target['name']}")
    md_lines.append(f"- 提取时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    md_lines.append(f"- 共 {len(homeworks)} 份作业, {len(all_data)} 道题\n")

    for hw in homeworks:
        hw_questions = [q for q in all_data if q.get("assignment_name") == hw["name"]]
        md_lines.append(f"## {hw['name']}（状态: {hw['status']}）\n")
        if not hw_questions:
            md_lines.append("*无题目数据*\n")
            continue

        for j, q in enumerate(hw_questions, 1):
            md_lines.append(f"### 第{j}题（{q.get('type', '')}）\n")
            md_lines.append(f"**题目**: {q.get('title', '')}\n")
            if q.get("options"):
                md_lines.append(f"**选项**:")
                for opt in q["options"]:
                    md_lines.append(f"- {opt}")
                md_lines.append("")
            md_lines.append(f"**正确答案**: {q.get('correct_answer', '')}  ")
            md_lines.append(f"**我的答案**: {q.get('student_answer', '')}  ")
            md_lines.append(f"**得分**: {q.get('score', '')}\n")
            md_lines.append(f"**解析**: {q.get('explanation', '')}\n")
            md_lines.append("---\n")

    with open(md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Markdown: {md_file}")

    print("\n完成!")
