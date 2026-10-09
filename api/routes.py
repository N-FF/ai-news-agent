"""FastAPI 路由：用户注册、订阅偏好、历史简报、手动触发"""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import db.database as db
from agent.loop import generate_daily_briefing_for_user

router = APIRouter()


# ============ 请求模型 ============
class UserCreate(BaseModel):
    name: str
    email: str
    timezone_name: str = "Asia/Shanghai"


class SubscriptionCreate(BaseModel):
    user_email: str
    topic: str
    keyword: str = ""


class TriggerRequest(BaseModel):
    user_email: str


class ScheduleUpdate(BaseModel):
    daily_send_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone_name: str = Field(min_length=1, max_length=64)


# ============ 页面 ============
@router.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


# ============ API：用户 ============
@router.post("/api/users")
def create_user(body: UserCreate):
    try:
        ZoneInfo(body.timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return {"code": 1, "msg": "无效的时区，请选择有效的 IANA 时区"}
    existing = db.get_user_by_email(body.email)
    if existing:
        return {"code": 0, "msg": "用户已存在", "user": existing}
    uid = db.create_user(body.name, body.email, body.timezone_name)
    return {"code": 0, "msg": "创建成功", "user": {"id": uid, "name": body.name, "email": body.email}}


@router.get("/api/users/{email}")
def get_user(email: str):
    user = db.get_user_by_email(email)
    if not user:
        return {"code": 1, "msg": "用户不存在"}
    subs = db.get_subscriptions(user["id"])
    return {"code": 0, "user": user, "subscriptions": subs}


@router.put("/api/users/{email}/schedule")
def update_user_schedule(email: str, body: ScheduleUpdate):
    try:
        ZoneInfo(body.timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return {"code": 1, "msg": "无效的时区，请选择有效的 IANA 时区"}
    if not db.update_user_schedule(email, body.daily_send_time, body.timezone_name):
        return {"code": 1, "msg": "用户不存在"}
    return {
        "code": 0,
        "msg": f"每日推送时间已设置为 {body.daily_send_time}（{body.timezone_name}）",
        "daily_send_time": body.daily_send_time,
        "timezone_name": body.timezone_name,
    }


# ============ API：订阅 ============
@router.post("/api/subscriptions")
def add_sub(body: SubscriptionCreate):
    user = db.get_user_by_email(body.user_email)
    if not user:
        return {"code": 1, "msg": "用户不存在"}
    db.add_subscription(user["id"], body.topic, body.keyword)
    subs = db.get_subscriptions(user["id"])
    return {"code": 0, "msg": "订阅成功", "subscriptions": subs}


@router.delete("/api/subscriptions/{sub_id}")
def del_sub(sub_id: int):
    db.delete_subscription(sub_id)
    return {"code": 0, "msg": "已删除"}


# ============ API：历史简报 ============
@router.get("/api/briefings/{email}")
def list_briefings(email: str):
    user = db.get_user_by_email(email)
    if not user:
        return {"code": 1, "msg": "用户不存在"}
    items = db.get_briefings(user["id"])
    return {"code": 0, "briefings": items}


# ============ API：手动触发一次 ============
@router.post("/api/trigger")
def trigger_now(body: TriggerRequest):
    user = db.get_user_by_email(body.user_email)
    if not user:
        return {"code": 1, "msg": "用户不存在"}
    subs = db.get_subscriptions(user["id"])
    if not subs:
        return {"code": 1, "msg": "请先设置订阅偏好"}
    # 跑 Agent
    result = generate_daily_briefing_for_user(user, subs)
    output = result["final_output"]
    if result["email_sent"]:
        # 历史简报保存用户实际收到的邮件正文，不保存 Agent 工具调用过程总结。
        db.save_briefing(
            user_id=user["id"],
            title="今日AI新闻简报",
            content=result["email_body"],
            news_count=0,
            briefing_date=datetime.now(ZoneInfo(user["timezone_name"])).strftime("%Y-%m-%d"),
        )
        message = "简报已生成并成功发送"
    elif result["email_attempted"]:
        message = f"简报已生成，但邮件未发送成功，未加入历史简报：{result['email_status']}"
    else:
        message = "简报已生成，但 Agent 未调用邮件发送工具，未加入历史简报"
    return {
        "code": 0,
        "msg": message,
        "output": output,
        "email_sent": result["email_sent"],
        "email_status": result["email_status"],
    }
