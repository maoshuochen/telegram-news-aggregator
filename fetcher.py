import feedparser
import os
import json
from typing import List
import logging
from logger import get_logger, report_error

logger = get_logger(__name__)

SUBSCRIPTIONS_FILE = os.path.join(os.path.dirname(__file__), "subscriptions.json")


def _ensure_subscriptions_file():
    if not os.path.exists(SUBSCRIPTIONS_FILE):
        try:
            with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
        except Exception as e:
            logger.exception("无法创建订阅文件 %s", SUBSCRIPTIONS_FILE)
            report_error(e, {"file": SUBSCRIPTIONS_FILE})


def load_subscriptions() -> List[str]:
    """加载本地保存的订阅（channel_id 列表）"""
    _ensure_subscriptions_file()
    try:
        with open(SUBSCRIPTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [str(x) for x in data]
    except Exception as e:
        logger.exception("加载订阅文件失败：%s", SUBSCRIPTIONS_FILE)
        report_error(e, {"file": SUBSCRIPTIONS_FILE})
        return []


def save_subscriptions(channels: List[str]):
    """保存订阅列表到文件"""
    try:
        os.makedirs(os.path.dirname(SUBSCRIPTIONS_FILE), exist_ok=True)
        with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("保存订阅文件失败：%s", SUBSCRIPTIONS_FILE)
        report_error(e, {"file": SUBSCRIPTIONS_FILE, "channels": channels})


def list_subscriptions() -> List[str]:
    """返回当前订阅源列表"""
    return load_subscriptions()


def add_subscription(channel_id: str) -> bool:
    """添加订阅；已存在返回 False，新增返回 True"""
    channel_id = str(channel_id).strip()
    if not channel_id:
        return False
    channels = load_subscriptions()
    if channel_id in channels:
        return False
    channels.append(channel_id)
    save_subscriptions(channels)
    return True


def remove_subscription(channel_id: str) -> bool:
    """移除订阅；存在并移除返回 True，否则返回 False"""
    channel_id = str(channel_id).strip()
    channels = load_subscriptions()
    if channel_id not in channels:
        return False
    channels = [c for c in channels if c != channel_id]
    save_subscriptions(channels)
    return True


def get_channel_news(channel_id, limit=5):
    """通过 RSSHub 抓取指定频道的最新消息"""
    rss_url = f"https://rsshub.app/telegram/channel/{channel_id}"
    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:
        logger.exception("抓取频道 %s 时发生错误：%s", channel_id, e)
        report_error(e, {"channel_id": channel_id, "url": rss_url})
        return []

    news_items = []
    try:
        for entry in feed.entries[:limit]:
            news_items.append(
                {
                    "source": channel_id,
                    "title": entry.get("title", ""),
                    "content": entry.get("summary", ""),
                    "link": entry.get("link", ""),
                }
            )
    except Exception as e:
        logger.exception("解析 RSS 条目失败：%s", channel_id)
        report_error(e, {"channel_id": channel_id, "url": rss_url})
    return news_items


def get_all_news(limit_per_channel=5):
    """从所有已保存的订阅源抓取消息并合并返回"""
    all_items = []
    for ch in load_subscriptions():
        try:
            all_items.extend(get_channel_news(ch, limit=limit_per_channel))
        except Exception as e:
            # 简单忽略单个源错误，调用方可记录或处理
            logger.error("抓取来源 %s 失败: %s", ch, e)
            report_error(e, {"channel": ch})
            continue
    return all_items
