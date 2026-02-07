import feedparser
import os
import json
from typing import List
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import SSLError
from logger import get_logger, report_error
from config import (
    RSSHUB_BASE_URL,
    RSSHUB_FALLBACKS,
    RSSHUB_TIMEOUT,
    RSS_ITEMS_PER_CHANNEL,
    DEFAULT_CHANNELS,
)

logger = get_logger(__name__)

SUBSCRIPTIONS_FILE = os.path.join(os.path.dirname(__file__), "subscriptions.json")


def _build_session() -> requests.Session:
    """Build a requests session with retry/backoff for transient errors."""
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


_SESSION = _build_session()


def _ensure_subscriptions_file():
    if not os.path.exists(SUBSCRIPTIONS_FILE):
        try:
            with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CHANNELS, f, ensure_ascii=False, indent=2)
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
    """通过 RSSHub 抓取指定频道的最新消息，支持可配置的 RSSHub 实例和备用列表"""
    bases = [RSSHUB_BASE_URL] + list(RSSHUB_FALLBACKS)
    last_feed = None
    last_url = None

    for base in bases:
        rss_url = f"{base.rstrip('/')}/telegram/channel/{channel_id}"
        last_url = rss_url
        try:
            resp = _SESSION.get(rss_url, timeout=RSSHUB_TIMEOUT)
            status = resp.status_code
            feed = feedparser.parse(resp.content)
            bozo = getattr(feed, "bozo", False)
            bozo_exc = getattr(feed, "bozo_exception", None)
            entries_len = len(getattr(feed, "entries", []))

            logger.debug(
                "RSS try: base=%s channel=%s status=%s bozo=%s entries=%d",
                base,
                channel_id,
                status,
                bozo,
                entries_len,
            )

            if status and status != 200:
                logger.warning(
                    "RSSHub returned non-200 status for %s at %s: %s",
                    channel_id,
                    base,
                    status,
                )

            if bozo and bozo_exc:
                logger.warning(
                    "feedparser bozo for %s at %s: %s", channel_id, base, bozo_exc
                )
                report_error(
                    bozo_exc,
                    {"channel_id": channel_id, "url": rss_url, "status": status},
                )

            # consider this feed successful if we have at least one entry and status is 200 or unknown
            if entries_len > 0 and (status is None or status == 200):
                last_feed = feed
                logger.info(
                    "Using RSSHub base %s for channel %s (entries=%d)",
                    base,
                    channel_id,
                    entries_len,
                )
                break
            else:
                # try next base
                logger.debug(
                    "No entries from %s, will try next base if available", rss_url
                )
                continue

        except SSLError as e:
            logger.warning("SSL 错误，准备切换实例：channel=%s base=%s err=%s", channel_id, base, e)
            report_error(e, {"channel_id": channel_id, "url": rss_url, "ssl": True})
            continue
        except Exception as e:
            logger.exception("抓取频道 %s 在 %s 时发生错误：%s", channel_id, base, e)
            report_error(e, {"channel_id": channel_id, "url": rss_url})
            continue

    if last_feed is None:
        logger.warning("所有 RSSHub 实例均未返回内容，最后尝试 URL: %s", last_url)
        return []

    news_items = []
    try:
        for entry in last_feed.entries[:limit]:
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
        report_error(e, {"channel_id": channel_id, "url": last_url})
    return news_items


def get_all_news(limit_per_channel=RSS_ITEMS_PER_CHANNEL):
    """从所有已保存的订阅源抓取消息并合并返回"""
    channels = load_subscriptions()
    if not channels:
        return []

    all_items = []
    max_workers = min(5, len(channels))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(get_channel_news, ch, limit_per_channel): ch
            for ch in channels
        }
        for future in as_completed(futures):
            ch = futures[future]
            try:
                all_items.extend(future.result())
            except Exception as e:
                # 简单忽略单个源错误，调用方可记录或处理
                logger.error("抓取来源 %s 失败: %s", ch, e)
                report_error(e, {"channel": ch})
                continue
    return all_items
