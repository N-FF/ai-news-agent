"""APScheduler 定时任务：每天定点为所有用户生成简报"""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import config
import db.database as db
from agent.loop import generate_daily_briefing_for_user

_scheduler = None


def daily_job(now: datetime | None = None):
    """每分钟检查一次，为当前时间设置了推送且有订阅的用户生成简报。"""
    now = now or datetime.now()
    send_time = now.strftime("%H:%M")
    users = db.get_users_scheduled_for_time(send_time)
    if not users:
        return

    print(f"[{now:%Y-%m-%d %H:%M:%S}] 到达推送时间 {send_time}，开始处理 {len(users)} 位用户...")
    for user in users:
        try:
            subs = db.get_subscriptions(user["id"])
            result = generate_daily_briefing_for_user(user, subs)
            db.save_briefing(
                user_id=user["id"],
                title=f"今日AI新闻简报",
                content=result["final_output"],
                news_count=0,
            )
            if result["email_sent"]:
                print(f"  -> 用户 {user['name']} 简报已生成并发送")
            else:
                print(
                    f"  -> 用户 {user['name']} 简报已生成，但邮件未确认发送成功："
                    f"{result['email_status']}"
                )
        except Exception as e:
            print(f"  -> 用户 {user['name']} 生成失败: {e}")


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
    _scheduler.start()
    print("定时任务已启动：每分钟检查用户各自设置的每日推送时间（服务器本地时区）")
