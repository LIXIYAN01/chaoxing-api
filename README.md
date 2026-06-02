# 超星学习通 API 逆向工程

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

通过纯 HTTP 请求与[超星学习通](https://i.chaoxing.com)平台交互的非官方 Python 工具包。支持登录、课程列表查询、作业详情解析（题目+选项+答案+得分）、考试成绩查看等功能，无需浏览器。

> ⚠️ **仅供学习研究使用**。请勿用于违反学术诚信或平台服务条款的行为。

## 功能

- **认证**: AES-CBC 加密登录，Cookie 持久化
- **课程**: 获取课程列表、解析课程主页隐藏参数
- **作业**: 作业列表、作业详情（题目、选项、你的答案、正确答案、得分）
- **考试**: 考试列表查询
- **成绩**: 综合成绩统计
- **讨论**: 课程讨论区列表
- **其他**: 用户信息、个人空间、课堂活动、AI 工作台

## 快速开始

### 安装依赖

```bash
pip install requests pycryptodome
```

### 登录并查看作业

```python
# 1. 复制 examples/check_homework.py 到本地
# 2. 填入你的手机号和密码
# 3. 运行
python check_homework.py
```

### 最小登录示例

```python
import requests, base64
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
session.get("https://passport2.chaoxing.com/login?loginType=1&newversion=true&fid=-1")
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

## 项目结构

```
├── API_REFERENCE.md       # 完整 API 文档
├── SKILL.md               # Claude Code 技能定义
├── chaoxing_check.py      # 完整的作业查询脚本
├── research_tools.py      # 研究工具库（会话管理、缓存、HTML 解析）
├── examples/
│   ├── login.py           # 最小登录示例
│   ├── list_courses.py    # 课程列表示例
│   └── check_homework.py  # 作业查询示例
├── phase1_explore.py      # Phase 1: 课程页面解剖
├── phase2_discover.py     # Phase 2: 端点发现
└── test_endpoints.py      # 端点快速测试
```

## 接口覆盖

| 模块 | 接口 | 状态 |
|------|------|------|
| 认证 | `passport2.chaoxing.com/fanyalogin` | ✅ |
| 课程列表 | `mooc2-ans.chaoxing.com/visit/courses/list` | ✅ |
| 课程主页 | `mooc1.chaoxing.com/visit/stucoursemiddle` | ✅ |
| 作业列表 | `mooc1.chaoxing.com/mooc2/work/list` | ✅ |
| 作业详情 | `mooc1.chaoxing.com/mooc-ans/mooc2/work/task` | ✅ |
| 答题记录 | `mooc1.chaoxing.com/mooc-ans/mooc2/work/answer-list` | ✅ |
| 考试列表 | `mooc1.chaoxing.com/exam-ans/mooc2/exam/exam-list` | ✅ |
| 综合成绩 | `stat2-ans.chaoxing.com/stat2/overall-score/stu-score` | ✅ |
| 讨论区 | `groupweb.chaoxing.com/course/topic/topicList` | ✅ |
| 用户信息 | `passport2.chaoxing.com/mooc/account` | ✅ |
| 个人空间 | `i.chaoxing.com/base` | ✅ |
| 课堂活动 | `mobilelearn.chaoxing.com/page/active/stuActiveList` | ✅ |
| AI 工作台 | `mooc1.chaoxing.com/course-ans/ai/getStuAiWorkBench` | ✅ |

## 技术要点

### 加密算法

| 项目 | 值 |
|------|------|
| 算法 | AES-CBC |
| 密钥 | `u2oh6Vu^HWe4_AES` (16字节) |
| IV | 与密钥相同 |
| 填充 | PKCS7 |
| 输出 | Base64 |

### enc 安全机制

学习通为每个功能模块分配独立的动态 `enc` 令牌（32位十六进制），包括:

- `workEnc` — 作业模块
- `examEnc` — 考试模块
- `openc` — 章节模块
- `enc` — 通用模块

这些令牌在每次访问课程主页时动态生成，不可缓存复用。

## 完整文档

详见 **[API_REFERENCE.md](API_REFERENCE.md)**，包含：
- 每个接口的 URL、参数表、请求头、响应格式
- DOM 结构图（作业详情页解析）
- Python 代码示例
- 域名清单、隐藏字段列表

## 许可

MIT License. 本项目仅供学习交流，使用者自行承担全部责任。
