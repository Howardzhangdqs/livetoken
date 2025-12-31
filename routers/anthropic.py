"""Anthropic API 路由 - 代理并监控 Anthropic API 请求"""
import json

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from config import settings
from monitor import ApiType, EventType, store, monitor
from token_counter import estimate_tokens, estimate_input_tokens, parse_response_headers, parse_usage_block
from websocket import manager

router = APIRouter()


async def _process_streaming_response(
    client_response: httpx.Response,
    metrics_id: str,
) -> None:
    """处理流式响应并转发"""
    metrics = store.get_request(metrics_id)
    if not metrics:
        return

    accumulated_text = ""
    buffer = ""

    async for chunk in client_response.aiter_bytes():
        # 解码并处理
        buffer += chunk.decode("utf-8", errors="ignore")

        # 处理 SSE 行
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)

            yield line + "\n"

            if not line.startswith("data: "):
                continue

            # 跳过事件行
            if line.startswith("event:"):
                continue

            # 解析 JSON
            try:
                json_str = line[6:].strip()  # 去掉 "data: "
                if json_str == "[DONE]":
                    continue

                data = json.loads(json_str)
                event_type = data.get("type", "")

                if event_type == "content_block_delta":
                    # 提取文本内容
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            accumulated_text += text
                            metrics.add_content(text)
                            # 实时更新 token 统计
                            metrics.token_count = estimate_tokens(accumulated_text)

                            # 推送首字事件
                            if metrics.ttft is not None:
                                await manager.emit_first_token(metrics)

                            # 推送进度事件
                            await manager.emit_progress(metrics)
                            monitor.update()

                elif event_type == "message_stop":
                    # 尝试从最后的 usage 获取精确 token 数
                    usage = data.get("usage", {})
                    if usage:
                        _, output_tokens = parse_usage_block(usage, "anthropic")
                        if output_tokens:
                            metrics.token_count = output_tokens
                            metrics.tokens_estimated = False  # 精确值

            except (json.JSONDecodeError, KeyError):
                pass

    # 完成
    store.complete_request(metrics_id, metrics.input_tokens, metrics.token_count)
    await manager.emit_complete(metrics)
    monitor.update()


@router.post("/v1/messages")
@router.post("/messages")
async def proxy_messages(request: Request):
    """代理 Anthropic Messages API"""
    # 获取请求体
    body = await request.body()

    try:
        body_json = json.loads(body)
        model = body_json.get("model", "unknown")
        stream = body_json.get("stream", False)
    except json.JSONDecodeError:
        model = "unknown"
        stream = False

    # 创建指标记录
    metrics = store.create_request(ApiType.ANTHROPIC, model)
    metrics.request_body = body_json  # 保存请求体
    metrics.request_headers = dict(request.headers)  # 保存请求头
    await manager.emit_started(metrics)
    monitor.update()

    # 构建上游请求
    url = f"{settings.anthropic_base_url}/v1/messages"
    headers = {
        "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
        "content-type": "application/json",
    }

    # 转发认证头 - 支持多种格式
    # 优先使用客户端发送的认证头
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    elif "x-api-key" in request.headers:
        headers["x-api-key"] = request.headers["x-api-key"]
    elif settings.api_key:
        # 使用配置的默认 API Key，根据上游服务类型选择格式
        if "Bearer" in settings.api_key or "sk-" in settings.api_key:
            headers["authorization"] = settings.api_key
        else:
            headers["x-api-key"] = settings.api_key

    if stream:
        # 流式请求
        async def generate():
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, content=body, headers=headers) as upstream_resp:
                    # 保存响应头
                    metrics.response_headers = dict(upstream_resp.headers)
                    # 从响应头获取输入 tokens，如果没有则估算
                    input_tokens, _ = parse_response_headers(
                        dict(upstream_resp.headers), "anthropic"
                    )
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

            # 保存响应头
            metrics.response_headers = dict(upstream_resp.headers)

            # 解析响应获取 token 信息
            try:
                response_data = upstream_resp.json()
                usage = response_data.get("usage", {})
                input_tokens, output_tokens = parse_usage_block(usage, "anthropic")

                # 如果没有输入 tokens，则估算
                if not input_tokens:
                    input_tokens = estimate_input_tokens(body_json)

                # 更新指标
                metrics.token_count = output_tokens
                metrics.input_tokens = input_tokens
                if output_tokens:
                    metrics.tokens_estimated = False  # 精确值
                metrics.accumulated_text = response_data.get("content", [{}])[0].get("text", "")
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
