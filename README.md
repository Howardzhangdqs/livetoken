# LiveToken Monitor

Claude Code API 请求实时监视器 - 支持同时代理和监控 Anthropic 与 OpenAI 格式的 API 请求。

## 功能特性

- 🔄 **双向代理**: 同时支持 Anthropic 和 OpenAI 格式的 API
- ⚡ **实时监控**: 首字时间 (TTFT)、Token 速度、请求耗时
- 📊 **双重展示**: Rich 终端面板 + Web 可视化界面
- 📡 **WebSocket 推送**: 实时推送请求进度到浏览器
- 🔍 **精确统计**: 优先从 API 响应头获取 token 数，后备估算方法

## 安装

```bash
# 克隆仓库
cd /data/github/livetoken

# 使用 uv 安装依赖
uv sync
```

## 使用

### 启动服务

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 7357
```

### 配置 Claude Code

在 Claude Code 配置中设置：

```yaml
baseurl: http://localhost:7357
```

### 访问 Web 面板

浏览器打开: http://localhost:7357

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LIVETOKEN_PORT` | 服务端口 | `7357` |
| `ANTHROPIC_BASE_URL` | Anthropic API 上游地址 | `https://api.anthropic.com` |
| `OPENAI_BASE_URL` | OpenAI API 上游地址 | `https://api.openai.com` |
| `API_KEY` | 默认 API Key（可选） | - |
| `ENABLE_CONSOLE` | 启用 Rich 终端输出 | `true` |
| `MAX_HISTORY` | 最大历史记录数 | `100` |

## 支持的 API 端点

### Anthropic 格式
- `POST /v1/messages` - Messages API
- `POST /messages` - 兼容旧路径

### OpenAI 格式
- `POST /v1/chat/completions` - Chat Completions API

## 监控指标

- **TTFT (Time to First Token)**: 从请求发出到收到第一个 token 的时间
- **Token 速度**: 每秒生成的 token 数量
- **总耗时**: 完整请求时长
- **输入/输出 Token 数**: 从 API 响应头或 usage 字段获取

## 项目结构

```
livetoken/
├── main.py              # FastAPI 主入口
├── config.py            # 配置管理
├── token_counter.py     # Token 统计
├── monitor.py           # 监控统计 + Rich Console
├── websocket.py         # WebSocket 推送
├── routers/
│   ├── anthropic.py     # Anthropic 路由
│   └── openai.py        # OpenAI 路由
└── static/
    ├── index.html       # Web 面板
    ├── app.js           # 前端逻辑
    └── style.css        # 样式
```

## License

MIT
