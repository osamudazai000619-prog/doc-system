print("--- 0. 开始运行 main.py ---")

from dotenv import load_dotenv
print("--- 1. dotenv 导入成功 ---")
load_dotenv()
print("--- 2. 环境变量加载成功 ---")

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("backend.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

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


# ========== 全局异常安全网 ==========
# 经验 368093：若错误响应/detail 或正常响应里混入了 bytes（例如把上传文件的
# 二进制拼进了异常消息），FastAPI 默认的 jsonable_encoder 会对 bytes 执行
# utf-8 解码，遇到非 UTF-8 字节（如 0xb2）触发 UnicodeDecodeError，导致连接
# 被中断、接口返回 500。这里注册自定义处理器，递归清洗掉 bytes，保证任何
# 情况下响应都是可 JSON 序列化的纯文本结构。
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request


def _sanitize(obj):
    """递归把对象里的 bytes 替换为安全字符串，保证 JSON 可序列化。"""
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8", errors="replace")
        except Exception:
            return "<binary data>"
    if isinstance(obj, dict):
        return {_sanitize(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, set):
        return [_sanitize(x) for x in obj]
    return obj


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(_sanitize(exc.errors()))},
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # 只暴露错误类型与简短信息，绝不回显可能含二进制的原始内容
    detail = _sanitize(f"{type(exc).__name__}: {exc}")
    return JSONResponse(status_code=500, content={"detail": detail})


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