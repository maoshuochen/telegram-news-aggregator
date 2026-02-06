from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN, CHANNELS, CHAT_ID
from fetcher import get_channel_news
from analyzer import analyze_news


async def generate_digest():
    """核心聚合逻辑"""
    all_raw_news = []
    for ch in CHANNELS:
        try:
            all_raw_news.extend(get_channel_news(ch))
        except Exception as e:
            print(f"抓取 {ch} 失败: {e}")

    if not all_raw_news:
        return "暂时没有抓取到新资讯。"

    return analyze_news(all_raw_news)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("你好！发送 /digest 获取今日 AI 聚合新闻简报。")


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 鉴权：只允许你本人操作
    if str(update.effective_chat.id) != str(CHAT_ID):
        return

    status_msg = await update.message.reply_text("正在抓取多源资讯并分析中，请稍候...")
    report = await generate_digest()
    await status_msg.edit_text(report, parse_mode="Markdown")


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("digest", digest_command))

    print("Bot 正在运行...")
    app.run_polling()
