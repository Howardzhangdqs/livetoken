# LiveToken Monitor

> Claude Code API 请求实时监视器 - 支持同时代理和监控 Anthropic 与 OpenAI 格式的 API 请求

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)

## 功能特性

- **双向代理** - 同时支持 Anthropic 和 OpenAI 格式的 API
- **实时监控** - 首字时间 (TTFT)、Token 速度、请求耗时
- **Web 可视化** - 实时推送请求进度，左右分栏详情面板
- **终端面板** - Rich Console 实时显示请求状态
- **WebSocket 推送** - 毫秒级同步请求进度到浏览器
- **精确统计** - 优先从 API 响应头获取精确 token 数
- **请求详情** - 完整记录请求/响应头、请求体、响应内容
- **可拖动布局** - Web 面板支持左右分栏拖动调整

## 界面预览

### Web 面板
- **实时列表** - 显示所有请求的状态、模型、耗时、速度
- **详情弹窗** - 点击请求查看完整信息：
  - 左侧：请求头、响应头
  - 右侧：元数据、输入/输出内容
  - 支持 Raw/解析视图切换

### 终端面板
```
┏━━━━━━━━━━━━━━━━ LiveToken Monitor ━━━━━━━━━━━━━━━━┓
┃                                                  ┃
┃  🔵 req_abc123  claude-sonnet-4-20250514  进行中  ┃
┃  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ┃
┃  TTFT: 0.82s  速度: 45.2 t/s  Tokens: 234        ┃
┃                                                  ┃
┃  🟢 req_def456  glm-4.7             完成        ┃
┃  TTFT: 0.45s  速度: 78.1 t/s  Tokens: 512        ┃
└──────────────────────────────────────────────────┘
```

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/livetoken.git
cd livetoken

# 使用 uv 安装依赖（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 启动服务

```bash
# 使用 uv 启动
uv run uvicorn main:app --host 0.0.0.0 --port 7357

# 或直接启动
uvicorn main:app --host 0.0.0.0 --port 7357
```

### 配置 Claude Code

编辑 Claude Code 配置文件，添加：

```yaml
baseurl: http://localhost:7357
```

### 访问 Web 面板

浏览器打开：http://localhost:7357

## 配置

### 环境变量

| 变量                 | 说明                   | 默认值                      |
| -------------------- | ---------------------- | --------------------------- |
| `LIVETOKEN_PORT`     | 服务端口               | `7357`                      |
| `ANTHROPIC_BASE_URL` | Anthropic API 上游地址 | `https://api.anthropic.com` |
| `OPENAI_BASE_URL`    | OpenAI API 上游地址    | `https://api.openai.com`    |
| `API_KEY`            | 默认 API Key（可选）   | -                           |
| `ENABLE_CONSOLE`     | 启用 Rich 终端输出     | `true`                      |
| `MAX_HISTORY`        | 最大历史记录数         | `100`                       |

### 配置文件 (config.toml)

```toml
anthropic_base_url = "https://api.anthropic.com"
openai_base_url = "https://api.openai.com"
api_key = "sk-your-key-here"
enable_console = true
max_history = 100
```

## API 端点

### 代理端点

| 端点                   | 方法 | 格式             |
| ---------------------- | ---- | ---------------- |
| `/v1/messages`         | POST | Anthropic        |
| `/messages`            | POST | Anthropic (兼容) |
| `/v1/chat/completions` | POST | OpenAI           |

### 管理端点

| 端点                 | 方法      | 说明         |
| -------------------- | --------- | ------------ |
| `/`                  | GET       | Web 面板     |
| `/ws`                | WebSocket | 实时推送     |
| `/api/request/{id}`  | GET       | 获取请求详情 |
| `/api/clear-history` | POST      | 清除历史     |
| `/api/stats`         | GET       | 获取统计信息 |

## 监控指标

| 指标            | 说明                                         |
| --------------- | -------------------------------------------- |
| **TTFT**        | 首字时间 - 请求发出到收到第一个 token 的时间 |
| **Token 速度**  | 每秒生成的 token 数量 (tokens/second)        |
| **总耗时**      | 完整请求时长                                 |
| **输入 Tokens** | 从 API 响应头获取，后备估算                  |
| **输出 Tokens** | 从 usage 字段获取精确值或估算                |

## 项目结构

```
livetoken/
├── main.py              # FastAPI 主入口
├── config.py            # 配置管理
├── token_counter.py     # Token 统计与估算
├── monitor.py           # 监控核心 + Rich Console
├── websocket.py         # WebSocket 推送管理
├── routers/
│   ├── anthropic.py     # Anthropic API 路由
│   └── openai.py        # OpenAI API 路由
└── static/
    ├── index.html       # Web 面板入口
    ├── app.js           # 前端逻辑
    └── style.css        # 样式文件
```

## 开发

```bash
# 安装开发依赖
uv sync --dev

# 运行测试
pytest

# 代码格式化
black .
ruff check .
```

## License

MIT License - 详见 [LICENSE](LICENSE) 文件
