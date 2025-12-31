"""OpenAI API 路由 - 代理并监控 OpenAI 格式 API 请求"""
import json

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from config import settings
from monitor import ApiType, EventType, store, monitor
from token_counter import estimate_tokens, estimate_input_tokens, parse_usage_block
from websocket import manager

router = APIRouter()


async def _process_streaming_response(
    client_response: httpx.Response,
    metrics_id: str,
) -> None:
    """处理 OpenAI 流式响应并转发"""
    metrics = store.get_request(metrics_id)
    if not metrics:
        return

    accumulated_text = ""
    buffer = ""

    async for chunk in client_response.aiter_bytes():
        buffer += chunk.decode("utf-8", errors="ignore")

        # 处理 SSE 行
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)

            yield line + "\n"

            if not line.startswith("data: "):
                continue

            # 跳过 [DONE]
            if line.strip() == "data: [DONE]":
                continue

            # 解析 JSON
            try:
                json_str = line[6:].strip()
                data = json.loads(json_str)

                # 提取 choices 中的 delta.content
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")

                    if content:
                        accumulated_text += content
                        metrics.add_content(content)
                        metrics.token_count = estimate_tokens(accumulated_text)

                        # 推送事件
                        if metrics.ttft is not None:
                            await manager.emit_first_token(metrics)
                        await manager.emit_progress(metrics)
                        monitor.update()

                # 检查是否有 usage（OpenAI 可能在最后一个块返回）
                usage = data.get("usage")
                if usage:
                    _, output_tokens = parse_usage_block(usage, "openai")
                    if output_tokens:
                        metrics.token_count = output_tokens
                        metrics.tokens_estimated = False  # 精确值

            except (json.JSONDecodeError, KeyError, IndexError):
                pass

    # 完成
    store.complete_request(metrics.request_id, metrics.input_tokens, metrics.token_count)
    await manager.emit_complete(metrics)
    monitor.update()


@router.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request):
    """代理 OpenAI Chat Completions API"""
    body = await request.body()

    try:
        body_json = json.loads(body)
        model = body_json.get("model", "unknown")
        stream = body_json.get("stream", False)
    except json.JSONDecodeError:
        model = "unknown"
        stream = False

    # 创建指标记录
    metrics = store.create_request(ApiType.OPENAI, model)
    metrics.request_body = body_json  # 保存请求体
    await manager.emit_started(metrics)
    monitor.update()

    # 构建上游请求
    url = f"{settings.openai_base_url}/v1/chat/completions"
    headers = {"content-type": "application/json"}

    # 转发认证头 - 支持多种格式
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    elif "x-api-key" in request.headers:
        # 某些服务使用 x-api-key
        headers["x-api-key"] = request.headers["x-api-key"]
    elif settings.api_key:
        # 使用配置的默认 API Key
        if settings.api_key.startswith("Bearer "):
            headers["authorization"] = settings.api_key
        else:
            headers["authorization"] = f"Bearer {settings.api_key}"

    if stream:
        # 流式请求
        async def generate():
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, content=body, headers=headers) as upstream_resp:
                    # 尝试从响应头获取输入 tokens，如果没有则估算
                    input_tokens = int(upstream_resp.headers.get("x-prompt-tokens", 0))
                    if not input_tokens:
                        input_tokens = estimate_input_tokens(body_json)
                    metrics.input_tokens = input_tokens

                    async for chunk in _process_streaming_response(upstream_resp, metrics.request_id):
                        yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )
    else:
        # 非流式请求
        async with httpx.AsyncClient(timeout=None) as client:
            upstream_resp = await client.post(url, content=body, headers=headers)

            # 解析响应获取 token 信息
            try:
                response_data = upstream_resp.json()
                usage = response_data.get("usage", {})
                input_tokens, output_tokens = parse_usage_block(usage, "openai")

                # 如果没有输入 tokens，则估算
                if not input_tokens:
                    input_tokens = estimate_input_tokens(body_json)

                metrics.token_count = output_tokens
                metrics.input_tokens = input_tokens
                if output_tokens:
                    metrics.tokens_estimated = False  # 精确值

                # 提取生成内容用于统计
                choices = response_data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
                    metrics.accumulated_text = content

            except (json.JSONDecodeError, KeyError, TypeError):
                pass

            store.complete_request(metrics.request_id, metrics.input_tokens, metrics.token_count)
            await manager.emit_complete(metrics)
            monitor.update()

            return Response(
                content=upstream_resp.content,
                status_code=upstream_resp.status_code,
                headers=dict(upstream_resp.headers),
            )
