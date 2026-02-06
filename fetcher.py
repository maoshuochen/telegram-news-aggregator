import feedparser
import requests


def get_channel_news(channel_id, limit=5):
    """通过 RSSHub 抓取指定频道的最新消息"""
    rss_url = f"https://rsshub.app/telegram/channel/{channel_id}"
    feed = feedparser.parse(rss_url)

    news_items = []
    for entry in feed.entries[:limit]:
        news_items.append(
            {
                "source": channel_id,
                "title": entry.get("title", ""),
                "content": entry.get("summary", ""),
                "link": entry.link,
            }
        )
    return news_items
