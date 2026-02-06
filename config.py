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
