"""Token 统计模块 - 响应头解析 + 估算后备"""
import json
import re


def estimate_input_tokens(request_body: dict) -> int:
    """估算输入 token 数量（用于 API 未返回时）

    Args:
        request_body: 请求体，包含 messages 或 prompt
    """
    if not request_body:
        return 0

    text = ""

    # 处理 messages 格式
    if "messages" in request_body:
        messages = request_body["messages"]
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")

                # 处理 content 格式
                if isinstance(content, str):
                    text += f"{role}: {content}\n"
                elif isinstance(content, list):
                    # 多模态内容（文本 + 图片）
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text += block.get("text", "")
                            elif block.get("type") == "image":
                                text += "[图片] "
                else:
                    text += str(content)

    # 处理 prompt 格式（Completion API）
    elif "prompt" in request_body:
        text = str(request_body["prompt"])

    return estimate_tokens(text)


def estimate_tokens(text: str) -> int:
    """Token 估算（响应头无 token 信息时的后备方案）

    中文字符每字约 1 token，英文每词约 0.75 token，其他每 3 字符约 1 token
    """
    if not text:
        return 0

    # 中文字符统计（每个约 1 token）
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))

    # 英文单词统计（每词约 0.75 token）
    english_words = len(re.findall(r"\b[a-zA-Z]+\b", text))

    # 其余字符（每 3 字符约 1 token）
    # 粗略减去已统计的英文字符（假设平均每词 5 字符）
    other = max(0, len(text) - chinese - english_words * 5)

    return chinese + int(english_words * 0.75) + other // 3


def count_chars(text: str) -> int:
    """纯字符计数，用于显示"""
    return len(text)


def parse_response_headers(headers: dict, api_type: str) -> tuple[int, int]:
    """从响应头解析 token 数量

    Args:
        headers: httpx 响应头
        api_type: "anthropic" 或 "openai"

    Returns:
        (input_tokens, output_tokens)
    """
    if api_type == "anthropic":
        input_tokens = int(headers.get("anthropic-input-tokens", 0))
        output_tokens = int(headers.get("anthropic-output-tokens", 0))
        return input_tokens, output_tokens

    elif api_type == "openai":
        # OpenAI 官方 API 通常不在响应头返回 token
        # 部分代理服务可能使用自定义头
        input_tokens = int(headers.get("x-prompt-tokens", 0))
        output_tokens = int(headers.get("x-completion-tokens", 0))
        return input_tokens, output_tokens

    return 0, 0


def parse_usage_block(usage: dict, api_type: str) -> tuple[int, int]:
    """从响应体的 usage 字段解析 token 数量

    Args:
        usage: API 响应中的 usage 对象
        api_type: "anthropic" 或 "openai"

    Returns:
        (input_tokens, output_tokens)
    """
    if not usage:
        return 0, 0

    if api_type == "anthropic":
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        return input_tokens, output_tokens

    elif api_type == "openai":
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        return input_tokens, output_tokens

    return 0, 0
