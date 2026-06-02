# 超星学习通 (Chaoxing) API 参考文档

> 通过纯 HTTP 请求与超星学习通平台交互的非官方 API 文档。
> 适用于学习通网课数据抓取、作业查询、考试信息获取等场景。
> 本项目仅供学习研究使用。

## 目录

- [1. 概述](#1-概述)
- [2. 认证系统](#2-认证系统)
  - [2.1 登录接口](#21-登录接口)
  - [2.2 加密算法](#22-加密算法)
  - [2.3 Session 与 Cookie](#23-session-与-cookie)
  - [2.4 通用请求头](#24-通用请求头)
- [3. 课程系统](#3-课程系统)
  - [3.1 课程列表](#31-课程列表)
  - [3.2 课程主页](#32-课程主页)
  - [3.3 课程导航结构](#33-课程导航结构)
- [4. 作业系统](#4-作业系统)
  - [4.1 作业列表](#41-作业列表)
  - [4.2 作业详情](#42-作业详情)
  - [4.3 答题记录](#43-答题记录)
- [5. 考试系统](#5-考试系统)
  - [5.1 考试列表](#51-考试列表)
- [6. 统计系统](#6-统计系统)
  - [6.1 综合成绩](#61-综合成绩)
- [7. 讨论系统](#7-讨论系统)
- [8. 用户系统](#8-用户系统)
- [9. 其他功能](#9-其他功能)
- [10. 附录](#10-附录)
  - [10.1 域名列表](#101-域名列表)
  - [10.2 enc 参数详解](#102-enc-参数详解)
  - [10.3 课程隐藏字段清单](#103-课程隐藏字段清单)
  - [10.4 Python 工具库参考](#104-python-工具库参考)

---

## 1. 概述

### 平台简介

超星学习通（Chaoxing）是国内高校广泛使用的在线教学平台，提供课程视频、作业、考试、讨论等功能。平台技术栈为传统的服务端渲染 HTML（非 SPA），大部分接口返回 HTML 页面或 HTML 片段而非 JSON。

### 技术特点

- **协议**: HTTP/HTTPS，REST-like 风格
- **响应格式**: 绝大多数返回 HTML（包括 `text/html` 和 HTML 片段），极少 JSON
- **认证**: AES-CBC 加密的 Cookie 会话认证
- **安全机制**: 每个功能模块使用独立的动态 `enc` 加密令牌，不可跨模块使用
- **请求头**: 部分接口需要 `X-Requested-With: XMLHttpRequest` 头

### 通用注意事项

1. **使用 `requests.Session()`** 保持 Cookie，所有请求必须在同一 Session 中完成
2. **User-Agent** 需模拟移动端/桌面浏览器（推荐 Chrome 120）
3. **enc 参数** 是动态生成的，每次进入课程页面时都会刷新，不可缓存复用
4. **Windows 终端** 打印中文可能乱码，建议使用 `PYTHONIOENCODING=utf-8` 或将输出写入文件
5. **课程列表** 中 `i.chaoxing.com` 域名的接口全部返回 404，只有 `mooc2-ans.chaoxing.com` 的可用

---

## 2. 认证系统

### 2.1 登录接口

#### 前置请求

在发送登录请求前，需要先访问登录页面以获取初始 Cookie：

```
GET https://passport2.chaoxing.com/login?loginType=1&newversion=true&fid=-1&refer=http%3A%2F%2Fi.chaoxing.com
```

#### 登录请求

**接口**: `POST http://passport2.chaoxing.com/fanyalogin`

**参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| fid | int | 是 | 固定值 `-1`（手机号登录） |
| uname | string | 是 | AES 加密后的手机号 |
| password | string | 是 | AES 加密后的密码 |
| refer | string | 是 | 固定值 `http%3A%2F%2Fi.chaoxing.com` |
| t | string | 是 | 固定值 `true` |
| forbidotherlogin | int | 是 | 固定值 `0` |

**成功判断**: `resp.json()["status"] == True`，且 Cookie 中出现 `_uid` 字段。

**响应示例**:
```json
{"status": true, "msg": "success"}
```

**Python 示例**:
```python
import requests
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

KEY = b"u2oh6Vu^HWe4_AES"
IV = KEY

def aes_encrypt(text: str) -> str:
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    padded = pad(text.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode("utf-8")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
})

# 获取初始 Cookie
session.get("https://passport2.chaoxing.com/login?"
            "loginType=1&newversion=true&fid=-1"
            "&refer=http%3A%2F%2Fi.chaoxing.com")

# 登录
resp = session.post("http://passport2.chaoxing.com/fanyalogin", data={
    "fid": "-1",
    "uname": aes_encrypt("手机号"),
    "password": aes_encrypt("密码"),
    "refer": "http%3A%2F%2Fi.chaoxing.com",
    "t": "true",
    "forbidotherlogin": "0",
})
print(resp.json())  # {"status": true}
```

### 2.2 加密算法

| 项目 | 值 |
|------|------|
| 算法 | AES |
| 模式 | CBC |
| 密钥 (Key) | `u2oh6Vu^HWe4_AES` (16 字节) |
| 初始向量 (IV) | 与密钥相同 |
| 填充方式 | PKCS7 |
| 输出编码 | Base64 |

**注意**: 手机号和密码必须分别用 AES-CBC 加密后以 Base64 字符串发送，不能发送明文或普通 Base64。

### 2.3 Session 与 Cookie

登录成功后，Session 中会包含以下关键 Cookie：

| Cookie | 说明 |
|--------|------|
| `_uid` | 用户唯一标识 |
| `JSESSIONID` | Tomcat Session ID |
| `route` | 服务器路由信息 |

所有后续请求必须携带这些 Cookie。Cookie 在一段时间后会过期，届时需要重新登录。

### 2.4 通用请求头

```python
{
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    # 以下按需添加:
    # "X-Requested-With": "XMLHttpRequest",  # 作业/考试列表等需要
    # "Referer": "http://mooc1.chaoxing.com/...",  # 部分接口需要
}
```

---

## 3. 课程系统

### 3.1 课程列表

**接口**: `GET http://mooc2-ans.chaoxing.com/visit/courses/list`

**参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| v | int | 是 | 时间戳（毫秒），如 `int(time.time() * 1000)` |
| rss | int | 否 | 固定 `1` |
| start | int | 否 | 分页起始位置 |
| size | int | 否 | 每页课程数，建议 `500` 一次加载全部 |

**响应格式**: HTML 页面

**数据提取**:
```python
import re

# 课程链接（含 courseid 和 clazzid）
links = re.findall(r'href="(https?://[^"]*stucoursemiddle\?[^"]+)"', html)

# 课程名称
titles = re.findall(r'title="([^"]+)"', html)

# 逐个提取参数
for title, link in zip(titles, links):
    courseid = re.search(r"courseid=(\d+)", link).group(1)
    clazzid = re.search(r"clazzid=(\d+)", link).group(1)
```

**注意**: 课程列表中存在大量重复条目——同一课程会以「课程名」和「教师名」两个入口分别出现，它们共享相同的 `courseId` 和 `classId`。只取其一即可。

### 3.2 课程主页

**接口**: 直接访问课程列表中的链接

```
GET http://mooc1.chaoxing.com/visit/stucoursemiddle?courseid={courseId}&clazzid={classId}
```

**隐藏字段提取**:

课程主页 HTML 中包含大量 `<input type="hidden">` 字段，这些是访问其他功能模块的关键参数：

```python
def extract_hidden_inputs(html: str) -> dict[str, str]:
    fields = {}
    for m in re.finditer(
        r'<input[^>]*type="hidden"[^>]*'
        r'name="([^"]*)"[^>]*'
        r'value="([^"]*)"[^>]*/?>',
        html,
    ):
        fields[m.group(1)] = m.group(2)
    return fields
```

**关键隐藏字段说明**:

| 字段名 | 类型 | 说明 | 使用场景 |
|--------|------|------|----------|
| `courseid` / `courseId` | int | 课程 ID | 所有接口 |
| `clazzid` / `classId` | int | 班级 ID | 所有接口 |
| `cpi` | int | 平台 ID | 大部分接口 |
| `enc` | string(32) | 课程级加密串 | 需要 verif 的通用接口 |
| `workEnc` | string(32) | 作业列表专用加密串 | 作业系统 |
| `examEnc` | string(32) | 考试列表专用加密串 | 考试系统 |
| `openc` | string(32) | 章节/知识点加密串 | 章节系统 |
| `oldenc` | string(32) | 旧版加密串（备用） | 兼容场景 |
| `fid` | int | 学校/机构 ID | 活动/签到 |
| `bbsid` | string(32) | 讨论区 ID | 讨论系统 |
| `cfid` | int | 课程分类 ID | 统计系统 |
| `userId` | int | 当前用户 ID | 个人信息 |
| `heardUt` | string | 用户类型标识 (s=学生, t=教师) | 部分接口 |

### 3.3 课程导航结构

课程页面侧边栏包含以下导航标签（以 `data-url` 或 JavaScript 事件绑定）：

| dataname | 标题 | data-url（相对路径需补全） | 说明 |
|----------|------|---------------------------|------|
| `ai_workbench` | AI工作 | `http://mooc1.chaoxing.com/course-ans/ai/getStuAiWorkBench?courseId=X&clazzId=Y&cpi=Z&ut=s` | AI 学习助手 |
| `hd` | 活动 | `http://mobilelearn.chaoxing.com/page/active/stuActiveList` | 课堂活动（签到、选人等） |
| `zj` | 章节 | `/mooc2-ans/mycourse/studentcourse` | 章节/知识点树（JS驱动，需进一步分析） |
| `tl` | 讨论 | `http://groupweb.chaoxing.com/course/topic/topicList` | 课程讨论区 |
| `zy` | 作业 | `http://mooc1.chaoxing.com/mooc2/work/list` | 作业列表 |
| `ks` | 考试 | `http://mooc1.chaoxing.com/exam-ans/mooc2/exam/exam-list` | 考试列表 |
| `zl` | 资料 | `/mooc2-ans/coursedata/stu-datalist` | 课程资料/资源 |
| `ctj` | 错题集 | `/mooc2-ans/wrongque/page` | 错题本 |
| `cj` | 学习记录 | `http://stat2-ans.chaoxing.com/study-data/index` | 学习数据统计 |
| `zsd` | 课程图谱 | `http://stat2-ans.chaoxing.com/study-knowledge/index` | 知识点图谱 |

**注意**: 章节（`zj`）和资料（`zl`）使用相对路径，其实际 URL 由 JavaScript (`contentLoader.js` / `course-stu.js`) 动态构造，直接拼接可能无法访问。这些模块的完整 API 路径需进一步分析前端 JS。

---

## 4. 作业系统

### 4.1 作业列表

**接口**: `GET http://mooc1.chaoxing.com/mooc2/work/list`

**参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| courseId | int | 是 | 课程 ID |
| classId | int | 是 | 班级 ID |
| enc | string | 是 | `workEnc`，从课程主页获取 |

**请求头**:
```
X-Requested-With: XMLHttpRequest
```

**响应格式**: HTML 片段（`<ul>` 列表）

**响应结构**:
```html
<ul>
  <li data="http://mooc1.chaoxing.com/mooc-ans/mooc2/work/task?
            courseId=X&classId=Y&cpi=Z&workId=W&answerId=A&enc=E"
      aria-label="作业名称 ; 完成状态">
    ...
  </li>
</ul>
```

**数据提取**:
```python
items = re.findall(
    r'<li[^>]*data="([^"]+)"[^>]*aria-label="([^"]*)"',
    html,
)
for data_url, aria_label in items:
    parts = aria_label.replace("&nbsp;", "").split(";")
    name = parts[0].strip()
    status = parts[1].strip() if len(parts) > 1 else "未知"

    work_id = re.search(r"workId=(\d+)", data_url).group(1)
    answer_id_match = re.search(r"answerId=(\d+)", data_url)
    answer_id = answer_id_match.group(1) if answer_id_match else None
```

**状态值说明**:

| 状态 | 含义 |
|------|------|
| `已完成` | 已提交且已批阅 |
| `未交` | 尚未提交 |
| `未完成` | 已开始但未提交 |
| `待批阅` | 已提交，等待老师批阅 |

### 4.2 作业详情

**接口**: `GET http://mooc1.chaoxing.com/mooc-ans/mooc2/work/task`

**参数**: 从作业列表的 `<li data="...">` 属性中完整获取

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| courseId | int | 是 | 课程 ID |
| classId | int | 是 | 班级 ID |
| cpi | int | 是 | 平台 ID |
| workId | int | 是 | 作业 ID |
| answerId | int | 否 | 答案 ID（已提交的作业才有） |
| enc | string | 是 | 该作业专用加密串 |

**响应格式**: HTML 页面（含完整批阅后的题目内容）

**作业详情页 DOM 结构**:

```
div.questionLi.singleQuesId              ← 每道题的容器（出现 N 次 = 题数）
├── div.aiArea > div.aiAreaContent
│   └── h3.mark_name
│       ├── "序号. "
│       ├── span.colorShallow → "(单选题/多选题/判断题/简答题)"  [题型]
│       └── span.qtContent.workTextWrap → "题目文本..."         [题目]
│
│   ul.mark_letter.qtDetail              ← 选项列表（选择题有）
│   └── li.workTextWrap → "A. xxx"  "B. xxx" ...
│
└── div.mark_answer
    └── div.mark_key
        ├── span > span.stuAnswerContent → "A/B/C/D"            [你的答案]
        └── span > span.rightAnswerContent → "A/B/C/D"          [正确答案]
    │
    └── div.mark_score
        ├── span.mark_judge_name > span.marking_dui/cuo/bandui  [对错]
        └── div.totalScore → "1.8分"                            [得分]
```

**Python 解析示例**:

```python
import re

def parse_questions(detail_html: str) -> list[dict]:
    """解析作业详情页中的所有题目"""
    # 按 questionLi 切割
    q_blocks = re.split(r'(?=<div class="questionLi)', detail_html)
    q_blocks = [b for b in q_blocks if 'questionLi' in b]

    questions = []
    for block in q_blocks:
        q = {}
        # 题型
        m = re.search(r'class="[^"]*colorShallow[^"]*"[^>]*>\((.*?)\)<', block)
        q["type"] = m.group(1) if m else ""

        # 题目文本
        m = re.search(r'class="[^"]*qtContent[^"]*"[^>]*>(.*?)</span>', block, re.DOTALL)
        q["title"] = m.group(1).strip() if m else ""

        # 选项
        q["options"] = re.findall(
            r'<li[^>]*class="[^"]*workTextWrap[^"]*"[^>]*>(.*?)</li>',
            block, re.DOTALL
        )

        # 我的答案
        m = re.search(r'class="[^"]*stuAnswerContent[^"]*"[^>]*>(.*?)</span>', block)
        q["my_answer"] = m.group(1).strip() if m else ""

        # 正确答案
        m = re.search(r'class="[^"]*rightAnswerContent[^"]*"[^>]*>(.*?)</span>', block)
        q["right_answer"] = m.group(1).strip() if m else ""

        # 得分
        m = re.search(r'class="[^"]*totalScore[^"]*"[^>]*>([\d.]+)分?</div>', block)
        q["score"] = float(m.group(1)) if m else 0.0

        # 对错标记
        q["is_correct"] = "marking_dui" in block
        q["is_wrong"] = "marking_cuo" in block
        q["is_half"] = "marking_bandui" in block

        questions.append(q)
    return questions
```

**题型与标记说明**:

| 题型 | 标记值 | 有选项 | 有标准答案 |
|------|--------|--------|------------|
| 单选题 | `单选题` | 是 | 是 |
| 多选题 | `多选题` | 是 | 是 |
| 判断题 | `判断题` | 否 | 是 |
| 简答题 | `简答题` | 否 | 否（需人工批阅） |

| 对错标记 | 含义 |
|----------|------|
| `marking_dui` | 正确 |
| `marking_cuo` | 错误 |
| `marking_bandui` | 半对 |

### 4.3 答题记录

**接口**: `GET http://mooc1.chaoxing.com/mooc-ans/mooc2/work/answer-list`

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| courseId | int | 课程 ID |
| classId | int | 班级 ID |
| cpi | int | 平台 ID |
| workId | int | 作业 ID |
| answerId | int | 答案 ID |
| enc | string | 作业加密串 |

**用途**: 获取某作业的历次提交记录和总分（不含详细题目内容）。

---

## 5. 考试系统

### 5.1 考试列表

**接口**: `GET http://mooc1.chaoxing.com/exam-ans/mooc2/exam/exam-list`

**参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| courseId | int | 是 | 课程 ID |
| classId | int | 是 | 班级 ID |
| enc | string | 是 | `examEnc`，从课程主页获取 |

**请求头**:
```
X-Requested-With: XMLHttpRequest
```

**响应格式**: HTML 页面，内容包含考试列表。结构类似于作业列表，每条考试记录包含名称、截止时间、状态等信息。

> **注意**: 考试详情页的 URL 结构和解析逻辑与作业类似但参数名略有不同。完整的考试详情解析尚待进一步逆向。

---

## 6. 统计系统

### 6.1 综合成绩

**接口**: `GET http://stat2-ans.chaoxing.com/stat2/overall-score/stu-score`

**参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| courseid | int | 是 | 课程 ID |
| clazzid | int | 是 | 班级 ID |
| cpi | int | 是 | 平台 ID |
| ut | string | 是 | 用户类型，`s` = 学生 |

**响应格式**: HTML 页面（~58KB），标题为「统计-综合成绩」

**包含内容**:
- 各项作业/考试/章节学习的权重和得分
- 综合成绩汇总表格
- 成绩分布图表数据

### 6.2 学习数据统计

**接口**: `GET http://stat2-ans.chaoxing.com/study-data/index`

**参数**: `courseId`, `classId`, `cpi`

> **注意**: 此接口返回 403，可能需要特定的 Referer 或额外的认证参数。

### 6.3 知识点图谱

**接口**: `GET http://stat2-ans.chaoxing.com/study-knowledge/index`

**参数**: `courseId`, `classId`, `cpi`

> **注意**: 此接口返回 403，可能需要特定的 Referer 或额外的认证参数。

---

## 7. 讨论系统

**接口**: `GET http://groupweb.chaoxing.com/course/topic/topicList`

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| courseId | int | 课程 ID |
| clazzid | int | 班级 ID |
| bbsid | string | 讨论区 ID，从课程主页获取 |
| cpi | int | 平台 ID |
| enc | string | 课程加密串 |

**响应格式**: HTML 页面，包含话题列表。

---

## 8. 用户系统

### 8.1 用户信息

**接口**: `GET http://passport2.chaoxing.com/mooc/account`

**响应格式**: HTML 页面，包含用户基本信息（姓名、学号/工号、学校等）。

### 8.2 个人空间

**接口**: `GET http://i.chaoxing.com/base`

**响应格式**: HTML 页面（~73KB），包含个人空间主页。

### 8.3 课程活动

**接口**: `GET http://mobilelearn.chaoxing.com/page/active/stuActiveList`

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| courseId | int | 课程 ID |
| classId | int | 班级 ID |
| fid | int | 学校/机构 ID |

**响应格式**: HTML 页面（~150KB），包含课堂活动列表（签到、投票、选人、抢答等）。

---

## 9. 其他功能

### 9.1 AI 工作台

**接口**: `GET http://mooc1.chaoxing.com/course-ans/ai/getStuAiWorkBench`

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| courseId | int | 课程 ID |
| clazzId | int | 班级 ID |
| cpi | int | 平台 ID |
| ut | string | 用户类型 |

**响应格式**: HTML 页面，包含 AI 学习助手界面和相关数据。

### 9.2 AI 聊天机器人

**接口**: `GET https://robot.chaoxing.com/chat`

**参数**: `unitId`, `robotId`, `referUrl`

**说明**: 超星 AI 问答机器人，嵌入在课程页面中。

---

## 10. 附录

### 10.1 域名列表

| 域名 | 用途 |
|------|------|
| `passport2.chaoxing.com` | 认证/登录 |
| `mooc2-ans.chaoxing.com` | 课程列表 |
| `mooc1.chaoxing.com` | 课程主页、作业、考试、AI 工作台 |
| `stat2-ans.chaoxing.com` | 统计数据、成绩 |
| `groupweb.chaoxing.com` | 讨论区 |
| `mobilelearn.chaoxing.com` | 移动学习、课堂活动 |
| `i.chaoxing.com` | 个人空间 |
| `mooc-res2.chaoxing.com` | 静态资源 CDN（JS/CSS） |
| `p.ananas.chaoxing.com` | 媒体资源 CDN（图片/视频） |
| `robot.chaoxing.com` | AI 聊天机器人 |
| `notice.chaoxing.com` | 通知系统（未验证） |

### 10.2 enc 参数详解

`enc` 是学习通最核心的安全机制。它是一个 32 位十六进制字符串，作为各功能模块的访问令牌。

**特点**:

1. **动态生成**: 每次访问课程主页时，服务端会重新生成所有 enc 值
2. **不可缓存**: 不能将上一次的 enc 存下来重复使用
3. **模块隔离**: 不同模块使用不同的 enc：
   - `enc` — 通用课程加密串
   - `workEnc` — 仅用于作业列表
   - `examEnc` — 仅用于考试列表
   - `openc` — 用于章节/知识点
4. **有效期**: 通常在一次 Session 内有效，但超时后会失效
5. **获取方式**: 必须通过 GET 课程主页 → 解析隐藏 `<input>` 字段获取

**正确的使用流程**:
```
1. GET 课程主页 → 提取 enc / workEnc / examEnc
2. 使用对应的 enc 访问对应模块
3. 如果 enc 失效（返回 302/404），重新访问课程主页获取新 enc
```

### 10.3 课程隐藏字段清单

以下是从课程主页中可提取的所有关键隐藏字段：

```json
{
  "courseid": "课程ID",
  "clazzid": "班级ID",
  "cfid": "课程分类ID",
  "bbsid": "讨论区ID",
  "cpi": "平台ID",
  "heardUt": "用户类型(s=学生)",
  "fid": "学校/机构ID",
  "openc": "章节加密串",
  "enc": "通用课程加密串",
  "oldenc": "旧版加密串",
  "userId": "当前用户ID",
  "moocDomainName": "MOOC服务域名",
  "courseApp": "是否使用课程APP",
  "workEnc": "作业加密串",
  "examEnc": "考试加密串",
  "bbsUrlSwitch": "讨论区URL开关",
  "courseEvaluateUrl": "课程评价URL",
  "learnSilverStartTime": "学习银币开始时间",
  "learnSilverEndTime": "学习银币结束时间"
}
```

### 10.4 Python 工具库参考

本项目提供了一个研究工具集 `research_tools.py`，包含：

**`ChaoxingSession`** — 会话管理器
- `login(force=False)` — 登录，支持 Cookie 缓存
- `get(url)` — 封装的 GET 请求
- `get_json(url)` — GET + JSON 解析
- `dump_page(url, name)` — 抓取页面并缓存到 `cache/` 目录
- `uid` — 当前用户 ID

**HTML 分析函数**:
- `extract_hidden_inputs(html)` — 提取所有隐藏字段
- `extract_data_urls(html)` — 提取所有 data-url
- `extract_iframes(html)` — 提取 iframe
- `extract_all_urls(html)` — 提取所有 URL
- `analyze_response(html)` — 分析响应类型

**课程解析函数**:
- `parse_course_list(html)` — 解析课程列表
- `parse_course_page(html)` — 解析课程主页结构

---

## 相关项目文件

| 文件 | 说明 |
|------|------|
| `chaoxing_check.py` | 完整的作业查询脚本（登录→课程列表→作业详情） |
| `research_tools.py` | API 研究工具库 |
| `phase1_explore.py` | Phase 1: 课程页面解剖脚本 |
| `phase2_discover.py` | Phase 2: 端点发现脚本 |
| `cache/` | 原始响应缓存目录 |

## 许可与声明

本项目为逆向工程研究，仅供学习交流使用。请勿用于：
- 违反学术诚信的自动化答题/代刷
- 大规模数据采集影响平台正常运行
- 任何违反超星学习通服务条款的行为

使用本项目的所有风险由使用者自行承担。
