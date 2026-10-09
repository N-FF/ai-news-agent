# 每日 AI 新闻助手 Agent

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

一个使用 **ReAct / Function Calling** 的 AI 新闻简报项目。用户可以设置关注话题、关键词、每日推送时间和时区；Agent 根据订阅收集新闻、整理简报，并尝试通过邮件推送。

> **GitHub 仓库：** [N-FF/ai-news-agent](https://github.com/N-FF/ai-news-agent)

## 项目亮点

- **模型驱动的工具选择：** Agent 通过手写 ReAct / Function Calling 循环工作；LLM 根据任务上下文选择工具、决定是否继续。15 步上限仅用于避免循环失控。
- **可扩展的工具 Schema：** 使用 `ToolSchema` 基类和子类描述工具参数，子类自动注册生成 LLM 所需的 JSON Schema。
- **个性化订阅和定时推送：** 每位用户可设置多个话题、关键词、每日发送时间和 IANA 时区。
- **新闻来源可组合：** 支持 RSS 和 Tavily 新闻搜索；抓取到的 RSS 新闻会缓存到 SQLite。
- **邮件及历史记录：** SMTP 配置超时和有限重试；只有发送成功的邮件正文才会显示在历史简报中。
- **简单 Web 页面：** 提供用户信息填写、订阅设置、推送时间配置、手动生成和历史简报查看。

## 页面功能

1. 填写姓名和接收简报的邮箱。
2. 添加或删除关注话题和关键词。
3. 选择每日推送时间及时区。
4. 手动触发简报生成，或等待定时任务。
5. 查看确认发送成功的邮件正文。

## 快速开始

### 环境要求

- Python 3.10+
- 通义千问 API Key
- 如需邮件推送：可用的 SMTP 发件邮箱及 SMTP 授权码
- 如需联网搜索：Tavily API Key（可选）

### 1. 克隆仓库

```bash
git clone https://github.com/N-FF/ai-news-agent.git
cd ai-news-agent
```

### 2. 创建虚拟环境并安装依赖

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. 配置环境变量

从模板创建 `.env`：

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

编辑 `.env`，至少填写 `DASHSCOPE_API_KEY`。启用邮件推送时填写 `SMTP_EMAIL` 和 `SMTP_PASSWORD`；该密码应为邮箱提供商生成的 SMTP 授权码，不是邮箱登录密码。Tavily 搜索未配置时不可用。**不要把含真实密钥的 `.env` 提交到 GitHub。**

### 4. 初始化并运行

```bash
python init_db.py
python main.py
```

打开 <http://127.0.0.1:8000>。

数据库表会在服务启动时一并初始化，因此通常可直接运行 `python main.py`。本地 SQLite 数据库文件为 `data/news_agent.db`。

## 环境变量

| 变量 | 说明 | 默认值 / 要求 |
|---|---|---|
| `DASHSCOPE_API_KEY` | 通义千问 API Key | 调用 LLM 必填 |
| `QWEN_MODEL` | 模型名称 | `qwen-plus` |
| `QWEN_BASE_URL` | OpenAI 兼容接口地址 | DashScope 兼容接口 |
| `TAVILY_API_KEY` | Tavily 新闻搜索 Key | 可选 |
| `RSS_FEEDS` | RSS 地址，以逗号分隔 | `.env.example` 提供示例 |
| `SMTP_EMAIL` | SMTP 发件邮箱 | 邮件发送必填 |
| `SMTP_PASSWORD` | SMTP 授权码 | 邮件发送必填 |
| `SMTP_SERVER` | SMTP 服务器 | `smtp.qq.com` |
| `SMTP_PORT` | SMTP SSL 端口 | `465` |
| `SMTP_TIMEOUT` | SMTP 连接超时（秒） | `15` |
| `ENABLE_BASH_TOOL` | 是否启用 Shell 工具 | `false`；仅可信本地环境按需启用 |
| `PORT` | Web 服务端口 | `8000` |

推送时间不是全局环境变量，而是用户在页面中设置的 `HH:MM` 和 IANA 时区（例如 `Asia/Shanghai`）。旧数据库用户迁移后的默认值为 `09:00` 和 `Asia/Shanghai`。

## Agent 与工具设计

工具分为 Schema 描述和实际执行两部分：

- [agent/tool_schemas.py](agent/tool_schemas.py)：`ToolSchema` 基类、具体工具 Schema 子类和自动注册。新增 Schema 时继承基类声明名称、说明和参数；文件类工具可继承 `PathToolSchema` 复用路径参数。
- [agent/tools.py](agent/tools.py)：工具执行函数、`TOOL_DISPATCH` 名称映射及 `execute_tool()` 分发器。
- [agent/loop.py](agent/loop.py)：将工具 Schema 提交给 LLM，执行工具调用、把结果追加回对话，并由模型决定继续或结束。
- [agent/llm.py](agent/llm.py)：通义千问 OpenAI 兼容客户端。

当前工具包括：

| 工具 | 用途 |
|---|---|
| `list_dir(path)` | 列出项目目录 |
| `read_file(path)` | 读取项目内文本文件，最多 5000 字符 |
| `search_content(keyword, dir)` | 按关键词搜索项目目录内容 |
| `write_file(path, content)` | 写入项目内文本文件 |
| `bash(command)` | 执行 Shell 命令，默认关闭 |
| `fetch_rss_news(limit)` | 抓取配置的 RSS 并缓存新闻 |
| `search_web_trending(query)` | 通过 Tavily 搜索新闻 |
| `send_email(to, subject, body)` | 发送简报邮件 |

新增一个完整工具仍需定义 Schema 子类、实现执行函数，并在 `TOOL_DISPATCH` 中注册对应名称。

## 定时推送与数据存储

- APScheduler 每分钟检查订阅用户在各自时区的当前时间；匹配用户设置时间时生成简报。
- 如果服务停机或调度错过对应分钟，当天任务不会自动补发。当前实现适合单进程演示，不包含持久化任务队列或多实例分布式锁。
- SMTP 使用超时和最多三次尝试。SMTP 接受邮件不保证邮件最终进入收件箱。
- 成功发送的邮件正文会保存到历史简报；发送失败或 Agent 未调用发信工具时不写入历史简报。
- 新闻缓存按 URL 去重/更新，并由每日任务清理 30 天以前的缓存；同一用户同一天的简报记录会更新而不是重复新增。
- SQLite 表结构位于 [schema.sql](schema.sql)，数据库访问和旧库迁移位于 [db/database.py](db/database.py)。

## 项目结构

```text
ai-news-agent/
├── main.py                  # FastAPI 入口、数据库初始化和调度器启动
├── config.py                # 环境变量配置
├── init_db.py               # 手动初始化数据库
├── schema.sql               # SQLite 表结构
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量示例（不含真实密钥）
├── agent/
│   ├── llm.py               # LLM 客户端
│   ├── tool_schemas.py      # 继承式工具 Schema 与自动注册
│   ├── tools.py             # 工具执行与分发
│   └── loop.py              # ReAct / Function Calling 循环
├── api/
│   └── routes.py            # FastAPI 页面与 API
├── db/
│   └── database.py          # SQLite 数据访问与迁移
├── scheduler/
│   └── tasks.py             # 用户时区定时推送与缓存清理
├── static/
│   └── index.html           # Web 前端
├── archive/                 # 简报归档
├── cache/                   # 新闻素材缓存
└── data/                    # 本地 SQLite 数据库
```

## 技术栈

Python · FastAPI · Uvicorn · 通义千问（OpenAI 兼容接口）· Function Calling / ReAct · SQLite · APScheduler · feedparser · Tavily · SMTP SSL

## 已知限制

- 页面按邮箱识别用户，当前没有密码登录、邮箱验证或 API 资源授权；不适合公开部署或存放敏感用户信息。
- 文件工具限制在项目目录内，但仍可访问该目录下的配置文件；Shell 工具默认禁用。请勿将其开放给不可信用户。
- 定时任务为进程内 APScheduler；若需要公网或多实例生产部署，应补充身份认证、工具权限隔离、持久队列、任务幂等和监控。
