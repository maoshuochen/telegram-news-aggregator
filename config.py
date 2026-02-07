import os

# 从 Zeabur 的环境变量中读取
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # 你的个人 TG ID，确保 Bot 只给你发消息
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
# 要订阅的频道 ID 列表（无需 @ 符号）
CHANNELS = [
    "TechCrunch",
    "wallstreetcn",
    "reuters_cn",
    "tnews365",
    "solidot",
    "landiansub",
    "OutsightChina",
    "outvivid",
]

# RSSHub 配置：可通过环境变量覆盖
RSSHUB_BASE_URL = os.getenv("RSSHUB_BASE_URL", "https://rsshub.app")
# 可选的备用 RSSHub 实例，逗号分隔
_rsshub_fallbacks = os.getenv("RSSHUB_FALLBACKS", "")
if _rsshub_fallbacks:
    RSSHUB_FALLBACKS = [u.strip() for u in _rsshub_fallbacks.split(",") if u.strip()]
else:
    RSSHUB_FALLBACKS = []

# LLM 分析配置
# 每篇文章的最大字符数（防止单篇过长挤占上下文）
ARTICLE_MAX_CHARS = int(os.getenv("ARTICLE_MAX_CHARS", "800"))
# 估算的 LLM 上下文限制（字符数，1 token ≈ 4 字符）
LLM_CONTEXT_LIMIT = int(os.getenv("LLM_CONTEXT_LIMIT", "120000"))
