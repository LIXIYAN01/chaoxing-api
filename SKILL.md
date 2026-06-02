---
name: chaoxing-api
description: 超星学习通(ChaoXing) API接口操作。用于通过纯API方式登录学习通、获取课程列表、读取作业详情（题目+选项+答案+得分）、检查作业完成状态。当用户需要查询学习通作业、抓取网课数据、自动化检查学习通任务时触发。
agent_created: true
---

# 学习通 (ChaoXing) API

通过纯 HTTP 请求方式与超星学习通平台交互，无需浏览器。

## 前置依赖

```bash
pip install requests pycryptodome
```

## 核心流程

### Step 1: 登录 (AES-CBC 加密)

**关键**: 手机号和密码必须用 AES-CBC 加密后发送，不能明文或 Base64。

```
密钥(Key): u2oh6Vu^HWe4_AES   (16字节)
IV:      与Key相同
模式:    CBC
填充:    PKCS7 (PKCS7)
编码:    Base64 输出
```

登录接口:
- **URL**: `POST http://passport2.chaoxing.com/fanyalogin`
- **前置请求**: 先 GET `https://passport2.chaoxing.com/login?loginType=1&newversion=true&fid=-1&refer=http%3A%2F%2Fi.chaoxing.com` 获取 Cookie
- **参数**:

| 参数 | 值 | 说明 |
|------|-----|------|
| fid | -1 | 手机号登录固定值 |
| uname | AES(手机号) | AES加密的手机号 |
| password | AES(密码) | AES加密的密码 |
| refer | http%3A%2F%2Fi.chaoxing.com | 固定 |
| t | true | 固定 |
| forbidotherlogin | 0 | 固定 |

**成功判断**: `resp.json()["status"] == True`，Cookie 中出现 `_uid`

### Step 2: 获取课程列表

- **URL**: `GET http://mooc2-ans.chaoxing.com/visit/courses/list?v={timestamp}&rss=1&start=0&size=500`
- **提取方式**: 正则匹配 `href="(https?://[^"]*stucoursemiddle\?[^"]+)"` 获取每个课程的链接
- **每个链接包含**: `courseid` 和 `clazzid`
- **课程名**: 同页面中 `title="(...)"` 属性，按顺序对应链接

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
- **data-url**: 课程页面中 `title="\u4f5c\u4e1a"[^>]*data-url="([^"]+)"` → 通常为 `http://mooc1.chaoxing.com/mooc2/work/list`
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
- **返回**: 大 HTML 页面 (~166KB)，包含完整的批阅后作业内容
- **注意**: 未完成的作业可能没有 answerId，此时 URL 不含 answerId 参数

### Step 6: 解析详情页HTML

作业详情页的核心 DOM 结构:

```
div.questionLi.singleQuesId (每道题容器, 出现N次 = 题数)
├── div.aiArea > div.aiAreaContent
│   └── h3.mark_name
│       ├── "序号. "
│       ├── span.colorShallow → "(单选题/多选题/判断题)"  [题型]
│       └── span.qtContent.workTextWrap → "题目文本..."     [题目]
│
│   ul.mark_letter.qtDetail (选项列表, 单选/多选题有)
│   └── li.workTextWrap → "A. xxx"  "B. xxx" ...           [选项]
│
└── div.mark_answer
    └── div.mark_key
        ├── span > span.stuAnswerContent → "A/B/C/D"        [你的答案]
        └── span > span.rightAnswerContent → "A/B/C/D"      [正确答案]
    │
    └── div.mark_score
        ├── span.mark_judge_name > span.marking_dui/cuo    [对错标记]
        └── div.totalScore → "1.8分"                        [每题得分]
```

解析要点:
1. **题目文本在 h3 内部的 span.qtContent 中** — 不是独立 div
2. 选项在 `ul.mark_letter > li` 中
3. 学生答案在 `span.stuAnswerContent` 标签内（纯字母）
4. 正确答案在 `span.rightAnswerContent` 标签内（纯字母）
5. 得分在 `div.totalScore` 内（数字+分）
6. 对错: 有 `marking_dui` = 对, `marking_cuo` = 错, `marking_bandui` = 半对

### 可选: 查看答题记录

- **URL**: `GET https://mooc1.chaoxing.com/mooc-ans/mooc2/work/answer-list`
- **参数**: courseId, classId, cpi, workId, answerId, enc
- **用途**: 获取某作业的历次提交记录和总分（不含详细题目）

## 注意事项

1. 所有请求使用同一个 `requests.Session()` 保持 Cookie
2. User-Agent 必须模拟浏览器 Chrome 120
3. 作业列表页需要 `X-Requested-With: XMLHttpRequest` 头
4. Windows 终端打印中文可能乱码，但文件写入 UTF-8 是正常的
5. enc 参数是动态生成的（每次进入课程页面时不同），不可缓存复用
6. 课程列表中的 `i.chaoxing.com` 域名接口全部返回假404，只有 `mooc2-ans.chaoxing.com` 的可用

## 完整 API 文档

详细的接口规范、参数说明、响应结构、Python 示例代码请参阅 [API_REFERENCE.md](API_REFERENCE.md)。

涵盖模块:
- 认证系统 (AES-CBC 加密登录)
- 课程系统 (课程列表、主页、导航)
- 作业系统 (列表、详情、答题记录)
- 考试系统 (考试列表)
- 统计系统 (综合成绩)
- 讨论系统 (话题列表)
- 用户系统 (个人信息、个人空间)
- 其他功能 (AI 工作台、活动列表)

## 项目文件

| 文件 | 说明 |
|------|------|
| `API_REFERENCE.md` | 完整 API 参考文档 |
| `chaoxing_check.py` | 作业查询脚本（登录→课程→作业→详情） |
| `research_tools.py` | API 研究工具库 |
| `examples/login.py` | 最小登录示例 |
| `examples/list_courses.py` | 课程列表示例 |
| `examples/check_homework.py` | 作业查询示例 |
