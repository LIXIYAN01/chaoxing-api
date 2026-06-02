#!/usr/bin/env python3
"""Phase 2: 端点发现 — 请求所有 data-url 并分类"""
import sys
import json
import time
import re
from pathlib import Path

from research_tools import (
    ChaoxingSession,
    parse_course_list,
    extract_data_urls,
    extract_hidden_inputs,
    analyze_response,
    url_base,
    save_json,
    load_json,
    safestr,
    CACHE_DIR,
    RESPONSES_DIR,
)

BASE_DIR = Path(__file__).parent
PHONE = "你的手机号"
PASSWORD = "你的密码"

print("=" * 70)
print("Phase 2: 端点发现与分类")
print("=" * 70)

cx = ChaoxingSession(PHONE, PASSWORD)
if not cx.login():
    print("登录失败!")
    sys.exit(1)

# ============================================================
# 选取一个活跃课程
# ============================================================
all_courses = load_json("all_courses.json")
# 选一个能拿到完整参数的课
target = None
for c in all_courses:
    # 跳过重复的教师名入口
    if len(c["title"]) > 20 and c["courseId"] != "217447956":  # 避开财务管理(重复)
        target = c
        break

if not target:
    target = all_courses[0]

# 获取课程主页参数
print(f"\n使用课程: {target['title']}")
course_html = cx.dump_page(target["url"], "02_course_page")
hidden = extract_hidden_inputs(course_html)

cid = hidden.get("courseid", target["courseId"])
clid = hidden.get("clazzid", target["classId"])
cpi = hidden.get("cpi", "")
enc = hidden.get("enc", "")
work_enc = hidden.get("workEnc", "")
exam_enc = hidden.get("examEnc", "")
openc = hidden.get("openc", "")

print(f"  courseId={cid}, classId={clid}, cpi={cpi}")
print(f"  enc={enc[:20]}...")
print(f"  workEnc={work_enc[:20]}...")
print(f"  examEnc={exam_enc[:20]}...")
print(f"  openc={openc[:20]}...")

