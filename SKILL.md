---
name: chaoxing-api
description: 超星学习通(ChaoXing/超星/学习通/mooc) API接口操作。用于通过纯API方式登录学习通、获取课程列表(含已结束课程)、读取作业详情（题目+选项+答案+得分）、检查作业完成状态、批量导出作业数据到Excel。当用户提到"学习通""超星""chaoxing""网课""mooc""课程作业""在线作业""查作业""导出作业"等关键词时立即触发。不要尝试用浏览器方式——直接用这个API。
---

# 学习通 (ChaoXing) API

> GitHub: [https://github.com/LIXIYAN01/chaoxing-api](https://github.com/LIXIYAN01/chaoxing-api)

通过纯 HTTP 请求方式与超星学习通平台交互，无需浏览器。支持登录、课程列表（含已结束课程）、作业列表、作业详情解析、导出Excel。

## 前置依赖

```bash
pip install requests pycryptodome openpyxl
```

## 可用脚本

| 脚本 | 用途 |
|------|------|
| `chaoxing_final.py` | **推荐** 生产版：登录→全部课程→每门课作业(名称+状态)→输出报告 |
| `chaoxing_extract.py` | 一键提取：指定课程→获取所有作业→解析题目→导出Excel/CSV/MD |
| `chaoxing_check.py` | 探索版：尝试多个API接口，调试用 |

## 核心流程

### Step 1: 登录 (AES-CBC 加密)

**关键**: 手机号和密码必须用 AES-CBC 加密后发送，不能明文或 Base64。

```
密钥(Key): u2oh6Vu^HWe4_AES   (16字节)
IV:      与Key相同
模式:    CBC
填充:    PKCS7
编码:    Base64 输出
```

登录接口:
- **前置请求**: 先 GET `https://passport2.chaoxing.com/login?loginType=1&newversion=true&fid=-1&refer=http%3A%2F%2Fi.chaoxing.com` 获取 Cookie
- **登录请求**: `POST http://passport2.chaoxing.com/fanyalogin`

| 参数 | 值 | 说明 |
|------|-----|------|
| fid | -1 | 手机号登录固定值 |
| uname | AES(手机号) | AES加密的手机号 |
| password | AES(密码) | AES加密的密码 |
| refer | http%3A%2F%2Fi.chaoxing.com | 固定 |
| t | true | 固定 |
| forbidotherlogin | 0 | 固定 |

**成功判断**: `resp.json()["status"] == True`，Cookie 中出现 `_uid`

### Step 2: 获取课程列表（含已结束课程）

- **URL**: `GET http://mooc2-ans.chaoxing.com/visit/courses/list?v={timestamp}&rss=1&start=0&size=500`
- **此接口同时返回进行中和已结束的课程**，无需额外参数。
- **提取方式**: 使用结构化正则将链接与课程名配对提取：

```python
# ✅ 正确做法：一条正则同时提取链接和对应的课程名span
pattern = r'<a[^>]*href="(https?://[^"]*stucoursemiddle[^"]+)"[^>]*>.*?<span[^>]*title="([^"]+)"[^>]*>'
matches = re.findall(pattern, html, re.S)
```

- **常见错误**: 不要分别匹配链接和title属性然后1:1对应。页面中有大量非课程名的 `title=` 属性（教师名、公告标题等），会导致课程名映射错乱。
- **每个链接包含**: `courseid` 和 `clazzid`

### Step 3: 进入课程获取隐藏参数

访问课程 URL (`http://mooc1.chaoxing.com/visit/stucoursemiddle?...`)，从 HTML 提取隐藏字段:

| 字段 | name/id | 用途 |
|------|---------|------|
| courseId | name="courseid" / id="courseId" | 课程ID |
| classId | name="clazzid" / id="classId" | 班级ID |
| cpi | name="cpi" / id="cpi" | 平台ID |
| enc | id="enc" | 课程级加密串 |
| workEnc | name="workEnc" / id="workEnc" | **作业列表专用加密串** |

### Step 4: 获取作业列表

- **URL**: `{data-url from title="作业"}?courseId={cid}&classId={clid}&enc={workEnc}`
- **data-url**: 课程页面中 `title="作业"[^>]*data-url="([^"]+)"` → 通常为 `http://mooc1.chaoxing.com/mooc2/work/list`
- **返回格式**: HTML 片段（非 JSON）
- **提取方式**: 每个 `<li>` 的 `data` 和 `aria-label` 属性

**每个作业项的关键信息在 `<li data="完整URL">` 中**:

```
data="http://mooc1.chaoxing.com/mooc-ans/mooc2/work/task?
       courseId=X&classId=Y&cpi=Z&
       workId=W&answerId=A&enc=E"
aria-label="作业名称 ; 已完成/未交"
```

其中:
- **workId (W)**: 数字型作业ID
- **answerId (A)**: 数字型答案ID（已提交的作业才有）
- **enc (E)**: 该作业专用的加密串

### Step 5: 获取作业详情（题目+答案）

- **URL**: 从 Step 4 的 `<li data="...">` 直接取完整 URL
- **即**: `/mooc-ans/mooc2/work/task?courseId=X&classId=Y&cpi=Z&workId=W&answerId=A&enc=E`
- **返回**: 大 HTML 页面，包含完整的批阅后作业内容
- **注意**: 未完成的作业可能没有 answerId

### Step 6: 解析详情页HTML

作业详情页的核心 DOM 结构:

```
div.questionLi.singleQuesId (每道题容器)
├── div.aiArea > div.aiAreaContent
│   └── h3.mark_name
│       ├── "序号. "
│       ├── span.colorShallow → "(单选题/多选题/判断题)"  [题型]
│       └── span.qtContent.workTextWrap → "题目文本..."     [题目]
│
│   ul.mark_letter.qtDetail (选项列表)
│   └── li.workTextWrap → "A. xxx"  "B. xxx" ...           [选项]
│
└── div.mark_answer
    └── div.mark_key
        ├── span > span.stuAnswerContent → "A/B/C/D"        [你的答案]
        └── span > span.rightAnswerContent → "A/B/C/D"      [正确答案]
    │
    └── div.mark_score
        ├── span.mark_judge_name > span.marking_dui/cuo    [对错标记]
        └── div.totalScore → "5分"                          [每题得分]
```

**解析要点**:
1. 题目文本在 `span.qtContent` 内部 `<p>` 标签中
2. 题型在 `span.colorShallow` 中，格式如 `(单选题)`，正则: `r'class="[^"]*colorShallow[^"]*"[^>]*>\s*[(（]?\s*([^)<]*?)\s*[)）]?\s*</span>'`
3. 选项在 `ul.mark_letter > li.workTextWrap` 中
4. 学生答案在 `span.stuAnswerContent` 内
5. 正确答案在 `span.rightAnswerContent` 内
6. 得分在 `div.totalScore` 内
7. 对错: `marking_dui` = 对, `marking_cuo` = 错, `marking_bandui` = 半对

**Question block 正则匹配**（非贪婪，到下一个questionLi或字符串末尾）:
```python
ques_blocks = re.findall(
    r'<div[^>]*class="[^"]*questionLi[^"]*"[^>]*>([\s\S]*?)(?=<div[^>]*class="[^"]*questionLi[^"]*"|$)',
    html
)
```

## 常见问题排查

### 问题1：Windows终端中文乱码

**现象**: `print()` 输出的中文显示为乱码。

**根因**: Windows CMD/PowerShell 默认使用 GBK 编码。

**解决方案**（按优先级）:
1. **所有关键数据写入UTF-8文件，用 Read 工具查看** — 最可靠。
2. 脚本开头: `sys.stdout.reconfigure(encoding='utf-8')`
3. `chaoxing_final.py` 已内置 `safe_print()` 函数处理编码回退。

**使用此skill时的最佳实践**: 执行脚本后，直接读取脚本生成的 JSON/CSV/MD 文件查看结果，而非依赖终端输出。

### 问题2：找不到"已结束的课程"

**现象**: 课程列表中看不到已结束学期的课程。

**根因**: `mooc2-ans.chaoxing.com/visit/courses/list` 接口**已同时返回进行中和已结束课程**。真正的问题是旧版脚本中课程名提取方式有 bug：

```python
# ❌ 错误：分别匹配链接和title，页面中title属性远多于课程数，映射错乱
links = re.findall(r'href="...stucoursemiddle..."', html)
titles = re.findall(r'title="([^"]{4,})"', html)
for i, t in enumerate(titles):
    courses[i]["name"] = t  # 序号对不上！
```

**正确做法**: 见 Step 2 的结构化正则。

### 问题3：Skill未触发

**现象**: 用户提到"学习通"但AI尝试浏览器而不是API。

**解决方案**: 本skill已覆盖主要触发词。若AI仍尝试浏览器，直接说"用超星API"即可触发。

## 注意事项

1. 所有请求使用同一个 `requests.Session()` 保持 Cookie
2. User-Agent 必须模拟浏览器 Chrome 120+
3. 作业列表页需要 `X-Requested-With: XMLHttpRequest` 头
4. enc 参数是动态生成的（每次进入课程页面时不同），不可缓存复用
5. 课程列表中的 `i.chaoxing.com` 域名接口全部返回假404，只有 `mooc2-ans.chaoxing.com` 的可用
6. 请求间隔建议 1-1.5 秒避免频率限制

## 完整 API 文档

详细的接口规范、参数说明、响应结构、Python 示例代码请参阅 [API_REFERENCE.md](API_REFERENCE.md)。
