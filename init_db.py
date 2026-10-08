"""数据库初始化脚本：建表 + 插入测试数据"""
import config
import db.database as db

if __name__ == "__main__":
    db.init_db()
    print("数据库初始化完成！")
    print(f"数据库文件位置：{config.DB_PATH}")
