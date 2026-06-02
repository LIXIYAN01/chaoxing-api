#!/usr/bin/env python3
"""Phase 1: 课程页面解剖 — 提取所有导航入口、隐藏参数、端点"""
import sys
import json
import time
from pathlib import Path
from collections import Counter

from research_tools import (
    ChaoxingSession,
    parse_course_list,
    parse_course_page,
    extract_data_urls,
    extract_hidden_inputs,
    extract_iframes,
    extract_scripts,
    extract_all_urls,
    find_urls_by_pattern,
    url_base,
    save_json,
    safestr,
    CACHE_DIR,
    RESPONSES_DIR,
)

BASE_DIR = Path(__file__).parent
PHONE = "你的手机号"
PASSWORD = "你的密码"

# ============================================================
# 登录
# ============================================================
print("=" * 70)
print("Phase 1: 课程页面解剖")
print("=" * 70)

cx = ChaoxingSession(PHONE, PASSWORD)
if not cx.login():
    print("登录失败!")
    sys.exit(1)

# ============================================================
# 获取课程列表
# ============================================================
print("\n[1] 获取课程列表...")

ts = int(time.time() * 1000)
resp = cx.get(f"http://mooc2-ans.chaoxing.com/visit/courses/list?v={ts}&rss=1&start=0&size=500")
courses_html = resp.text
courses = parse_course_list(courses_html)
save_json(courses, "all_courses.json")
print(f"  共 {len(courses)} 门课程")

# ============================================================
# 选取代表性课程进行深度分析
# ============================================================
print("\n[2] 选取课程进行深度分析...")

# 优先选当前学期的专业课（有作业的那种）
target_keywords = ["高级财务", "财务会计", "经济法", "税务筹划", "应用文", "统计"]
target_course = None
for kw in target_keywords:
    for c in courses:
        if kw in c["title"]:
            target_course = c
            break
    if target_course:
        break

if not target_course:
    target_course = courses[0]

print(f"  选中: {target_course['title']}")

# ============================================================
# Step A: Dump 课程主页
# ============================================================
print(f"\n[3] Dump 课程主页...")
course_url = target_course["url"]
course_html = cx.dump_page(course_url, "01_course_page_full")

# ============================================================
# Step B: 提取所有隐藏字段
# ============================================================
print("\n[4] 提取隐藏字段...")
hidden = extract_hidden_inputs(course_html)
print(f"  发现 {len(hidden)} 个隐藏字段:")
for k, v in hidden.items():
    val_display = safestr(v, 60)
    if "enc" in k.lower():
        print(f"    [ENC]  {k} = {val_display}")
    elif "id" in k.lower():
        print(f"    [ID]   {k} = {v}")
    else:
        print(f"    [MISC] {k} = {val_display}")
save_json(hidden, "01_hidden_fields.json")

# ============================================================
# Step C: 提取所有 data-url
# ============================================================
print("\n[5] 提取所有 data-url...")
data_urls = extract_data_urls(course_html)
print(f"  发现 {len(data_urls)} 个 data-url 元素:")
# 按功能分组
for entry in data_urls:
    du = entry["data_url"]
    title = entry.get("title", entry.get("aria_label", ""))
    # 解码 unicode
    try:
        title_decoded = title.encode().decode("unicode_escape") if "\\u" in title else title
    except Exception:
        title_decoded = title
    path = url_base(du)
    print(f"    [{safestr(title_decoded, 30)}] → {safestr(du, 90)}")
save_json(data_urls, "01_data_urls.json")

# ============================================================
# Step D: 提取 iframe
# ============================================================
print("\n[6] 提取 iframe...")
iframes = extract_iframes(course_html)
print(f"  发现 {len(iframes)} 个 iframe:")
for f in iframes:
    print(f"    src = {safestr(f, 100)}")

# ============================================================
# Step E: 提取 script 块中的 URL
# ============================================================
print("\n[7] 提取 script 中的 URL...")
scripts = extract_scripts(course_html)
# 从 script 中找 URL 模式
script_urls = set()
for u in find_urls_by_pattern(course_html, r'["\']((https?:)?//[^"\']*(?:api|mooc|knowl|exam|work|discuss|bbs|forum|notic|stat|resource|material|upload)[^"\']*)["\']'):
    script_urls.add(u if isinstance(u, str) else u[0])
