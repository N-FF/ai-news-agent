"""LLM tool schemas declared as small subclasses and auto-registered."""
from __future__ import annotations

from typing import Any, ClassVar


class ToolSchema:
    """Base class for one OpenAI-compatible function tool schema."""

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    properties: ClassVar[dict[str, dict[str, Any]]] = {}
    required: ClassVar[tuple[str, ...]] = ()
    _registry: ClassVar[list[type[ToolSchema]]] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            ToolSchema._registry.append(cls)

    @classmethod
    def to_openai_schema(cls) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": {
                    "type": "object",
                    "properties": cls.properties,
                    "required": list(cls.required),
                },
            },
        }

    @classmethod
    def all_schemas(cls) -> list[dict[str, Any]]:
        return [tool.to_openai_schema() for tool in ToolSchema._registry]


class PathToolSchema(ToolSchema):
    """Shared path parameter for filesystem tools."""

    properties = {"path": {"type": "string", "description": "项目目录中的文件或目录路径"}}
    required = ("path",)


class ListDirSchema(PathToolSchema):
    name = "list_dir"
    description = "列出指定目录下的所有文件和子目录"


class ReadFileSchema(PathToolSchema):
    name = "read_file"
    description = "读取指定文件的文本内容"


class SearchContentSchema(ToolSchema):
    name = "search_content"
    description = "在指定目录下按关键词搜索文件内容（全文搜索）"
    properties = {
        "keyword": {"type": "string", "description": "要搜索的关键词"},
        "dir": {"type": "string", "description": "要搜索的目录路径"},
    }
    required = ("keyword", "dir")


class WriteFileSchema(PathToolSchema):
    name = "write_file"
    description = "把内容写入指定文件（覆盖写入）"
    properties = {
        "path": PathToolSchema.properties["path"],
        "content": {"type": "string", "description": "要写入的文本内容"},
    }
    required = ("path", "content")


class BashSchema(ToolSchema):
    name = "bash"
    description = "执行 shell 命令；仅在可信本地环境显式设置 ENABLE_BASH_TOOL=true 后可用"
    properties = {
        "command": {"type": "string", "description": "要执行的 shell 命令"}
    }
    required = ("command",)


class FetchRssNewsSchema(ToolSchema):
    name = "fetch_rss_news"
    description = "抓取预置的AI新闻RSS源，返回最新的新闻列表（标题、链接、摘要、来源）"
    properties = {
        "limit": {"type": "integer", "description": "每个源最多取几条，默认10条"}
    }


class SearchWebTrendingSchema(ToolSchema):
    name = "search_web_trending"
    description = "用 Tavily 联网搜索今天的 AI 相关热点新闻"
    properties = {
        "query": {"type": "string", "description": "搜索关键词，如 '大模型 最新进展'"}
    }
    required = ("query",)


class SendEmailSchema(ToolSchema):
    name = "send_email"
    description = "发送邮件给用户，用于推送生成的AI新闻简报"
    properties = {
        "to": {"type": "string", "description": "收件人邮箱"},
        "subject": {"type": "string", "description": "邮件主题"},
        "body": {"type": "string", "description": "邮件正文（纯文本）"},
    }
    required = ("to", "subject", "body")


# The base class auto-registers subclasses; adding a tool only requires one class.
TOOLS_SCHEMA = ToolSchema.all_schemas()
TOOL_PARAMETERS_BY_NAME = {
    schema["function"]["name"]: schema["function"]["parameters"]
    for schema in TOOLS_SCHEMA
}
