from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.helpers import escape_markdown
import re
from config import BOT_TOKEN, CHAT_ID
from fetcher import (
    get_channel_news,
    list_subscriptions,
    add_subscription,
    get_all_news,
)
from analyzer import analyze_news
from logger import get_logger, report_error

logger = get_logger(__name__)


async def generate_digest():
    """核心聚合逻辑"""
    all_raw_news = get_all_news()

    if not all_raw_news:
        return "暂时没有抓取到新资讯。"

    return await analyze_news(all_raw_news)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("你好！发送 /digest 获取今日 AI 聚合新闻简报。")


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 鉴权：只允许你本人操作
    if str(update.effective_chat.id) != str(CHAT_ID):
        return

    status_msg = await update.message.reply_text("正在抓取多源资讯并分析中，请稍候...")
    report = await generate_digest()
    safe_report = _escape_markdown_preserve_links(report)
    await status_msg.edit_text(safe_report, parse_mode="MarkdownV2")


def _escape_markdown_preserve_links(text: str) -> str:
    pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    links = []

    def repl(match):
        links.append(match.group(0))
        return f"LINKTOKEN{len(links)-1}"

    temp = re.sub(pattern, repl, text)
    temp = escape_markdown(temp, version=2)
    for i, link in enumerate(links):
        temp = temp.replace(f"LINKTOKEN{i}", link)
    return temp


async def list_subs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = list_subscriptions()
    if not subs:
        await update.message.reply_text(
            "当前没有订阅源。使用 /add_sub <channel_id> 添加。"
        )
        return
    await update.message.reply_text("当前订阅源：\n" + "\n".join(subs))


async def add_sub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("用法：/add_sub <channel_id>")
        return
    channel_id = context.args[0]
    ok = add_subscription(channel_id)
    if ok:
        await update.message.reply_text(f"已添加订阅：{channel_id}")
    else:
        await update.message.reply_text(f"订阅已存在或无效：{channel_id}")


async def fetch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch RSSHub content for a specific channel: /fetch <channel_id> [limit]"""
    # 鉴权：只允许你本人操作
    if str(update.effective_chat.id) != str(CHAT_ID):
        return

    if len(context.args) == 0:
        await update.message.reply_text("用法：/fetch <channel_id> [limit]")
        return

    channel_id = context.args[0]
    try:
        limit = int(context.args[1]) if len(context.args) > 1 else 5
    except Exception:
        limit = 5

    status_msg = await update.message.reply_text(
        f"正在抓取 {channel_id} 的最新 {limit} 条 RSS..."
    )
    try:
        items = get_channel_news(channel_id, limit=limit)
    except Exception as e:
        logger.exception("抓取单个源失败：%s", e)
        report_error(e, {"channel_id": channel_id})
        await status_msg.edit_text(f"抓取失败：{e}")
        return

    if not items:
        await status_msg.edit_text("未能从该订阅源获取到内容（可能被限制或无条目）。")
        return

    # 构造较短的文本回复（避免过长）
    parts = []
    for it in items:
        title = it.get("title") or "(无标题)"
        content = (it.get("content") or "").strip().replace("\n", " ")
        if len(content) > 300:
            content = content[:300] + "..."
        link = it.get("link") or ""
        parts.append(f"- {title}\n{content}\n{link}")

    text = "\n\n".join(parts)
    # 如果文本过长，分多条发送
    if len(text) <= 4000:
        await status_msg.edit_text(text)
    else:
        await status_msg.edit_text(text[:4000])
        remaining = text[4000:]
        # 继续发送剩余部分
        while remaining:
            chunk = remaining[:4000]
            remaining = remaining[4000:]
            await update.message.reply_text(chunk)


async def global_error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler for the Application."""
    logger.exception("Unhandled exception during update processing: %s", context.error)
    try:
        report_error(
            context.error, {"update": getattr(update, "to_dict", lambda: str(update))()}
        )
    except Exception:
        logger.exception("Failed to send error report from global handler")


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("digest", digest_command))
    app.add_handler(CommandHandler("list_subs", list_subs_command))
    app.add_handler(CommandHandler("add_sub", add_sub_command))
    app.add_handler(CommandHandler("fetch", fetch_command))

    app.add_error_handler(global_error_handler)

    logger.info("Bot 正在运行...")
    app.run_polling()
