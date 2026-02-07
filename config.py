import os

# 从 Zeabur 的环境变量中读取
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # 你的个人 TG ID，确保 Bot 只给你发消息
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5-nano")
# 默认订阅的频道 ID 列表（无需 @ 符号）
DEFAULT_CHANNELS = [
    "wallstreetcn",
    "reuters_cn",
]

# RSSHub 配置：可通过环境变量覆盖
RSSHUB_BASE_URL = os.getenv("RSSHUB_BASE_URL", "https://rsshub.rssforever.com")
# 可选的备用 RSSHub 实例，逗号分隔
_rsshub_fallbacks = os.getenv("RSSHUB_FALLBACKS", "")
if _rsshub_fallbacks:
    RSSHUB_FALLBACKS = [u.strip() for u in _rsshub_fallbacks.split(",") if u.strip()]
else:
    RSSHUB_FALLBACKS = []
# RSSHub 请求超时（秒）
RSSHUB_TIMEOUT = int(os.getenv("RSSHUB_TIMEOUT", "10"))
# 每个频道抓取的条数
RSS_ITEMS_PER_CHANNEL = int(os.getenv("RSS_ITEMS_PER_CHANNEL", "20"))

# LLM 分析配置
# 每篇文章的最大字符数（防止单篇过长挤占上下文）
ARTICLE_MAX_CHARS = int(os.getenv("ARTICLE_MAX_CHARS", "900"))
# 估算的 LLM 上下文限制（字符数，1 token ≈ 4 字符）
# GPT-5 mini: 400k context window -> 1,600,000 chars
LLM_CONTEXT_LIMIT = int(os.getenv("LLM_CONTEXT_LIMIT", "1600000"))
# 预留给输出的字符数（completion）
# GPT-5 mini: 128k max output -> 512,000 chars
LLM_COMPLETION_LIMIT = int(os.getenv("LLM_COMPLETION_LIMIT", "512000"))
# LLM 调用参数
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "40000"))
LLM_CONTINUATION_MAX_TOKENS = int(os.getenv("LLM_CONTINUATION_MAX_TOKENS", "128000"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.4"))
# 线程池并发（LLM 调用）
LLM_THREADPOOL_WORKERS = int(os.getenv("LLM_THREADPOOL_WORKERS", "3"))
# LLM 请求超时与重试
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
LLM_RETRIES = int(os.getenv("LLM_RETRIES", "2"))
LLM_RETRY_BACKOFF = float(os.getenv("LLM_RETRY_BACKOFF", "1.5"))