# ============================================================
# 端点测试矩阵
# ============================================================
ENDPOINTS = [
    # === 课程主页 ===
    {
        "id": "course_page",
        "name": "课程主页",
        "category": "course",
        "url": target["url"],
        "params": {},
        "headers": {},
    },
    # === 章节/知识点 (已知模式) ===
    {
        "id": "knowledge_cards",
        "name": "章节卡片树",
        "category": "chapters",
        "url": f"http://mooc1.chaoxing.com/knowledge/cards",
        "params": {
            "clazzid": clid,
            "courseid": cid,
            "cpi": cpi,
            "enc": openc,
            "ut": hidden.get("heardUt", "s"),
            "v": "0",
        },
        "headers": {},
    },
    {
        "id": "knowledge_cards_enc",
        "name": "章节卡片树(通用enc)",
        "category": "chapters",
        "url": f"http://mooc1.chaoxing.com/knowledge/cards",
        "params": {
            "clazzid": clid,
            "courseid": cid,
            "cpi": cpi,
            "enc": enc,
            "ut": hidden.get("heardUt", "s"),
            "v": "0",
        },
        "headers": {},
    },
    # === 作业 ===
    {
        "id": "homework_list",
        "name": "作业列表",
        "category": "homework",
        "url": f"http://mooc1.chaoxing.com/mooc2/work/list",
        "params": {
            "courseId": cid,
            "classId": clid,
            "enc": work_enc,
        },
        "headers": {"X-Requested-With": "XMLHttpRequest"},
    },
    # === 考试 ===
    {
        "id": "exam_list",
        "name": "考试列表",
        "category": "exam",
        "url": f"http://mooc1.chaoxing.com/exam-ans/mooc2/exam/exam-list",
        "params": {
            "courseId": cid,
            "classId": clid,
            "enc": exam_enc,
        },
        "headers": {"X-Requested-With": "XMLHttpRequest"},
    },
    # === 讨论 ===
    {
        "id": "discussion_list",
        "name": "讨论区",
        "category": "discussion",
        "url": f"http://groupweb.chaoxing.com/course/topic/topicList",
        "params": {
            "courseId": cid,
            "clazzid": clid,
            "bbsid": hidden.get("bbsid", ""),
            "cpi": cpi,
            "enc": enc,
        },
        "headers": {},
    },
    # === 资料/资源 ===
    {
        "id": "resource_list",
        "name": "资料列表",
        "category": "resources",
        "url": f"http://mooc1.chaoxing.com/mooc2/course/data",
        "params": {
            "courseId": cid,
            "classId": clid,
            "cpi": cpi,
            "enc": enc,
        },
        "headers": {},
    },
    {
        "id": "resource_list2",
        "name": "资料列表(变体)",
        "category": "resources",
        "url": f"http://mooc1.chaoxing.com/course-ans/courseportal/resource",
        "params": {
            "courseId": cid,
            "classId": clid,
        },
        "headers": {},
    },
    # === 课程数据/统计 ===
    {
        "id": "course_data",
        "name": "课程数据",
        "category": "stats",
        "url": f"http://mooc1.chaoxing.com/mooc2-ans/coursedata/stu-datalist",
        "params": {
            "courseId": cid,
            "classId": clid,
            "cpi": cpi,
            "enc": enc,
        },
        "headers": {"X-Requested-With": "XMLHttpRequest"},
    },
    {
        "id": "study_data",
        "name": "学习统计",
        "category": "stats",
        "url": f"http://stat2-ans.chaoxing.com/study-data/index",
        "params": {
            "courseId": cid,
            "classId": clid,
            "cpi": cpi,
        },
        "headers": {},
    },
    {
        "id": "study_knowledge",
        "name": "知识点统计",
        "category": "stats",
        "url": f"http://stat2-ans.chaoxing.com/study-knowledge/index",
        "params": {
            "courseId": cid,
            "classId": clid,
            "cpi": cpi,
        },
        "headers": {},
    },
    # === 错题集 ===
    {
        "id": "wrong_questions",
        "name": "错题集",
        "category": "other",
        "url": f"http://mooc1.chaoxing.com/mooc2-ans/wrongque/page",
        "params": {
            "courseId": cid,
            "classId": clid,
            "cpi": cpi,
            "enc": enc,
        },
        "headers": {"X-Requested-With": "XMLHttpRequest"},
    },
    # === AI 工作台 ===
    {
        "id": "ai_workbench",
        "name": "AI工作台",
        "category": "other",
        "url": f"http://mooc1.chaoxing.com/course-ans/ai/getStuAiWorkBench",
        "params": {
            "courseId": cid,
            "clazzId": clid,
            "cpi": cpi,
            "ut": hidden.get("heardUt", "s"),
        },
        "headers": {"X-Requested-With": "XMLHttpRequest"},
    },
    # === 活动 ===
    {
        "id": "activities",
        "name": "课程活动列表",
        "category": "other",
        "url": f"http://mobilelearn.chaoxing.com/page/active/stuActiveList",
        "params": {
            "courseId": cid,
            "classId": clid,
            "fid": hidden.get("fid", ""),
        },
        "headers": {},
    },
    # === 用户相关 ===
    {
        "id": "user_info",
        "name": "用户信息",
        "category": "user",
        "url": f"http://passport2.chaoxing.com/mooc/account",
        "params": {},
        "headers": {},
    },
    {
        "id": "user_space",
        "name": "个人空间",
        "category": "user",
        "url": f"http://i.chaoxing.com/base",
        "params": {},
        "headers": {},
    },
    # === 视频进度上报 (JSON API) ===
    {
        "id": "video_progress",
        "name": "视频进度(POST测试)",
        "category": "chapters",
        "url": f"http://mooc1.chaoxing.com/ananas/status/get",
        "params": {
            "courseId": cid,
            "classId": clid,
        },
        "headers": {},
    },
    # === 通知 ===
    {
        "id": "notifications",
        "name": "课程通知",
        "category": "notification",
        "url": f"http://mooc1.chaoxing.com/mooc2/notific",
        "params": {
            "courseId": cid,
            "classId": clid,
            "cpi": cpi,
        },
        "headers": {},
    },
    # === 课程评价 ===
    {
        "id": "course_evaluate",
        "name": "课程评价",
        "category": "other",
        "url": hidden.get("courseEvaluateUrl", ""),
        "params": {
            "courseId": cid,
        },
        "headers": {},
    },
    # === 更多常见模式 ===
    {
        "id": "study_record",
        "name": "学习记录",
        "category": "chapters",
        "url": f"http://mooc1.chaoxing.com/visit/study",
        "params": {
            "courseId": cid,
            "classId": clid,
            "cpi": cpi,
            "enc": enc,
        },
        "headers": {},
    },
    {
        "id": "ppt_page",
        "name": "PPT课件",
        "category": "chapters",
        "url": f"http://mooc1.chaoxing.com/knowledge/ppt",
        "params": {
            "courseId": cid,
            "classId": clid,
            "cpi": cpi,
            "enc": enc,
        },
        "headers": {},
    },
    # === 课程班级信息 ===
    {
        "id": "class_info",
        "name": "班级信息",
        "category": "course",
        "url": f"http://mooc1.chaoxing.com/mooc2-ans/class/info",
        "params": {
            "courseId": cid,
            "classId": clid,
            "cpi": cpi,
        },
        "headers": {"X-Requested-With": "XMLHttpRequest"},
    },
    # === 课程门户 ===
    {
        "id": "course_portal",
        "name": "课程门户",
        "category": "course",
        "url": f"http://mooc1.chaoxing.com/course/portal/pOWwag1xr4s9av4a6Y08xQ==",
        "params": {"clazzId": clid},
        "headers": {},
    },
]

