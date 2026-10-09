# 每日AI新闻助手 Agent

一个基于 **ReAct / Function Calling** 的智能 Agent：每天自动为用户收集 AI 新闻、按订阅偏好筛选、生成简报并邮件推送。

**核心特点：工具调用顺序完全由 LLM 自主决策，不是硬编码流水线。**

---

## 快速开始（5分钟）

### 1. 环境要求
- Python 3.10+

### 2. 克隆/进入项目目录
```bash
cd ai-news-agent
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置环境变量
```bash
cp .env.example .env
```
编辑 `.env`，填入你的密钥：
- `DASHSCOPE_API_KEY`：[通义千问控制台](https://dashscope.console.aliyun.com/) 获取
- `TAVILY_API_KEY`：[tavily.com](https://tavily.com) 获取（可选）
- `SMTP_EMAIL` / `SMTP_PASSWORD`：你的邮箱和SMTP授权码

### 5. 初始化数据库
```bash
python init_db.py
```

### 6. 启动服务
```bash
python main.py
```
打开浏览器访问 http://localhost:8000

登录后可在页面设置个人每日推送时间及时区；新用户默认检测浏览器时区，旧数据库用户迁移时默认 `Asia/Shanghai`。简报日期按用户设置时区计算。SMTP 发送配置了超时、有限重试和数据库发送记录；新闻缓存按 URL 去重并保留最近 30 天，同一用户每天只保留一份简报。

---

## 项目结构

```
ai-news-agent/
├── main.py              # 入口：启动FastAPI + 定时任务
├── config.py           # 环境变量配置
├── init_db.py          # 初始化数据库
├── schema.sql          # 建表SQL
├── requirements.txt    # 依赖清单
├── .env.example        # 环境变量模板
├── agent/
│   ├── llm.py          # 千问客户端封装
│   ├── tools.py        # 8个工具的Schema + 执行函数
│   └── loop.py         # ReAct循环核心（LLM自主决策）
├── api/
│   └── routes.py       # FastAPI路由
├── db/
│   └── database.py     # SQLite操作
├── scheduler/
│   └── tasks.py        # APScheduler每分钟检查各用户的推送时间
├── static/
│   └── index.html      # 简单前端页面
└── data/               # SQLite数据库文件
```

---

## Agent 工具集（共8个）

| 工具 | 作用 |
|---|---|
| `list_dir(path)` | 列出目录内容 |
| `read_file(path)` | 读取文件 |
| `search_content(keyword, dir)` | 全文搜索 |
| `write_file(path, content)` | 写入文件 |
| `bash(command)` | 执行shell命令 |
| `fetch_rss_news(limit)` | 抓取AI新闻RSS源 |
| `search_web_trending(query)` | Tavily联网搜热点 |
| `send_email(to, subject, body)` | 邮件推送简报 |

---

## 技术栈

- **LLM**：通义千问 qwen-plus（OpenAI兼容接口）
- **Agent**：手写 ReAct / Function Calling 循环
- **后端**：FastAPI
- **数据库**：SQLite
- **定时任务**：APScheduler
- **新闻源**：RSS + Tavily Search
- **推送**：SMTP邮件

---

## 核心设计说明

工具调用顺序由 LLM 自主决定：Agent 拿到用户任务后，在循环中不断调用千问API，模型自己决定下一步用哪个工具、要不要再搜一次、什么时候认为信息足够并输出最终简报。整个流程没有硬编码的"先RSS再搜索再发邮件"流水线。
