"""主入口：启动 FastAPI 服务 + 定时任务"""
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import config
from api.routes import router
from scheduler.tasks import start_scheduler
import db.database as db

app = FastAPI(title="每日AI新闻助手 Agent")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册路由
app.include_router(router)


@app.on_event("startup")
def on_startup():
    # 确保数据库表存在
    db.init_db()
    # 启动定时任务
    start_scheduler()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
