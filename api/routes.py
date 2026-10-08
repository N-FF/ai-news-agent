"""FastAPI 路由：用户注册、订阅偏好、历史简报、手动触发"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import db.database as db
from agent.loop import generate_daily_briefing_for_user

router = APIRouter()


# ============ 请求模型 ============
class UserCreate(BaseModel):
    name: str
    email: str


class SubscriptionCreate(BaseModel):
    user_email: str
    topic: str
    keyword: str = ""


class TriggerRequest(BaseModel):
    user_email: str


# ============ 页面 ============
@router.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


# ============ API：用户 ============
@router.post("/api/users")
def create_user(body: UserCreate):
    existing = db.get_user_by_email(body.email)
    if existing:
        return {"code": 0, "msg": "用户已存在", "user": existing}
    uid = db.create_user(body.name, body.email)
    return {"code": 0, "msg": "创建成功", "user": {"id": uid, "name": body.name, "email": body.email}}


@router.get("/api/users/{email}")
def get_user(email: str):
    user = db.get_user_by_email(email)
    if not user:
        return {"code": 1, "msg": "用户不存在"}
    subs = db.get_subscriptions(user["id"])
    return {"code": 0, "user": user, "subscriptions": subs}


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
    output = generate_daily_briefing_for_user(user, subs)
    # 存库
    db.save_briefing(
        user_id=user["id"],
        title=f"今日AI新闻简报",
        content=output,
        news_count=0,
    )
    return {"code": 0, "msg": "简报已生成并推送", "output": output}
