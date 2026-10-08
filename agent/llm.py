"""通义千问 LLM 客户端封装（兼容 OpenAI SDK）"""
from openai import OpenAI
import config

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.DASHSCOPE_API_KEY,
            base_url=config.QWEN_BASE_URL,
        )
    return _client


def chat(messages: list, tools: list = None, temperature: float = 0.7):
    """调用千问 chat.completions，支持 function calling"""
    client = get_client()
    kwargs = {
        "model": config.QWEN_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message
