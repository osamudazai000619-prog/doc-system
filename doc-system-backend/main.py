print("--- 0. 开始运行 main.py ---")

from dotenv import load_dotenv
print("--- 1. dotenv 导入成功 ---")
load_dotenv()
print("--- 2. 环境变量加载成功 ---")

from fastapi import FastAPI
print("--- 3. FastAPI 导入成功 ---")
from fastapi.middleware.cors import CORSMiddleware
print("--- 4. CORS 导入成功 ---")

print("--- 5. 准备导入 upload 路由 ---")
from routers.upload import router as upload_router
print("--- 6. upload 路由导入成功 ---")

print("--- 7. 准备导入 extract 路由 ---")
from routers.extract import router as extract_router
print("--- 8. extract 路由导入成功 ---")

print("--- 9. 准备导入 export 路由 ---")
from routers.export import router as export_router
print("--- 10. export 路由导入成功 ---")

print("--- 10.1 准备导入 history 路由 ---")
from routers.history import router as history_router
print("--- 10.2 history 路由导入成功 ---")

print("--- 10.3 准备导入 drafts 路由 ---")
from routers.drafts import router as drafts_router
print("--- 10.4 drafts 路由导入成功 ---")

print("--- 10.5 准备导入 schemes 路由 ---")
from routers.schemes import router as schemes_router
print("--- 10.6 schemes 路由导入成功 ---")

print("--- 10.7 准备导入 assets 路由 ---")
from routers.assets import router as assets_router
print("--- 10.8 assets 路由导入成功 ---")

from db.database import init_db
init_db()
print("--- 10.9 数据库表初始化完成 ---")

app = FastAPI(title="文档信息提取系统", version="0.1.0")
print("--- 11. APP 实例化成功 ---")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(extract_router)
app.include_router(export_router)
app.include_router(history_router)
app.include_router(drafts_router)
app.include_router(schemes_router)
app.include_router(assets_router)

# 确保在文件最底部加上这段：
if __name__ == "__main__":
    import uvicorn
    import asyncio
    import sys

    # 1. 强制将 Windows 的底层异步策略切换为更稳定的 Selector 模式，阻止内核崩溃
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    print("--- 准备通过 Python 内部启动 Uvicorn ---")
    
    # 2. 直接传 app 对象（不加引号），避免文件被重复执行
    # 3. 强制使用 h11 纯 Python 解析器
    uvicorn.run(app, host="127.0.0.1", port=8000, loop="asyncio", http="h11")