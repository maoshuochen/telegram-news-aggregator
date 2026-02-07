from typing import List, Optional
import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import LLM_API_KEY, LLM_BASE_URL
from logger import get_logger, report_error

logger = get_logger(__name__)

# LLM 上下文限制（字符数估算，大致 prompt + completion 总和）
# api2gpt gpt-5-mini 等模型的标准上下文约 128k tokens，保留 20% 安全余地
ESTIMATED_CONTEXT_LIMIT = 120000  # 字符数（1 token ≈ 4 字符）
ESTIMATED_COMPLETION_LIMIT = 20000  # 预留给输出的字符数

# 可复用的线程池执行器（用于异步化同步操作）
_executor = ThreadPoolExecutor(max_workers=3)


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数（字符数 / 4）"""
    return len(text) // 4


def _truncate_news_items(all_news: List[dict], max_chars: int) -> List[dict]:
    """
    裁剪新闻项，确保总字符数不超过 max_chars。
    优先保留完整项，超出后面的项将被截断或删除。
    """
    result = []
    total_chars = 0
    for item in all_news:
        source = item.get("source", "")
        content = item.get("content", "")[:800]  # 单篇文章最多 800 字符

        item_str = f"【来源: {source}】\n内容: {content}\n---\n"
        item_chars = len(item_str)

        if total_chars + item_chars <= max_chars:
            result.append(item)
            total_chars += item_chars
        else:
            # 如果已有内容，就停止；否则至少保留一条
            if result:
                break

    return result if result else all_news[:1]


def _call_llm_sync(
    prompt: str,
    max_tokens: int = 1200,
    attempt: int = 1,
    parent_finish_reason: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """
    同步调用 LLM 的核心逻辑。
    返回 (content, finish_reason)

    如果 finish_reason == "length" 且 content 非空，可以调用者决定是否续写。
    """
    url = f"{LLM_BASE_URL.rstrip('/')}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }
    payload = {
        "model": "gpt-5-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except Exception as e:
        logger.exception(f"[尝试 {attempt}] LLM 请求失败：%s", e)
        report_error(e, {"url": url, "attempt": attempt})
        return ("LLM 调用失败：无法连接到 LLM 服务，详见日志。", None)

    if resp.status_code != 200:
        logger.error(
            f"[尝试 {attempt}] LLM 返回非 200：%s %s", resp.status_code, resp.text
        )
        parsed_err = None
        try:
            parsed_err = resp.json()
        except Exception:
            parsed_err = None

        report_error(
            Exception(f"LLM status {resp.status_code}"),
            {"status_code": resp.status_code, "body": resp.text, "attempt": attempt},
        )

        # 识别常见错误
        if parsed_err and parsed_err.get("code") == "40003":
            return ("LLM API key 无效或不存在，请检查 LLM_API_KEY。", None)
        if (
            parsed_err
            and isinstance(parsed_err.get("message"), str)
            and "key does not exist" in parsed_err.get("message")
        ):
            return ("LLM API key 无效或不存在，请检查 LLM_API_KEY。", None)
        if "key does not exist" in (resp.text or ""):
            return ("LLM API key 无效或不存在，请检查 LLM_API_KEY。", None)

        return (f"LLM 调用失败：{resp.status_code}", None)

    try:
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            finish_reason = choice.get("finish_reason")

            # 提取内容
            content = ""
            if "message" in choice and "content" in choice["message"]:
                content = choice["message"]["content"]
            elif "text" in choice:
                content = choice["text"]

            logger.debug(
                f"[尝试 {attempt}] LLM 返回 finish_reason={finish_reason}, "
                f"content_len={len(content)}, tokens={data.get('usage', {})}"
            )

            # 检查内容是否为空
            if not content or not str(content).strip():
                logger.error(
                    f"[尝试 {attempt}] LLM 返回空内容 (finish_reason={finish_reason}): %s",
                    data,
                )
                report_error(
                    Exception("LLM returned empty content"),
                    {"response": data, "attempt": attempt},
                )
                return ("LLM 未返回可用内容，请检查日志或稍后重试。", finish_reason)

            return (content, finish_reason)

        logger.error(f"[尝试 {attempt}] LLM 返回格式不符合预期：%s", data)
        return ("LLM 返回了不可解析的响应，详见日志。", None)

    except Exception as e:
        logger.exception(f"[尝试 {attempt}] 解析 LLM 响应失败：%s", e)
        report_error(e, {"response_text": resp.text, "attempt": attempt})
        return ("解析 LLM 响应失败，详见日志。", None)


async def analyze_news(all_news: List[dict]) -> str:
    """
    异步分析新闻。

    流程：
    1. 估算 token，若超出则裁剪新闻项
    2. 在线程池中调用 LLM（避免阻塞事件循环）
    3. 若返回 finish_reason="length" 且内容非空，尝试续写
    4. 若内容为空且超出 token，则裁剪后重试
    """
    # 裁剪输入以确保不超过上下文限制
    max_input_chars = ESTIMATED_CONTEXT_LIMIT - ESTIMATED_COMPLETION_LIMIT
    truncated_news = _truncate_news_items(all_news, max_input_chars)

    # 构建初始 prompt
    context = ""
    for item in truncated_news:
        context += f"【来源: {item['source']}】\n内容: {item.get('content','')}\n---\n"

    prompt = f"""你是一个资深的新闻分析师。以下是过去几个小时内不同来源的资讯信息：
{context}

