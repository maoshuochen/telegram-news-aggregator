# Analyzer 优化改进总结

## 概述
本次更新对 `analyzer.py` 进行了三项核心优化，以解决 LLM 返回空内容和因上下文限制导致请求失败的问题。

---

## 1️⃣ Token 预检查与自动裁剪

### 问题
前面的日志显示 LLM 返回空内容，原因是 `prompt_tokens = 21046`，加上 `completion_tokens = 1200`，已接近模型上下文限制，导致模型无法生成有意义的输出（finish_reason="length"）。

### 方案
- **Token 估算**: 使用粗略公式 `tokens ≈ chars / 4`（OpenAI 标准）来估算 prompt 大小
- **自动裁剪**:
  - 每篇文章最多 800 字符（可通过 `ARTICLE_MAX_CHARS` 环保量配置）
  - 当估算 tokens 接近 80% 限制时，自动进行激进裁剪（只保留最关键部分）
  - 优先保留完整的新闻项，确保内容完整性
- **分级裁剪策略**:
  - 第一次调用：使用完整输入（如果在限制内）
  - 若失败且超出 token：裁剪到 50% 并重试

### 代码实现
```python
def _estimate_tokens(text: str) -> int:
    return len(text) // 4

def _truncate_news_items(all_news, max_chars):
    # 逐项添加直到达到字符限制
```

---

## 2️⃣ 非阻塞异步执行

### 问题
原来的 `analyze_news()` 是同步函数，直接在 async handler 中调用会阻塞事件循环，特别是在等待 LLM 响应（通常 10-30 秒）时会影响其他 Telegram 事件的处理。

### 方案
- **线程池执行器**：使用 `asyncio.run_in_executor()` 将同步的 LLM 请求转移到后台线程池
  - 避免阻塞主事件循环
  - 允许 Telegram getUpdates 等操作继续进行
  - 配置 `ThreadPoolExecutor(max_workers=3)` 以限制并发数
- **函数签名变化**：`analyze_news()` 现在是 `async def`，必须用 `await` 调用

### 代码实现
```python
_executor = ThreadPoolExecutor(max_workers=3)

async def analyze_news(all_news):
    # 在线程池中执行同步的 LLM 调用
    content, finish_reason = await loop.run_in_executor(
        _executor,
        _call_llm_sync,
        prompt,
        1200,
        1,  # attempt
        None,
    )
```

### 调用方修改
在 `main.py` 的 `generate_digest()` 中：
```python
# 之前
return analyze_news(all_raw_news)

# 现在
return await analyze_news(all_raw_news)
```

---

## 3️⃣ 截断恢复与重试策略

### 问题
即使 LLM 因上下文长度被截断（finish_reason="length"），仍可能返回部分有用的内容。同时，若内容为空，单纯抛错不够有效，应该尝试更激进的裁剪后重试。

### 方案
- **续写（Continuation）**：
  - 检测 `finish_reason == "length"` 且 `content` 非空时，发送"请继续"prompt
  - 尝试让 LLM 补全被截断的分析
  - 续写时使用较小的 `max_tokens=800`（已有 1200 token 的内容）
  - 若续写成功，合并两部分内容；否则返回已有部分

- **激进重试**：
  - 当内容为空且 token 预估超过 80% 限制时，自动进行第二次尝试
  - 裁剪到原来的 50%，使用更简洁的 prompt（3 行而非 10 行）
  - 最多尝试 3 次（初始、续写、激进重试）

### 代码流程
```
[初始调用] → 
  ✓ 成功 & 内容非空 → 返回
  ✓ finish_reason="length" & 有内容 → [续写] → 返回合并
  ✗ 内容为空 & token 超出 → [激进重试] → 返回或降级提示
```

---

## 📊 改进效果预期

| 问题 | 原方案 | 新方案 | 期望改进 |
|------|-------|-------|---------|
| LLM 因 context 超出返回空 | 直接失败，返回错误提示 | 自动裁剪后重试，最多 3 次 | 避免空消息，提高成功率 |
| Event loop 阻塞（LLM 请求等待） | 同步阻塞 10-30 秒 | 异步线程池（非阻塞） | Telegram 消息响应更及时 |
| 输出被截断 | 返回空或不完整 | 检测截断后尝试续写 | 更完整的分析结果 |
| Token 浪费 | 无优化 | 估算 token 并自动裁剪输入 | 避免不必要的浪费，提高准确性 |

---

## 🔧 新增配置参数

在 `.env` 或环保变量中可配置：

```bash
# 每篇文章的最大字符数（防止单篇过长）
ARTICLE_MAX_CHARS=800

# 估算的 LLM 上下文限制（字符数）
LLM_CONTEXT_LIMIT=120000
```

默认值已调优，无需修改即可工作。

---

## 📝 日志示例

### 成功示例（带续写）
```
[尝试 1] LLM 返回 finish_reason=length, content_len=1200
检测到 finish_reason=length，尝试续写...
[尝试 2] LLM 返回 finish_reason=stop, content_len=300
→ 返回 content + continuation = ~1500 chars
```

### 自动重试示例
```
[尝试 1] LLM 返回空内容 (finish_reason=length)
Token 预估超过 80% 限制，进行激进裁剪并重试...
[尝试 3] LLM 返回 finish_reason=stop, content_len=600
→ 返回简洁版分析
```

---

## ✅ 测试验证

运行 `python test_analyzer.py` 验证：
- ✓ Token 估算准确性
- ✓ 新闻项裁剪逻辑
- ✓ 异步执行结构
- ✓ 完整的分析流程

---

## 🚀 后续优化方向

1. **RSSHub 调用也异步化**：目前 `fetcher.get_channel_news()` 仍是同步，可用 `run_in_executor` 包装
2. **自适应 max_tokens**：根据剩余 context 动态调整 `max_tokens`
3. **缓存优化**：缓存最近的 RSSHub 和 LLM 结果，避免频繁调用
4. **错误统计**：跟踪各类错误发生频率，优化裁剪策略

---

## 📌 关键代码位置

| 文件 | 函数 | 说明 |
|------|------|------|
| analyzer.py | `_estimate_tokens()` | Token 估算 |
| analyzer.py | `_truncate_news_items()` | 新闻裁剪 |
| analyzer.py | `_call_llm_sync()` | 核心 LLM 调用逻辑（带重试）|
| analyzer.py | `analyze_news()` | 异步入口点（使用 run_in_executor）|
| main.py | `generate_digest()` | 调用 analyzer 的地方（已加 await）|
| config.py | `ARTICLE_MAX_CHARS`, `LLM_CONTEXT_LIMIT` | 新增配置 |

---

## 总结

这次优化从 **三个角度** 提高了系统的健壮性：
1. **智能输入管理**：预估 token 并自动裁剪，避免超出限制
2. **非阻塞执行**：异步化 LLM 调用，保持 Telegram 事件响应性
3. **智能重试**：检测截断并尝试续写或重试，最大化成功率

预期能显著降低 "LLM 返回空内容" 和 "Event loop 阻塞" 的问题。
