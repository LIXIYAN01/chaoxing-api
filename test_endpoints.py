"""Quick endpoint testing"""
import re
from research_tools import ChaoxingSession, RESPONSES_DIR, extract_hidden_inputs, save_json

cx = ChaoxingSession("你的手机号", "你的密码")
cx.login()

# Test with 高级财务会计
resp = cx.get("http://mooc1.chaoxing.com/visit/stucoursemiddle?courseid=249808478&clazzid=139370929")
html = resp.text
RESPONSES_DIR.joinpath("03_gkj_course.html").write_text(html, encoding="utf-8")

# Broader search for hidden inputs
hidden = {}
for m in re.finditer(r'<input[^>]*type\s*=\s*"hidden"[^>]*name\s*=\s*"([^"]+)"[^>]*value\s*=\s*"([^"]*)"', html, re.I):
    hidden[m.group(1)] = m.group(2)
# Also try the other order
for m in re.finditer(r'<input[^>]*name\s*=\s*"([^"]+)"[^>]*type\s*=\s*"hidden"[^>]*value\s*=\s*"([^"]*)"', html, re.I):
    if m.group(1) not in hidden:
        hidden[m.group(1)] = m.group(2)
# Also try id-based
for m in re.finditer(r'id\s*=\s*"(courseId|classId|cpi|enc|workEnc|examEnc)"[^>]*value\s*=\s*"([^"]*)"', html):
    if m.group(1) not in hidden:
        hidden[m.group(1)] = m.group(2)

print(f"Found {len(hidden)} hidden params:")
for k, v in hidden.items():
    print(f"  {k} = {v[:80]}")

cid = hidden.get("courseid", hidden.get("courseId", "249808478"))
clid = hidden.get("clazzid", hidden.get("clazzId", "139370929"))
cpi = hidden.get("cpi", "360821194")
enc = hidden.get("enc", "")
openc = hidden.get("openc", "")

# Now try the known-good pattern for overall score
print("\n=== Testing key endpoints ===")

endpoints = [
    ("Overall Score", f"http://stat2-ans.chaoxing.com/stat2/overall-score/stu-score?courseid={cid}&cpi={cpi}&clazzid={clid}&ut=s"),
    ("Exam List", f"http://mooc1.chaoxing.com/exam-ans/mooc2/exam/exam-list?courseId={cid}&classId={clid}&enc={hidden.get('examEnc','')}"),
    ("Discussion", f"http://groupweb.chaoxing.com/course/topic/topicList?courseId={cid}&clazzid={clid}&bbsid={hidden.get('bbsid','')}&cpi={cpi}&enc={enc}"),
    ("Homework List", f"http://mooc1.chaoxing.com/mooc2/work/list?courseId={cid}&classId={clid}&enc={hidden.get('workEnc','')}"),
    ("AI Workbench", f"http://mooc1.chaoxing.com/course-ans/ai/getStuAiWorkBench?courseId={cid}&clazzId={clid}&cpi={cpi}&ut=s"),
    ("Activities", f"http://mobilelearn.chaoxing.com/page/active/stuActiveList?courseId={cid}&classId={clid}&fid={hidden.get('fid','')}"),
    ("User Account", "http://passport2.chaoxing.com/mooc/account"),
    ("User Space", "http://i.chaoxing.com/base"),
    ("Score Detail", f"http://stat2-ans.chaoxing.com/stat2/stu-score?courseid={cid}&cpi={cpi}&clazzid={clid}"),
    ("Chapter Map", f"http://stat2-ans.chaoxing.com/study-knowledge/index?courseId={cid}&classId={clid}&cpi={cpi}"),
    ("Study Data", f"http://stat2-ans.chaoxing.com/study-data/index?courseId={cid}&classId={clid}&cpi={cpi}"),
]

results = {}
for name, url in endpoints:
    if not url:
        print(f"[SKIP] {name}: no URL")
        continue
    try:
        resp = cx.session.get(url, allow_redirects=True, timeout=10)
        ok = resp.status_code == 200 and len(resp.text) > 500
        tag = "[OK]" if ok else f"[{resp.status_code}]"
        print(f"{tag} {name}: {len(resp.text)} bytes")
        if ok:
            results[name] = {"url": url, "size": len(resp.text), "preview": resp.text[:300]}
            safe_name = name.lower().replace(" ", "_")
            RESPONSES_DIR.joinpath(f"03_{safe_name}.html").write_text(resp.text[:100000], encoding="utf-8")
    except Exception as e:
        print(f"[ERR] {name}: {e}")

save_json(results, "03_working_endpoints.json")
print(f"\n{len(results)} working endpoints saved")
