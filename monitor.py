"""监控统计模块 - 追踪请求指标并推送到 WebSocket"""
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Literal

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TaskID
from rich.table import Table
from rich.text import Text

from config import settings
from token_counter import estimate_tokens, count_chars


class ApiType(Enum):
    """API 类型"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"

    @property
    def color(self) -> str:
        return "blue" if self == ApiType.ANTHROPIC else "green"

    @property
    def short_code(self) -> str:
        return "ANT" if self == ApiType.ANTHROPIC else "OAI"


class EventType(Enum):
    """事件类型"""
    STARTED = "started"
    FIRST_TOKEN = "first_token"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class RequestMetrics:
    """单个请求的指标"""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8].upper())
    api_type: ApiType = ApiType.ANTHROPIC
    model: str = ""
    start_time: float = field(default_factory=time.time)
    first_token_time: float | None = None
    accumulated_text: str = ""  # 输出内容
    request_body: dict | None = None  # 请求体
    token_count: int = 0
    input_tokens: int = 0
    end_time: float | None = None
    error: str | None = None
    tokens_estimated: bool = True  # token 是否为估算值，默认 True

    @property
    def ttft(self) -> float | None:
        """首字时间 (秒)"""
        if self.first_token_time:
            return self.first_token_time - self.start_time
        return None

    @property
    def duration(self) -> float:
        """总耗时 (秒)"""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def token_speed(self) -> float:
        """Token 速度 (tokens/秒)"""
        if self.duration > 0:
            return self.token_count / self.duration
        return 0.0

    @property
    def char_count(self) -> int:
        """已生成字符数"""
        return count_chars(self.accumulated_text)

    def record_first_token(self):
        """记录首字时间"""
        if self.first_token_time is None:
            self.first_token_time = time.time()

    def add_content(self, text: str):
        """添加生成内容"""
        self.accumulated_text += text
        self.record_first_token()

    def to_event(self, event_type: EventType) -> dict:
        """转换为 WebSocket 事件"""
        return {
            "type": event_type.value,
            "request_id": self.request_id,
            "api_type": self.api_type.value,
            "model": self.model,
            "ttft": round(self.ttft, 3) if self.ttft else None,
            "tokens": self.token_count,
            "chars": self.char_count,
            "input_tokens": self.input_tokens,
            "speed": round(self.token_speed, 2),
            "duration": round(self.duration, 3),
            "error": self.error,
            "tokens_estimated": self.tokens_estimated,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

    def get_short_id(self) -> str:
        """获取短 ID"""
        return f"[{self.api_type.short_code}-{self.request_id}]"

    def get_model_display(self) -> str:
        """获取模型显示名称（截断）"""
        if len(self.model) > 30:
            return self.model[:27] + "..."
        return self.model

    def to_detail_dict(self) -> dict:
        """转换为详情字典（用于 API 返回）"""
        return {
            "request_id": self.request_id,
            "api_type": self.api_type.value,
            "model": self.model,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "ttft": round(self.ttft, 3) if self.ttft else None,
            "duration": round(self.duration, 3),
            "input_tokens": self.input_tokens,
            "output_tokens": self.token_count,
            "tokens_estimated": self.tokens_estimated,
            "speed": round(self.token_speed, 2),
            "request_body": self.request_body,
            "response_text": self.accumulated_text,
            "error": self.error,
        }


class MetricsStore:
    """指标存储和管理"""

    def __init__(self):
        self._requests: dict[str, RequestMetrics] = {}
        self._history: list[RequestMetrics] = []
        self._lock = Lock()
        self._max_history = settings.max_history

    def create_request(
        self,
        api_type: ApiType,
        model: str,
    ) -> RequestMetrics:
        """创建新请求记录"""
        with self._lock:
            metrics = RequestMetrics(api_type=api_type, model=model)
            self._requests[metrics.request_id] = metrics
            return metrics

    def get_request(self, request_id: str) -> RequestMetrics | None:
        """获取请求记录"""
        return self._requests.get(request_id)

    def complete_request(self, request_id: str, input_tokens: int = 0, output_tokens: int = 0) -> RequestMetrics | None:
        """完成请求，返回 metrics"""
        with self._lock:
            metrics = self._requests.get(request_id)
            if metrics:
                metrics.end_time = time.time()
                metrics.input_tokens = input_tokens
                metrics.token_count = output_tokens or metrics.token_count
                # 移入历史记录
                self._history.append(metrics)
                del self._requests[request_id]
                # 限制历史记录数量
                if len(self._history) > self._max_history:
                    self._history.pop(0)
                return metrics
            return None

    def get_active_requests(self) -> list[RequestMetrics]:
        """获取进行中的请求"""
        with self._lock:
            return list(self._requests.values())

    def get_history(self, limit: int = 50) -> list[RequestMetrics]:
        """获取历史记录"""
        with self._lock:
            return self._history[-limit:]

    def get_request_detail(self, request_id: str) -> dict | None:
        """获取请求详情"""
        with self._lock:
            # 先查进行中的
            metrics = self._requests.get(request_id)
            if not metrics:
                # 再查历史记录
                metrics = next((m for m in self._history if m.request_id == request_id), None)
            if metrics:
                return metrics.to_detail_dict()
            # 调试：打印当前状态
            print(f"[DEBUG] Looking for request_id: {request_id}")
            print(f"[DEBUG] Active requests: {list(self._requests.keys())}")
            print(f"[DEBUG] History count: {len(self._history)}")
            if self._history:
                print(f"[DEBUG] History IDs: {[m.request_id for m in self._history[:5]]}")
            return None

    def clear_history(self) -> int:
        """清除历史记录，返回清除数量"""
        with self._lock:
            count = len(self._history)
            self._history.clear()
            return count

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            total = len(self._history)
            if total == 0:
                return {
                    "total_requests": 0,
                    "avg_ttft": 0,
                    "avg_speed": 0,
                }

            completed = [m for m in self._history if m.ttft is not None]
            avg_ttft = sum(m.ttft for m in completed) / len(completed) if completed else 0
            avg_speed = sum(m.token_speed for m in self._history) / total

            return {
                "total_requests": total,
                "avg_ttft": round(avg_ttft, 3),
                "avg_speed": round(avg_speed, 2),
            }


# 全局存储实例
store = MetricsStore()


class ConsoleMonitor:
    """Rich Console 实时监控"""

    def __init__(self):
        self.console = Console()
        self.live = None
        self.enabled = settings.enable_console

    def start(self):
        """启动监控"""
        if not self.enabled:
            return
        self.live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=4,
        )
        self.live.start()

    def stop(self):
        """停止监控"""
        if self.live:
            self.live.stop()
            self.live = None

    def update(self):
        """更新显示"""
        if self.live:
            self.live.update(self._render())

    def _render(self) -> Panel:
        """渲染监控面板"""
        stats = store.get_stats()
        active = store.get_active_requests()

        # 主表格
        table = Table(
            show_header=False,
            box=None,
            expand=True,
            padding=(0, 1),
        )

        # 标题行
        header = Text()
        header.append("  📡 ", style="bold")
        header.append("LiveToken Monitor", style="bold cyan")
        header.append(f"  [{datetime.now().strftime('%H:%M:%S')}]", style="dim")
        table.add_row(header)

        if not active:
            table.add_row(Text("  等待请求...", style="dim italic"))
        else:
            for metrics in active:
                table.add_row(self._render_request(metrics))

        # 统计行
        stats_text = Text()
        stats_text.append(
            f"  统计: 今日 {stats['total_requests']} 请求 | "
            f"平均 TTFT: {stats['avg_ttft']}s | "
                    f"平均速度: {stats['avg_speed']} t/s",
            style="dim",
        )
        table.add_row(stats_text)

        return Panel(
            table,
            border_style="cyan",
            padding=(0, 0),
        )

    def _render_request(self, metrics: RequestMetrics) -> Text:
        """渲染单个请求"""
        text = Text()

        # 状态图标和 ID
        icon = "🔵" if metrics.api_type == ApiType.ANTHROPIC else "🟢"
        text.append(f"  {icon} ", style=metrics.api_type.color)
        text.append(metrics.get_short_id(), style=metrics.api_type.color)
        text.append(f" {metrics.get_model_display()}", style="dim")
        text.append("\n     ")

        # TTFT
        if metrics.ttft:
            text.append(f"TTFT: {metrics.ttft:.2f}s │ ", style="yellow")
        else:
            text.append("TTFT: -- │ ", style="dim")

        # Tokens
        text.append(f"Tokens: {metrics.token_count}", style="green")
        if metrics.input_tokens:
            text.append(f" (in: {metrics.input_tokens})", style="dim")
        text.append(f" │ Speed: {metrics.token_speed:.1f} t/s\n     ")

        # 进度条
        progress_bar = self._render_progress(metrics)
        text.append(progress_bar)

        return text

    def _render_progress(self, metrics: RequestMetrics) -> str:
        """渲染进度条"""
        # 估算进度（基于字符数，假设 2000 字符为完整响应）
        progress = min(1.0, metrics.char_count / 2000)
        filled = int(40 * progress)
        bar = "█" * filled + "░" * (40 - filled)
        percentage = int(progress * 100)

        return f"{bar} {percentage:3d}%"


# 全局监控实例
monitor = ConsoleMonitor()