# ============================================================
# 测试每个端点
# ============================================================
print(f"\n{'=' * 70}")
print(f"测试 {len(ENDPOINTS)} 个端点...")
print(f"{'=' * 70}")

results = []

for i, ep in enumerate(ENDPOINTS):
    if not ep["url"]:
        results.append({**ep, "status": "SKIPPED", "reason": "no url"})
        continue

    # 构建 URL
    base = ep["url"]
    params = ep["params"]
    url = base
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v)
        url = f"{base}?{qs}"

    # 构建请求头
    req_headers = {}
    if ep["headers"].get("X-Requested-With"):
        cx.session.headers["X-Requested-With"] = ep["headers"]["X-Requested-With"]

    try:
        resp = cx.session.get(url, allow_redirects=True, timeout=15)
    except Exception as e:
        results.append({**ep, "status": "ERROR", "error": str(e)})
        print(f"[{i+1:02d}] ERR  {ep['name']}: {e}")
        if "X-Requested-With" in cx.session.headers:
            del cx.session.headers["X-Requested-With"]
        continue

    if "X-Requested-With" in cx.session.headers:
        del cx.session.headers["X-Requested-With"]

    resp.encoding = "utf-8"
    text = resp.text
    content_type = resp.headers.get("Content-Type", "")
    status_code = resp.status_code

    # 分析响应
    analysis = analyze_response(text)

    # 保存响应
    safe_id = ep["id"].replace("/", "_")
    resp_file = f"02_{safe_id}.html" if analysis["is_html_page"] or analysis["is_html_fragment"] else f"02_{safe_id}.txt"
    try:
        (RESPONSES_DIR / resp_file).write_text(
            text[:500000], encoding="utf-8", errors="replace"
        )
    except Exception:
        pass

    # 分类
    if status_code in (301, 302):
        rtype = "REDIRECT"
    elif analysis["is_json"]:
        rtype = "JSON"
    elif analysis["is_empty"]:
        rtype = "EMPTY"
    elif analysis["is_html_page"]:
        rtype = "HTML_PAGE"
    elif analysis["is_html_fragment"]:
        rtype = "HTML_FRAGMENT"
    else:
        rtype = "UNKNOWN"

    result = {
        **ep,
        "status_code": status_code,
        "response_type": rtype,
        "size_kb": analysis["size_kb"],
        "has_table": analysis["has_table"],
        "has_form": analysis["has_form"],
        "link_count": analysis["link_count"],
        "data_url_count": analysis["data_url_count"],
        "saved_as": resp_file,
        "final_url": resp.url[:200] if resp.url != url else "",
    }
    results.append(result)

    # 打印状态
    icon = {
        "HTML_PAGE": "[PAGE]",
        "HTML_FRAGMENT": "[FRAG]",
        "JSON": "[JSON]",
        "REDIRECT": "[301]",
        "EMPTY": "[EMPT]",
        "ERROR": "[ERR]",
        "UNKNOWN": "[???]",
    }.get(rtype, "[???]")

    print(f"[{i+1:02d}] {icon} {ep['name']:20s} | HTTP{status_code} | {analysis['size_kb']:.0f}KB | {rtype}")

    time.sleep(0.5)  # 温和的延迟避免限流

# ============================================================
# 汇总报告
# ============================================================
print(f"\n{'=' * 70}")
print("分类汇总")
print(f"{'=' * 70}")

type_counts = {}
cat_counts = {}
for r in results:
    rtype = r.get("response_type", "SKIPPED")
    cat = r.get("category", "other")
    type_counts[rtype] = type_counts.get(rtype, 0) + 1
    cat_counts[cat] = cat_counts.get(cat, 0) + 1

print("\n按响应类型:")
for t, c in sorted(type_counts.items()):
    print(f"  {t}: {c}")

print("\n按功能分类:")
for t, c in sorted(cat_counts.items()):
    print(f"  {t}: {c}")

save_json(results, "02_endpoint_catalog.json")

print(f"\nPhase 2 完成! {len(results)} 个端点已分类")