请执行以下任务：
1. 聚合相同事件：将讨论同一件事的新闻归类。
2. 多维度分析：如果同一个事件有多个来源，请对比它们在报道立场、侧重点或细节上的差异。
3. 每日精选：选出最值得关注的 3 条新闻。

请用 Markdown 格式输出，语言简洁专业。"""

    loop = asyncio.get_event_loop()

    # 第一次调用：完整 prompt
    content, finish_reason = await loop.run_in_executor(
        _executor,
        _call_llm_sync,
        prompt,
        1200,  # max_tokens
        1,  # attempt
        None,  # parent_finish_reason
    )

    # 若出错或返回了完整响应，直接返回
    if not isinstance(content, str) or content.startswith("LLM"):
        return content

    # 若因长度被截断且有内容，尝试续写
    if finish_reason == "length" and content:
        logger.info("检测到 finish_reason=length，尝试续写...")
        continuation_prompt = f"""继续完成上述分析任务。已完成内容：
{content}

请从上面中断的地方继续，补充剩余的分析内容。"""

        continuation, _ = await loop.run_in_executor(
            _executor,
            _call_llm_sync,
            continuation_prompt,
            800,  # 续写时减少 max_tokens
            2,  # attempt 2
            finish_reason,
        )

        if continuation and not continuation.startswith("LLM"):
            return content + "\n\n" + continuation
        # 续写失败，返回已有内容
        return content

    # 若内容为空且 token 超出，尝试更激进地裁剪后重试
    if not content or content.startswith("LLM"):
        if _estimate_tokens(prompt) > ESTIMATED_CONTEXT_LIMIT * 0.8:
            logger.warning("Token 预估超过 80% 限制，进行激进裁剪并重试...")
            aggressive_truncated = _truncate_news_items(all_news, max_input_chars // 2)

            aggressive_context = ""
            for item in aggressive_truncated:
                aggressive_context += f"【来源: {item['source']}】\n内容: {item.get('content','')[:400]}\n---\n"

            aggressive_prompt = f"""你是一个新闻分析师。这是来自多个来源的资讯摘要：
{aggressive_context}

请简洁地聚合主要事件并列出 3 条最值得关注的新闻，用 Markdown 格式输出。"""

            retry_content, _ = await loop.run_in_executor(
                _executor,
                _call_llm_sync,
                aggressive_prompt,
                800,
                3,  # attempt 3
                finish_reason,
            )

            if retry_content and not retry_content.startswith("LLM"):
                return retry_content

    return content if content else "LLM 未返回可用内容，请检查日志或稍后重试。"
