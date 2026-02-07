from typing import List
import requests
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    ARTICLE_MAX_CHARS,
    LLM_CONTEXT_LIMIT,
    LLM_COMPLETION_LIMIT,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_THREADPOOL_WORKERS,
    LLM_TIMEOUT,
    LLM_RETRIES,
    LLM_RETRY_BACKOFF,
)
from logger import get_logger, report_error

logger = get_logger(__name__)

# LLM 上下文限制（字符数估算，大致 prompt + completion 总和）
# 通过环境变量 LLM_CONTEXT_LIMIT 配置
ESTIMATED_CONTEXT_LIMIT = LLM_CONTEXT_LIMIT
ESTIMATED_COMPLETION_LIMIT = LLM_COMPLETION_LIMIT  # 预留给输出的字符数

# 可复用的线程池执行器（用于异步化同步操作）
_executor = ThreadPoolExecutor(max_workers=LLM_THREADPOOL_WORKERS)


def _truncate_news_items(all_news: List[dict], max_chars: int) -> List[dict]:
    """
    裁剪新闻项，确保总字符数不超过 max_chars。
    尽量保留更多条目，必要时等比例缩短内容。
    """
    if not all_news:
        return []

    # 先计算每条的基础信息与内容长度
    items = []
    overhead = 0
    for item in all_news:
        source = item.get("source", "")
        content = item.get("content", "") or ""
        content = content[:ARTICLE_MAX_CHARS]
        prefix = f"【来源: {source}】\n内容: "
        suffix = "\n---\n"
        overhead += len(prefix) + len(suffix)
        items.append(
            {"item": item, "content": content, "prefix": prefix, "suffix": suffix}
        )

    # 可用字符预算
    budget = max_chars - overhead
    if budget <= 0:
        return all_news[:1]

    # 等比例分配内容长度，尽量保留更多条目
    total_content_len = sum(len(x["content"]) for x in items)
    if total_content_len <= budget:
        return [x["item"] for x in items]

    ratio = budget / max(total_content_len, 1)
    result = []
    for x in items:
        keep = max(50, int(len(x["content"]) * ratio))
        new_item = dict(x["item"])
        new_item["content"] = x["content"][:keep]
        result.append(new_item)

    return result


def _call_llm_sync(
    prompt: str,
    max_tokens: int = 1200,
    attempt: int = 1,
) -> str:
    """
    同步调用 LLM 的核心逻辑。
    返回 content 或错误提示字符串。
    """
    base = LLM_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        url = f"{base}/chat/completions"
    else:
        url = f"{base}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": LLM_TEMPERATURE,
    }

    for i in range(LLM_RETRIES + 1):
        try:
            resp = requests.post(
                url, json=payload, headers=headers, timeout=LLM_TIMEOUT
            )
        except Exception as e:
            if isinstance(e, requests.exceptions.Timeout):
                err_msg = "LLM 调用超时，请稍后重试。"
            elif isinstance(e, requests.exceptions.ConnectionError):
                err_msg = "LLM 连接失败，请检查网络或服务状态。"
            else:
                err_msg = "LLM 调用失败：无法连接到 LLM 服务，详见日志。"
            logger.exception(f"[尝试 {attempt}.{i}] LLM 请求失败：%s", e)
            report_error(e, {"url": url, "attempt": attempt, "retry": i})
            if i < LLM_RETRIES:
                time.sleep(LLM_RETRY_BACKOFF * (i + 1))
                continue
            return err_msg

        if resp.status_code in (429, 500, 502, 503, 504):
            logger.warning(
                "[尝试 %s.%s] LLM 返回可重试状态码：%s",
                attempt,
                i,
                resp.status_code,
            )
            if i < LLM_RETRIES:
                time.sleep(LLM_RETRY_BACKOFF * (i + 1))
                continue
            # fall through to error handling below
        # non-retryable status or retries exhausted
        break

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
            return "LLM API key 无效或不存在，请检查 LLM_API_KEY。"
        if (
            parsed_err
            and isinstance(parsed_err.get("message"), str)
            and "key does not exist" in parsed_err.get("message")
        ):
            return "LLM API key 无效或不存在，请检查 LLM_API_KEY。"
        if "key does not exist" in (resp.text or ""):
            return "LLM API key 无效或不存在，请检查 LLM_API_KEY。"

        if 400 <= resp.status_code < 500:
            return f"LLM 请求被拒绝（{resp.status_code}），请检查请求参数。"
        return f"LLM 调用失败：{resp.status_code}"

    try:
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            # 提取内容
            content = ""
            if "message" in choice and "content" in choice["message"]:
                content = choice["message"]["content"]
            elif "text" in choice:
                content = choice["text"]

            logger.debug(
                f"[尝试 {attempt}] LLM 返回 content_len={len(content)}, tokens={data.get('usage', {})}"
            )

            # 检查内容是否为空
            if not content or not str(content).strip():
                logger.error(
                    f"[尝试 {attempt}] LLM 返回空内容: %s",
                    data,
                )
                report_error(
                    Exception("LLM returned empty content"),
                    {"response": data, "attempt": attempt},
                )
                return "LLM 未返回可用内容，请检查日志或稍后重试。"

            return content

        logger.error(f"[尝试 {attempt}] LLM 返回格式不符合预期：%s", data)
        return "LLM 返回了不可解析的响应，详见日志。"

    except Exception as e:
        logger.exception(f"[尝试 {attempt}] 解析 LLM 响应失败：%s", e)
        report_error(e, {"response_text": resp.text, "attempt": attempt})
        return "解析 LLM 响应失败，详见日志。"


def _build_prompt(context: str) -> str:
    return f"""你是一个资深的新闻分析师。以下是来自不同来源的资讯信息：
{context}

请执行以下任务：
1. 聚合相同事件：将讨论同一件事的新闻归类。
2. 多维度分析：如果同一个事件有多个来源，请对比它们在报道立场、侧重点或细节上的差异。
3. 精选：选出最值得关注的 10 条新闻。

输出格式（严格遵守）：
【序号】标题
- 摘要：1 句
- 影响：1 句
- 来源：来源名[链接]; 来源名[链接]

要求：
- 仅输出 10 条，不足 10 条也不要编造或重复
- 标题不超过 20 字
- 每条必须是不同事件，不得把同一事件拆成多条
- 优先覆盖更多不同来源；若来源数量接近，以新闻重要性排序
- 来源必须使用原始链接，若有 Telegram 消息链接则优先使用（t.me/ 开头）
- 使用 Telegram MarkdownV2 的链接格式：来源名[链接] 写成 [来源名](URL)
- 不要向用户提问或要求补充信息
"""


async def analyze_news(all_news: List[dict]) -> str:
    """
    异步分析新闻。

    简化流程：
    1. 裁剪新闻项
    2. 完整 prompt 调用
    """
    # 裁剪输入以确保不超过上下文限制
    max_input_chars = ESTIMATED_CONTEXT_LIMIT - ESTIMATED_COMPLETION_LIMIT
    truncated_news = _truncate_news_items(all_news, max_input_chars)

    # 构建上下文
    context = ""
    for item in truncated_news:
        context += f"【来源: {item['source']}】\n内容: {item.get('content','')}\n---\n"

    loop = asyncio.get_running_loop()

    # 第一次调用：完整 prompt
    content = await loop.run_in_executor(
        _executor,
        _call_llm_sync,
        _build_prompt(context),
        LLM_MAX_TOKENS,  # max_tokens
        1,  # attempt
    )

    return (
        content
        if isinstance(content, str) and content.strip()
        else "LLM 未返回可用内容，请检查日志或稍后重试。"
    )
