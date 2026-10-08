"""
Agent 工具集：定义 8 个工具的 JSON Schema + 实际执行函数
题目要求至少5个文件/系统工具，这里额外加了3个业务工具（RSS、联网搜索、发邮件）
"""
import os
import subprocess
import sqlite3
import feedparser
from tavily import TavilyClient
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config
import db.database as db


# ===========================================
# 1. 工具的 JSON Schema 定义（给 LLM 看的）
# ===========================================
TOOLS_SCHEMA = [
    # --- 题目要求的5个文件/系统工具 ---
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出指定目录下的所有文件和子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要列出的目录路径，默认项目根目录"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文件的文本内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要读取的文件路径"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_content",
            "description": "在指定目录下按关键词搜索文件内容（全文搜索）",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "要搜索的关键词"},
                    "dir": {"type": "string", "description": "要搜索的目录路径"}
                },
                "required": ["keyword", "dir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "把内容写入指定文件（覆盖写入）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要写入的文件路径"},
                    "content": {"type": "string", "description": "要写入的文本内容"}
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "执行一条 shell 命令并返回输出结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 shell 命令"}
                },
                "required": ["command"],
            },
        },
    },
    # --- 额外的3个业务工具 ---
    {
        "type": "function",
        "function": {
            "name": "fetch_rss_news",
            "description": "抓取预置的AI新闻RSS源，返回最新的新闻列表（标题、链接、摘要、来源）",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "每个源最多取几条，默认10条"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web_trending",
            "description": "用 Tavily 联网搜索今天的 AI 相关热点新闻",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如 '大模型 最新进展'"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "发送邮件给用户，用于推送生成的AI新闻简报",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "收件人邮箱"},
                    "subject": {"type": "string", "description": "邮件主题"},
                    "body": {"type": "string", "description": "邮件正文（纯文本）"}
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]


# ===========================================
# 2. 工具的实际执行函数
# ===========================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _list_dir(path: str) -> str:
    target = path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)
    if not os.path.isdir(target):
        return f"错误：目录不存在 {target}"
    items = os.listdir(target)
    return f"目录 {target} 内容（共{len(items)}项）：\n" + "\n".join(items)


def _read_file(path: str) -> str:
    target = path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)
    if not os.path.isfile(target):
        return f"错误：文件不存在 {target}"
    with open(target, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return content[:5000]  # 截断防止超长


def _search_content(keyword: str, dir_path: str) -> str:
    target_dir = dir_path if os.path.isabs(dir_path) else os.path.join(PROJECT_ROOT, dir_path)
    if not os.path.isdir(target_dir):
        return f"错误：目录不存在 {target_dir}"
    results = []
    for root, _, files in os.walk(target_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if keyword.lower() in line.lower():
                            results.append(f"{fpath}:{i}: {line.strip()[:200]}")
            except Exception:
                continue
    if not results:
        return f"在 {target_dir} 中未找到包含 '{keyword}' 的内容"
    return f"找到 {len(results)} 处匹配：\n" + "\n".join(results[:30])


def _write_file(path: str, content: str) -> str:
    target = path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已写入文件 {target}（{len(content)} 字符）"


def _bash(command: str) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30,
            cwd=PROJECT_ROOT,
        )
        out = result.stdout[-3000:] if result.stdout else ""
        err = result.stderr[-1000:] if result.stderr else ""
        return f"[exit={result.returncode}]\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    except Exception as e:
        return f"命令执行失败：{e}"


def _fetch_rss_news(limit: int = 10) -> str:
    if not config.RSS_FEEDS:
        return "未配置 RSS 源，请在 .env 中设置 RSS_FEEDS"
    all_news = []
    for url in config.RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            source = feed.feed.get("title", url)
            for entry in feed.entries[:limit]:
                title = entry.get("title", "无标题")
                link = entry.get("link", "")
                summary = entry.get("summary", "")[:300]
                published = entry.get("published", "")
                all_news.append(f"[{source}] {title}\n  链接: {link}\n  时间: {published}\n  摘要: {summary}\n")
                db.cache_news(title, link, source, summary, published)
        except Exception as e:
            all_news.append(f"[抓取失败] {url}: {e}")
    return f"共抓取 {len(all_news)} 条新闻：\n\n" + "\n---\n".join(all_news)


def _search_web_trending(query: str) -> str:
    if not config.TAVILY_API_KEY:
        return "未配置 TAVILY_API_KEY，无法联网搜索"
    try:
        client = TavilyClient(api_key=config.TAVILY_API_KEY)
        resp = client.search(query=query, max_results=8, topic="news")
        results = []
        for r in resp.get("results", []):
            results.append(f"- {r.get('title','')}\n  {r.get('url','')}\n  {r.get('content','')[:200]}")
        return "联网搜索结果：\n" + "\n".join(results)
    except Exception as e:
        return f"搜索失败：{e}"


def _send_email(to: str, subject: str, body: str) -> str:
    if not config.SMTP_EMAIL:
        return "未配置 SMTP 邮件，跳过发送"
    try:
        msg = MIMEMultipart()
        msg["From"] = config.SMTP_EMAIL
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_EMAIL, to, msg.as_string())
        return f"邮件已发送至 {to}"
    except Exception as e:
        return f"邮件发送失败：{e}"


# ===========================================
# 3. 统一分发：根据工具名路由到执行函数
# ===========================================
TOOL_DISPATCH = {
    "list_dir": _list_dir,
    "read_file": _read_file,
    "search_content": _search_content,
    "write_file": _write_file,
    "bash": _bash,
    "fetch_rss_news": _fetch_rss_news,
    "search_web_trending": _search_web_trending,
    "send_email": _send_email,
}


def execute_tool(name: str, arguments: dict) -> str:
    """根据工具名执行对应函数，返回字符串结果"""
    func = TOOL_DISPATCH.get(name)
    if func is None:
        return f"错误：未知工具 {name}"
    try:
        return func(**arguments)
    except Exception as e:
        return f"工具 {name} 执行出错：{e}"
