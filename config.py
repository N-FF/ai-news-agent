"""全局配置：从 .env 读取所有环境变量"""
import os
from dotenv import load_dotenv

load_dotenv()

# 通义千问
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# Tavily
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# 邮件
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

# 服务
PORT = int(os.getenv("PORT", "8000"))
DAILY_RUN_HOUR = int(os.getenv("DAILY_RUN_HOUR", "9"))
DAILY_RUN_MINUTE = int(os.getenv("DAILY_RUN_MINUTE", "0"))

# RSS源
RSS_FEEDS = [u.strip() for u in os.getenv("RSS_FEEDS", "").split(",") if u.strip()]

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "news_agent.db")
