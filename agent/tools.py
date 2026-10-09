"""Agent 工具执行函数与名称分发。Schema 定义位于 agent.tool_schemas。"""
import os
import sqlite3
import time
import subprocess
from pathlib import Path
import feedparser
from tavily import TavilyClient
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config
import db.database as db
from agent.tool_schemas import TOOL_PARAMETERS_BY_NAME
# ===========================================
# 工具的实际执行函数
# ===========================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_project_path(path: str) -> Path:
    requested = Path(path)
    target = (requested if requested.is_absolute() else PROJECT_ROOT / requested).resolve()
    try:
        target.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError("文件工具仅允许访问项目目录中的路径") from exc
    return target


def _list_dir(path: str) -> str:
    target = _resolve_project_path(path)
    if not target.is_dir():
        return f"错误：目录不存在 {target}"
    items = os.listdir(target)
    return f"目录 {target} 内容（共{len(items)}项）：\n" + "\n".join(items)


def _read_file(path: str) -> str:
    target = _resolve_project_path(path)
    if not target.is_file():
        return f"错误：文件不存在 {target}"
    with open(target, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return content[:5000]  # 截断防止超长


def _search_content(keyword: str, dir: str) -> str:
    target_dir = _resolve_project_path(dir)
    if not target_dir.is_dir():
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
    target = _resolve_project_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已写入文件 {target}（{len(content)} 字符）"


def _bash(command: str) -> str:
    if not config.ENABLE_BASH_TOOL:
        return "bash 工具默认禁用；仅在可信本地环境于 .env 中设置 ENABLE_BASH_TOOL=true 后启用。"
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
        _record_email_delivery(to, subject, "skipped", 0, "未配置 SMTP_EMAIL")
        return "未配置 SMTP 邮件，跳过发送"
    msg = MIMEMultipart()
    msg["From"] = config.SMTP_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    max_attempts = 3
    last_error = "未知 SMTP 错误"
    attempts = 0
    for attempts in range(1, max_attempts + 1):
        try:
            with smtplib.SMTP_SSL(
                config.SMTP_SERVER,
                config.SMTP_PORT,
                timeout=config.SMTP_TIMEOUT,
            ) as server:
                server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
                refused = server.sendmail(config.SMTP_EMAIL, to, msg.as_string())
                if refused:
                    raise smtplib.SMTPRecipientsRefused(refused)
            _record_email_delivery(to, subject, "sent", attempts)
            return f"邮件已发送至 {to}"
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused) as exc:
            last_error = str(exc)
            break
        except smtplib.SMTPResponseException as exc:
            last_error = str(exc)
            if not 400 <= exc.smtp_code < 500:
                break
        except (smtplib.SMTPServerDisconnected, OSError, TimeoutError) as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
            break

        if attempts < max_attempts:
            time.sleep(attempts)

    _record_email_delivery(to, subject, "failed", attempts, last_error)
    return f"邮件发送失败（尝试{attempts}次）：{last_error}"


def _record_email_delivery(
    to: str,
    subject: str,
    status: str,
    attempts: int,
    error_message: str = "",
) -> None:
    try:
        db.record_email_delivery(to, subject, status, attempts, error_message)
    except Exception as log_error:
        # 日志落库失败不能导致已经发出的邮件被重新发送。
        print(f"邮件发送记录写入失败：{log_error}")


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


def execute_tool(
    name: str,
    arguments: dict,
) -> str:
    """根据工具名执行对应函数，返回字符串结果"""
    func = TOOL_DISPATCH.get(name)
    if func is None:
        return f"错误：未知工具 {name}"
    if not isinstance(arguments, dict):
        return f"工具 {name} 参数格式错误：需要 JSON 对象，请重新调用。"

    parameter_schema = TOOL_PARAMETERS_BY_NAME.get(name, {})
    missing = [key for key in parameter_schema.get("required", []) if key not in arguments]
    if missing:
        missing_list = "、".join(missing)
        return f"工具 {name} 缺少必填参数：{missing_list}。请补齐参数后重新调用。"

    try:
        return func(**arguments)
    except Exception as e:
        return f"工具 {name} 执行出错：{e}"
