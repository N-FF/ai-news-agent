"""APScheduler 定时任务：每天定点为所有用户生成简报"""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import config
import db.database as db
from agent.loop import generate_daily_briefing_for_user

_scheduler = None


def daily_job():
    """每天定时跑：给每个有订阅的用户生成简报"""
    print(f"[{datetime.now()}] 定时任务触发，开始为所有用户生成简报...")
    users = db.get_all_users()
    for user in users:
        subs = db.get_subscriptions(user["id"])
        if not subs:
            continue
        try:
            output = generate_daily_briefing_for_user(user, subs)
            db.save_briefing(
                user_id=user["id"],
                title=f"今日AI新闻简报",
                content=output,
                news_count=0,
            )
            print(f"  -> 用户 {user['name']} 简报已生成")
        except Exception as e:
            print(f"  -> 用户 {user['name']} 生成失败: {e}")


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        daily_job,
        "cron",
        hour=config.DAILY_RUN_HOUR,
        minute=config.DAILY_RUN_MINUTE,
        id="daily_briefing",
    )
    _scheduler.start()
    print(f"定时任务已启动：每天 {config.DAILY_RUN_HOUR:02d}:{config.DAILY_RUN_MINUTE:02d} 自动生成简报")
