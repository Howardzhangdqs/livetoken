"""WebSocket 推送模块 - 实时推送请求事件到 Web 面板"""
import json
from typing import Set

from fastapi import WebSocket

from monitor import EventType, RequestMetrics, store


class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """接受新连接"""
        await websocket.accept()
        self._connections.add(websocket)

        # 发送当前状态
        await self._send_initial_state(websocket)

    def disconnect(self, websocket: WebSocket):
        """断开连接"""
        self._connections.discard(websocket)

    async def broadcast(self, event: dict):
        """广播事件到所有连接的客户端"""
        if not self._connections:
            return

        message = json.dumps(event, ensure_ascii=False)
        # 复制集合以避免迭代时修改
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                # 连接可能已断开，移除
                self._connections.discard(ws)

    async def _send_initial_state(self, websocket: WebSocket):
        """发送初始状态到新连接的客户端"""
        # 发送历史记录
        history = store.get_history()
        for metrics in reversed(history):
            event = metrics.to_event(EventType.COMPLETE)
            try:
                await websocket.send_text(json.dumps(event, ensure_ascii=False))
            except Exception:
                break

        # 发送当前进行中的请求
        active = store.get_active_requests()
        for metrics in active:
            event = metrics.to_event(EventType.PROGRESS)
            try:
                await websocket.send_text(json.dumps(event, ensure_ascii=False))
            except Exception:
                break

    async def emit_started(self, metrics: RequestMetrics):
        """发送请求开始事件"""
        await self.broadcast(metrics.to_event(EventType.STARTED))

    async def emit_first_token(self, metrics: RequestMetrics):
        """发送首字事件"""
        await self.broadcast(metrics.to_event(EventType.FIRST_TOKEN))

    async def emit_progress(self, metrics: RequestMetrics):
        """发送进度事件"""
        await self.broadcast(metrics.to_event(EventType.PROGRESS))

    async def emit_complete(self, metrics: RequestMetrics):
        """发送完成事件"""
        await self.broadcast(metrics.to_event(EventType.COMPLETE))

    async def emit_error(self, metrics: RequestMetrics, error: str):
        """发送错误事件"""
        metrics.error = error
        await self.broadcast(metrics.to_event(EventType.ERROR))


# 全局 WebSocket 管理器实例
manager = WebSocketManager()
