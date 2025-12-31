"""LiveToken Monitor - Claude Code API 请求实时监视器

主入口文件，启动 FastAPI 服务器。
"""
import contextlib
from importlib import metadata

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from monitor import monitor, store
from routers import anthropic, openai
from websocket import manager

# 读取版本
try:
    __version__ = metadata.version("livetoken")
except metadata.PackageNotFoundError:
    __version__ = "0.1.0"

# 创建 FastAPI 应用
app = FastAPI(
    title="LiveToken Monitor",
    description="Claude Code API 请求实时监视器",
    version=__version__,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(anthropic.router, tags=["Anthropic"])
app.include_router(openai.router, tags=["OpenAI"])

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """返回 Web 面板"""
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


@app.get("/api/request/{request_id}")
async def get_request_detail(request_id: str):
    """获取请求详情"""
    detail = store.get_request_detail(request_id)
    if not detail:
        return JSONResponse(status_code=404, content={"error": "Request not found"})
    return detail


@app.post("/api/clear-history")
async def clear_history():
    """清除历史记录"""
    count = store.clear_history()
    return {"cleared": count}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点，用于实时推送请求事件"""
    await manager.connect(websocket)
    try:
        # 保持连接
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    monitor.start()


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理"""
    monitor.stop()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
        reload=True,  # 自动重新加载
    )