for u in find_urls_by_pattern(course_html, r'url\s*:\s*["\']([^"\']+)["\']'):
    script_urls.add(u if isinstance(u, str) else u[0])
for u in find_urls_by_pattern(course_html, r'var\s+\w+\s*=\s*["\']([^"\']+)["\']'):
    script_urls.add(u if isinstance(u, str) else u[0])
print(f"  从 script 中发现 {len(script_urls)} 个潜在 API URL:")
for u in sorted(script_urls):
    print(f"    {safestr(u, 110)}")

save_json(list(script_urls), "01_script_urls.json")

# ============================================================
# Step F: 提取所有 URL (分类)
# ============================================================
print("\n[8] 提取所有 URL 并分类...")
all_urls = extract_all_urls(course_html)
print(f"  总计 {len(all_urls)} 个唯一 URL")

# 按域名/路径前缀分类
domain_counter = Counter()
for u in all_urls:
    if "://" in u:
        domain = u.split("://")[1].split("/")[0]
    else:
        domain = u.split("/")[0] if "/" in u else "(relative)"
    domain_counter[domain] += 1

print("\n  域名分布:")
for domain, count in domain_counter.most_common(15):
    print(f"    {domain}: {count} URLs")

# 按功能路径分类
paths = Counter()
for u in all_urls:
    stripped = url_base(u)
    for seg in stripped.split("/"):
        if seg and len(seg) > 1 and not seg.isdigit():
            paths[seg] += 1

print("\n  路径关键词 (Top 20):")
for path, count in paths.most_common(20):
    if count >= 2:
        print(f"    /{path}: {count}")

# ============================================================
# Step G: 构建导航地图
# ============================================================
print("\n[9] 构建导航地图...")
page_info = parse_course_page(course_html)

navigation = page_info["navigation"]
if not navigation:
    # Fallback: 从 data_urls 中找 nav 相关
    for entry in data_urls:
        title = entry.get("title", entry.get("aria_label", ""))
        if title:
            navigation.append({
                "title": title,
                "data_url": entry["data_url"],
            })

print(f"  导航条目: {len(navigation)}")
for nav in navigation:
    t = nav.get("title", "")
    u = nav.get("data_url", "")
    print(f"    [{safestr(t, 30)}] → {safestr(u, 80)}")

# 按功能分类的额外 URL
feature_urls = page_info.get("feature_urls", {})
print(f"\n  按功能分类的 URL:")
for feat, urls in feature_urls.items():
    if urls:
        print(f"    {feat}: {len(urls)} 个")

navigation_map = {
    "course": {
        "title": target_course["title"],
        "courseId": target_course["courseId"],
        "classId": target_course["classId"],
    },
    "hidden_inputs": hidden,
    "navigation": navigation,
    "feature_urls": feature_urls,
    "iframes": iframes,
    "script_urls": list(script_urls),
    "all_urls_by_domain": dict(domain_counter.most_common()),
}

save_json(navigation_map, "01_navigation_map.json")

# ============================================================
# Step H: 分析同一个 courseId 但不同入口的课程（教师名 vs 课程名）
# ============================================================
print("\n[10] 分析同一 courseId 的不同入口...")
cid_groups = {}
for c in courses:
    cid = c["courseId"]
    if cid not in cid_groups:
        cid_groups[cid] = []
    cid_groups[cid].append(c)

dup_count = sum(1 for g in cid_groups.values() if len(g) > 1)
print(f"  存在 {dup_count} 组重复 courseId (教师名+课程名双入口)")
if dup_count > 0:
    print("  示例:")
    sample_count = 0
    for cid, group in cid_groups.items():
        if len(group) > 1 and sample_count < 3:
            for c in group:
                print(f"    - [{c['title']}] courseId={c['courseId']} classId={c['classId']}")
            sample_count += 1

print("\n" + "=" * 70)
print("Phase 1 完成!")
print(f"所有数据已保存到: {CACHE_DIR}")
print("=" * 70)
