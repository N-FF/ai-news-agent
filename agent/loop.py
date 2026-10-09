"""
ReAct / Function Calling 循环核心：
让 LLM 自己决定调哪个工具、调几次、什么时候停。
不是硬编码流水线，是 LLM 自主决策。
"""
import json
from agent.llm import chat
from agent.tools import TOOLS_SCHEMA, execute_tool


SYSTEM_PROMPT = """你是一个「每日AI新闻助手 Agent」。
你的任务：根据用户的订阅偏好，自动完成"收集AI新闻 → 筛选相关内容 → 生成简报 → 推送"的完整流程。

工作方式：
1. 你可以调用工具来获取信息和执行动作
2. 工具调用顺序完全由你自己决定——先做什么、后做什么、要不要再搜一次，都由你判断
3. 拿到工具结果后，判断信息是否足够；不够就继续调用工具，够了就输出最终简报
4. 最终简报要求：
   - 标题：今日AI新闻简报（日期）
   - 按用户关注的话题分类组织
   - 每条新闻给出：标题、来源、一句话摘要、为什么值得关注
   - 控制在 10 条以内，精选最重要的
   - 结尾给出一句话总结

注意：
- 不要编造新闻，所有内容必须来自工具返回的真实结果
- 调用 send_email 时，正文用你生成的简报
- 完成所有工作后，输出一段总结说明你做了什么（调了哪些工具、筛了几条新闻、推送给了谁）
"""


def run_agent(
    user_query: str,
    max_steps: int = 15,
) -> dict:
    """
    运行 Agent 循环。
    返回：{ "final_output": str, "steps": list, "tool_calls_count": int }
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    steps = []
    tool_calls_count = 0
    email_attempted = False
    email_sent = False
    email_status = "Agent 未调用邮件发送工具"
    email_body = ""

    for step in range(max_steps):
        # 调 LLM，带上工具列表
        ai_message = chat(messages, tools=TOOLS_SCHEMA, temperature=0.5)

        # 把 LLM 的回复加进上下文
        messages.append({
            "role": "assistant",
            "content": ai_message.content or "",
            "tool_calls": [tc.model_dump() for tc in (ai_message.tool_calls or [])] if ai_message.tool_calls else None,
        })
        # 清理掉 None 字段
        messages[-1] = {k: v for k, v in messages[-1].items() if v is not None}

        # 如果 LLM 没有要求调用工具，说明它认为任务完成了
        if not ai_message.tool_calls:
            return {
                "final_output": ai_message.content or "",
                "steps": steps,
                "tool_calls_count": tool_calls_count,
                "email_attempted": email_attempted,
                "email_sent": email_sent,
                "email_status": email_status,
                "email_body": email_body,
            }

        # 依次执行 LLM 要求的每个工具调用
        for tool_call in ai_message.tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            print(f"[Step {step+1}] 调用工具: {tool_name} | 参数: {tool_args}")
            result = execute_tool(tool_name, tool_args)
            tool_calls_count += 1
            if tool_name == "send_email":
                email_attempted = True
                email_status = result
                if result.startswith("邮件已发送至 "):
                    email_sent = True
                    email_body = tool_args.get("body", "")
            steps.append({"tool": tool_name, "args": tool_args, "result_preview": result[:300]})

            # 把工具结果作为 tool 角色消息塞回上下文
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": result,
            })

    # 超过最大步数还没停，强制退出
    return {
        "final_output": "（达到最大步数限制，任务强制结束）",
        "steps": steps,
        "tool_calls_count": tool_calls_count,
        "email_attempted": email_attempted,
        "email_sent": email_sent,
        "email_status": email_status,
        "email_body": email_body,
    }


def generate_daily_briefing_for_user(user: dict, subscriptions: list) -> dict:
    """
    为某个用户生成今日简报。
    user: {id, name, email}
    subscriptions: [{topic, keyword}, ...]
    """
    topics = "、".join([s["topic"] for s in subscriptions])
    keywords = "、".join([s.get("keyword", "") for s in subscriptions if s.get("keyword")])

    query = f"""请为用户【{user['name']}】生成今天的AI新闻简报。
用户邮箱：{user['email']}
关注话题：{topics}
额外关键词：{keywords if keywords else '无'}

请你自主决定：
1. 是否先看看本地有什么缓存
2. 抓RSS新闻、联网搜热点
3. 按用户话题筛选
4. 生成简报后写入文件存档
5. 最后发送邮件到 {user['email']}
"""
    result = run_agent(query)
    return result
