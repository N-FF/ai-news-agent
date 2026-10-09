"""APScheduler 定时任务：每天定点为所有用户生成简报"""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from zoneinfo import ZoneInfo
import config
import db.database as db
from agent.loop import generate_daily_briefing_for_user

_scheduler = None


def daily_job(now: datetime | None = None):
    """每分钟按每位用户的时区检查推送时间。"""
    now = now or datetime.now().astimezone()
    users = db.get_users_with_subscriptions()
    due_users = []
    for user in users:
        user_now = now.astimezone(ZoneInfo(user["timezone_name"]))
        if user_now.strftime("%H:%M") == user["daily_send_time"]:
            due_users.append((user, user_now))
    if not due_users:
        return

    print(f"[{now:%Y-%m-%d %H:%M:%S}] 到达用户推送时间，开始处理 {len(due_users)} 位用户...")
    for user, user_now in due_users:
        try:
            subs = db.get_subscriptions(user["id"])
            result = generate_daily_briefing_for_user(user, subs)
            if result["email_sent"]:
                # 历史简报的正文与成功发出的邮件正文保持一致。
                db.save_briefing(
                    user_id=user["id"],
                    title="今日AI新闻简报",
                    content=result["email_body"],
                    news_count=0,
                    briefing_date=user_now.strftime("%Y-%m-%d"),
                )
                print(f"  -> 用户 {user['name']} 简报已生成并发送")
            else:
                print(
                    f"  -> 用户 {user['name']} 未收到邮件，本次不写入历史简报："
                    f"{result['email_status']}"
                )
        except Exception as e:
            print(f"  -> 用户 {user['name']} 生成失败: {e}")


def cleanup_news_cache_job():
    removed = db.cleanup_old_news_cache(retention_days=30)
    if removed:
        print(f"新闻缓存清理完成：删除 {removed} 条超过 30 天的记录")


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        daily_job,
        "interval",
        minutes=1,
        id="check_user_briefing_schedules",
        coalesce=True,
        max_instances=1,
    )
    _scheduler.add_job(
        cleanup_news_cache_job,
        "cron",
        hour=3,
        minute=15,
        id="cleanup_old_news_cache",
        coalesce=True,
        max_instances=1,
    )
    _scheduler.start()
    print("定时任务已启动：每分钟检查用户各自设置的推送时间及时区")
